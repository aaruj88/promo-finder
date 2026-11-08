import pytest
import os
import glob
from promofinder.parser import parse_episode_file, parse_all_episodes, parse_timestamp_to_seconds, normalize_speaker

DATA_DIR = "./data"

def test_parse_timestamp():
    assert parse_timestamp_to_seconds("00:00.00") == 0.0
    assert parse_timestamp_to_seconds("01:15.50") == 75.50
    assert parse_timestamp_to_seconds("02:18.00") == 138.00
    assert parse_timestamp_to_seconds("(00:11.30)") == 11.30

def test_normalize_speaker():
    kind, spk, emo = normalize_speaker("CAMERA")
    assert kind == "camera"
    assert spk is None
    
    kind, spk, emo = normalize_speaker("ACTION")
    assert kind == "action"
    
    kind, spk, emo = normalize_speaker("SOUND FX")
    assert kind == "sfx"
    
    kind, spk, emo = normalize_speaker("MATRIARCH (Cold, Commanding)")
    assert kind == "dialogue"
    assert spk == "MATRIARCH"
    assert emo == "Cold, Commanding"

    kind, spk, emo = normalize_speaker("LADY JULIANA (Confused, Breathless)")
    assert kind == "dialogue"
    assert spk == "JULIANA"

    kind, spk, emo = normalize_speaker("THE BEARDED STRANGER")
    assert kind == "dialogue"
    assert spk == "ALEXANDER"

def test_all_50_episodes_parse():
    episodes = parse_all_episodes(DATA_DIR)
    assert len(episodes) == 50, f"Expected 50 episodes, got {len(episodes)}"
    
    for ep in episodes:
        assert ep.number > 0, f"Episode number invalid: {ep.number}"
        assert len(ep.lines) > 0, f"Episode {ep.number} has no lines"
        assert ep.logline, f"Episode {ep.number} has no logline"
        # Plausible durations: between 60s and 250s
        assert 60.0 <= ep.duration_s <= 250.0, f"Episode {ep.number} duration implausible: {ep.duration_s}s"
        
        # Verify line schema and monotonic ordering after parse
        prev_st = -0.01
        for line in ep.lines:
            assert line.episode == ep.number
            assert line.line_id.startswith("L")
            assert line.start_s <= line.end_s
            assert line.start_s >= prev_st, f"Lines not sorted by start time in ep {ep.number}: {line.start_s} < {prev_st}"
            assert line.kind in ["camera", "action", "sfx", "dialogue"]
            assert line.text, f"Empty text in ep {ep.number} {line.line_id}"
            assert line.scene, f"Empty scene in ep {ep.number} {line.line_id}"
            prev_st = line.start_s

def test_non_monotonic_sorting_handling():
    # Synthetic test where blocks are in reverse or scrambled order
    synthetic_script = """EPISODE NUMBER: Episode 999
EPISODE LOGLINE: Test logline
CONTINUITY NOTES: Test notes

--- SCRIPT START ---

SCENE 01
Scene heading: INT. ROOM – DAY
Scene start: 00:00.00
Scene end: 01:00.00

**CAMERA:**
Start: (00:10.00) | End: (00:15.00)
Shot 2

**ACTION:**
Start: (00:01.00) | End: (00:05.00)
Shot 1

**LADY JULIANA:**
Start: (00:01.00) | End: (00:04.00)
"Simultaneous line"
"""
    tmp_path = "test_synthetic_ep.txt"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(synthetic_script)
        ep = parse_episode_file(tmp_path)
        assert len(ep.lines) == 3
        # L01 should have start_s == 1.0 (ACTION was first in file among start=1.0)
        assert ep.lines[0].line_id == "L01"
        assert ep.lines[0].start_s == 1.0
        assert ep.lines[0].kind == "action"
        
        # L02 should have start_s == 1.0 (LADY JULIANA was second in file)
        assert ep.lines[1].line_id == "L02"
        assert ep.lines[1].start_s == 1.0
        assert ep.lines[1].kind == "dialogue"
        assert ep.lines[1].speaker == "JULIANA"

        # L03 should have start_s == 10.0 (CAMERA)
        assert ep.lines[2].line_id == "L03"
        assert ep.lines[2].start_s == 10.0
        assert ep.lines[2].kind == "camera"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

