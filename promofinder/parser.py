import os
import re
from typing import List, Dict, Optional, Tuple
from promofinder.models import Line, Episode

ALIAS_MAP = {
    "LADY JULIANA": "JULIANA",
    "JULIANA (O.S.)": "JULIANA",
    "JULIANA (V.O.)": "JULIANA",
    "LADY JULIANA (OFF-SCREEN)": "JULIANA",
    "LADY JULIANA (V.O.)": "JULIANA",
    "LADY CLARISSA": "CLARISSA",
    "CLARISSA (O.S.)": "CLARISSA",
    "LADY CATHERINE": "CATHERINE",
    "CATHERINE (O.S.)": "CATHERINE",
    "CATHERINE (V.O.)": "CATHERINE",
    "GERALD (O.S.)": "GERALD",
    "GERALD (V.O.)": "GERALD",
    "ALEXANDER (O.S.)": "ALEXANDER",
    "ALEXANDER (V.O.)": "ALEXANDER",
    "THE BEARDED STRANGER": "ALEXANDER",
    "THE BEARDED STRANGER (O.S.)": "ALEXANDER",
    "MYSTERIOUS BEARDED MAN": "ALEXANDER",
    "SCARRED BEARDED MAN": "ALEXANDER",
    "BLOND NOBLEMAN": "RUPERT",
    "BLOND NOBLEMAN (RUPERT)": "RUPERT",
    "BLOND NOBLEMAN (O.S.)": "RUPERT",
    "NOBLE MATRIARCH": "MATRIARCH",
    "MATRIARCH (O.S.)": "MATRIARCH",
    "HIGH PRIEST": "PRIEST",
    "HIGH PRIEST (O.S.)": "PRIEST",
    "THE PRIEST": "PRIEST",
    "LADY IN GOLD GOWN": "CLARISSA",
    "LADY IN GOLD GOWN (OFF-SCREEN)": "CLARISSA",
    "THE FORMER GROOM": "SEAMUS",
    "THE FORMER GROOM (OFF-SCREEN)": "SEAMUS",
    "POLICE CONSTABLE": "CONSTABLE",
    "JUDGE (O.S.)": "JUDGE",
    "ARISTOCRATIC WOMAN (O.S.)": "ARISTOCRATIC WOMAN",
    "DOWAGER DUCHESS (O.S.)": "DOWAGER DUCHESS",
}

def parse_timestamp_to_seconds(ts_str: str) -> float:
    """Parses mm:ss.ff or mm:ss into float seconds."""
    ts_str = ts_str.strip().strip("()")
    parts = ts_str.split(":")
    if len(parts) == 2:
        minutes = float(parts[0])
        seconds = float(parts[1])
        return round(minutes * 60.0 + seconds, 2)
    elif len(parts) == 3:
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        return round(hours * 3600.0 + minutes * 60.0 + seconds, 2)
    return float(ts_str)

def normalize_speaker(raw_label: str) -> Tuple[str, Optional[str], str]:
    """
    Normalizes speaker label and extracts kind, speaker, and emotion.
    Returns: (kind, speaker, emotion)
    """
    label_clean = raw_label.strip()
    
    # Extract emotion if in parentheses, e.g. "MATRIARCH (Cold, Commanding)"
    emotion = None
    emotion_match = re.search(r"\(([^)]+)\)", label_clean)
    if emotion_match:
        emotion = emotion_match.group(1).strip()
        label_base = re.sub(r"\([^)]+\)", "", label_clean).strip()
    else:
        label_base = label_clean

    label_upper = label_base.upper().rstrip(":")
    
    # Check kinds
    if label_upper in ["CAMERA"]:
        return "camera", None, emotion
    elif label_upper in ["ACTION"]:
        return "action", None, emotion
    elif label_upper in ["SOUND FX", "SFX", "SOUND"]:
        return "sfx", None, emotion
    
    # Otherwise it's dialogue
    normalized_name = ALIAS_MAP.get(label_upper, label_upper)
    return "dialogue", normalized_name, emotion

def parse_episode_file(filepath: str) -> Episode:
    """
    Parses an episode file into an Episode pydantic object.
    Robustly handles non-monotonic blocks, CRLF, varying scene casings, etc.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract headers
    ep_num_match = re.search(r"EPISODE NUMBER:\s*Episode\s*(\d+)", content, re.IGNORECASE)
    ep_number = int(ep_num_match.group(1)) if ep_num_match else 0
    if ep_number == 0:
        # Fallback to filename
        m = re.search(r"episode-(\d+)", os.path.basename(filepath), re.IGNORECASE)
        ep_number = int(m.group(1)) if m else 1

    logline_match = re.search(r"EPISODE LOGLINE:\s*(.*?)(?=\n[A-Z\s]+:|\n---|\Z)", content, re.IGNORECASE | re.DOTALL)
    logline = logline_match.group(1).strip() if logline_match else ""

    continuity_match = re.search(r"CONTINUITY NOTES:\s*(.*?)(?=\n[A-Z\s]+:|\n---|\Z)", content, re.IGNORECASE | re.DOTALL)
    continuity = continuity_match.group(1).strip() if continuity_match else ""

    # Split into scenes
    # Matches "SCENE 01", "SCENE 1", etc.
    scene_splits = list(re.finditer(r"(?i)^SCENE\s+(\d+)\s*\r?\n", content, re.MULTILINE))
    
    raw_blocks: List[Dict] = []
    
    if not scene_splits:
        # Single implicit scene if no explicit SCENE markers found
        scene_splits = []
        scene_spans = [(0, len(content), "SCENE 01: UNTITLED")]
    else:
        scene_spans = []
        for i, match in enumerate(scene_splits):
            sc_idx = match.group(1)
            start_pos = match.start()
            end_pos = scene_splits[i+1].start() if i + 1 < len(scene_splits) else len(content)
            
            # Find scene heading within this segment
            scene_text = content[start_pos:end_pos]
            heading_m = re.search(r"(?i)Scene heading:\s*(.*?)\r?\n", scene_text)
            heading_str = heading_m.group(1).strip() if heading_m else ""
            scene_label = f"SCENE {sc_idx}: {heading_str}".strip(" :")
            scene_spans.append((start_pos, end_pos, scene_label))

    # Regex for blocks:
    # **LABEL (optional emotion):**
    # Start: (mm:ss.ff) | End: (mm:ss.ff)
    # text
    block_pattern = re.compile(
        r"\*\*([^*]+?):?\*\*:?\s*\r?\n"
        r"Start:\s*\(([0-9:.]+)\)\s*\|\s*End:\s*\(([0-9:.]+)\)\r?\n"
        r"(.*?)(?=\r?\n\*\*|\r?\n(?i:SCENE\s+\d+)|\r?\n--- SCRIPT END ---|\Z)",
        re.DOTALL
    )

    for sc_start, sc_end, scene_label in scene_spans:
        sc_content = content[sc_start:sc_end]
        for m in block_pattern.finditer(sc_content):
            raw_label = m.group(1).strip()
            st_s = parse_timestamp_to_seconds(m.group(2))
            end_s = parse_timestamp_to_seconds(m.group(3))
            raw_text = m.group(4).strip()
            
            # Clean dialogue text (strip surrounding quotes if dialogue)
            kind, speaker, emotion = normalize_speaker(raw_label)
            clean_text = raw_text.strip()
            if kind == "dialogue":
                if clean_text.startswith('"') and clean_text.endswith('"'):
                    clean_text = clean_text[1:-1].strip()

            raw_blocks.append({
                "original_order": len(raw_blocks),
                "start_s": st_s,
                "end_s": end_s,
                "kind": kind,
                "speaker": speaker,
                "emotion": emotion,
                "text": clean_text,
                "scene": scene_label
            })

    # Sort blocks by start time, using original file order as tiebreak
    raw_blocks.sort(key=lambda b: (b["start_s"], b["original_order"]))

    # Assign sequential line IDs: L01, L02, ...
    lines: List[Line] = []
    for idx, b in enumerate(raw_blocks):
        line_id = f"L{idx+1:02d}"
        lines.append(Line(
            episode=ep_number,
            line_id=line_id,
            start_s=b["start_s"],
            end_s=b["end_s"],
            kind=b["kind"],
            speaker=b["speaker"],
            emotion=b["emotion"],
            text=b["text"],
            scene=b["scene"]
        ))

    duration_s = max((l.end_s for l in lines), default=0.0)
    
    return Episode(
        number=ep_number,
        logline=logline,
        continuity=continuity,
        lines=lines,
        duration_s=duration_s
    )

def parse_all_episodes(directory: str) -> List[Episode]:
    """Parses all episode files in the given directory or show subdirectory."""
    files = []
    if os.path.isdir(directory):
        for root, _, filenames in os.walk(directory):
            for fn in filenames:
                if fn.startswith("episode-") and fn.endswith(".txt"):
                    files.append(os.path.join(root, fn))
    files.sort(key=lambda p: int(re.search(r"episode-(\d+)", os.path.basename(p)).group(1)))
    return [parse_episode_file(f) for f in files]

