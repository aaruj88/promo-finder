import os
import json
import logging
from typing import List, Dict, Optional
from promofinder.models import (
    Episode,
    ValidatedSegment,
    ColdViewerOutput,
)
from promofinder.llm import LLMClient
from promofinder.prompt_loader import load_prompt_file

logger = logging.getLogger("promofinder.cold_viewer")

def render_clip_lines_text(segments: List[ValidatedSegment], episodes_by_num: Dict[int, Episode]) -> str:
    """
    Renders ONLY the text of the lines included in the promo clip segments.
    Omits line IDs, timestamps, and metadata to simulate what a viewer sees/hears.
    """
    rendered_parts = []
    for seg in segments:
        ep = episodes_by_num.get(seg.episode)
        if not ep:
            continue
        seg_lines = [
            l for l in ep.lines
            if l.start_s >= seg.start_s and l.end_s <= seg.end_s + 0.1
        ]
        current_scene = None
        for l in seg_lines:
            if l.scene != current_scene:
                current_scene = l.scene
                rendered_parts.append(f"\n[{current_scene}]")
            if l.kind == "dialogue":
                spk = l.speaker or "CHARACTER"
                emo = f" ({l.emotion})" if l.emotion else ""
                rendered_parts.append(f"{spk}{emo}: \"{l.text}\"")
            elif l.kind == "action":
                rendered_parts.append(f"(ACTION: {l.text})")
            elif l.kind == "camera":
                rendered_parts.append(f"(VISUAL: {l.text})")
            elif l.kind == "sfx":
                rendered_parts.append(f"(SOUND: {l.text})")

    return "\n".join(rendered_parts).strip()

def run_cold_viewer_test(
    segments: List[ValidatedSegment],
    episodes_by_num: Dict[int, Episode],
    llm: LLMClient,
    cache_dir: str = "./.cache/cold_viewer"
) -> ColdViewerOutput:
    """
    Stage 4: Cold-viewer test.
    The evaluator sees ONLY the clip text (no bible, no logline, no external context).
    Evaluates:
    - who are characters
    - situation
    - confusing points
    - standalone score (1 to 5)
    """
    clip_text = render_clip_lines_text(segments, episodes_by_num)
    
    system_prompt = load_prompt_file("prompts/cold_viewer.md")

    user_prompt = (
        "Here is a short video clip transcript from a microdrama. "
        "You have never seen this show before. Evaluate how well it stands on its own:\n\n"
        f"--- CLIP START ---\n{clip_text}\n--- CLIP END ---"
    )

    try:
        output = llm.call_structured(
            schema=ColdViewerOutput,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.2
        )
        return output
    except Exception as e:
        logger.error(f"Cold-viewer evaluation failed: {e}")
        return ColdViewerOutput(
            characters=["Unknown"],
            situation="Evaluation error",
            confusing_points=["Evaluation failed"],
            standalone_score=3,
            notes=str(e)
        )

