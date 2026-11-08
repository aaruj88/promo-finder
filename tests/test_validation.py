import pytest
from promofinder.models import Line, Episode, CandidateProposal, SegmentSpec
from promofinder.validator import validate_candidate

def create_mock_episode(number: int, num_lines: int = 10) -> Episode:
    lines = []
    for i in range(num_lines):
        line_id = f"L{i+1:02d}"
        lines.append(Line(
            episode=number,
            line_id=line_id,
            start_s=float(i * 5),
            end_s=float(i * 5 + 4),
            kind="dialogue" if i % 2 == 1 else "action",
            speaker="JULIANA" if i % 2 == 1 else None,
            emotion=None,
            text=f"Line {i+1} text.",
            scene="SCENE 01: INT. ROOM"
        ))
    return Episode(
        number=number,
        logline="Mock logline",
        continuity="Mock notes",
        lines=lines,
        duration_s=float(num_lines * 5)
    )

def test_duration_bounds_validation():
    ep1 = create_mock_episode(1, 20)  # total 100s
    ep_map = {1: ep1}

    # Too short (< 20s): L01 to L03 (0.0 to 14.0 = 14.0s)
    cand_short = CandidateProposal(
        segments=[SegmentSpec(episode=1, first_line_id="L01", last_line_id="L03")],
        hook_description="Short hook",
        cliffhanger_description="Short cliffhanger",
        rationale="Short"
    )
    res_short = validate_candidate(cand_short, ep_map, min_duration=20.0, max_duration=60.0)
    assert not res_short.is_valid
    assert "under minimum" in res_short.reject_reason

    # Too long (> 60s): L01 to L15 (0.0 to 74.0 = 74.0s)
    cand_long = CandidateProposal(
        segments=[SegmentSpec(episode=1, first_line_id="L01", last_line_id="L15")],
        hook_description="Long hook",
        cliffhanger_description="Long cliffhanger",
        rationale="Long"
    )
    res_long = validate_candidate(cand_long, ep_map, min_duration=20.0, max_duration=60.0)
    assert not res_long.is_valid
    assert "exceeds maximum" in res_long.reject_reason

    # Valid duration (between 20s and 60s): L01 to L08 (0.0 to 39.0 = 39.0s)
    cand_valid = CandidateProposal(
        segments=[SegmentSpec(episode=1, first_line_id="L01", last_line_id="L08")],
        hook_description="Valid hook",
        cliffhanger_description="Valid cliffhanger",
        rationale="Valid"
    )
    res_valid = validate_candidate(cand_valid, ep_map, min_duration=20.0, max_duration=60.0)
    assert res_valid.is_valid
    assert 20.0 <= res_valid.total_duration_s <= 60.0

def test_overlapping_and_order_validation():
    ep1 = create_mock_episode(1, 20)
    ep2 = create_mock_episode(2, 20)
    ep_map = {1: ep1, 2: ep2}

    # Overlapping segments in same episode
    cand_overlap = CandidateProposal(
        segments=[
            SegmentSpec(episode=1, first_line_id="L01", last_line_id="L06"),
            SegmentSpec(episode=1, first_line_id="L04", last_line_id="L09")
        ],
        hook_description="Overlap",
        cliffhanger_description="Overlap",
        rationale="Overlap"
    )
    res_overlap = validate_candidate(cand_overlap, ep_map, min_duration=5.0, max_duration=90.0)
    assert not res_overlap.is_valid
    assert "Overlapping segments" in res_overlap.reject_reason

    # Out of order episodes (Ep 2 before Ep 1)
    cand_order = CandidateProposal(
        segments=[
            SegmentSpec(episode=2, first_line_id="L01", last_line_id="L04"),
            SegmentSpec(episode=1, first_line_id="L01", last_line_id="L04")
        ],
        hook_description="Order",
        cliffhanger_description="Order",
        rationale="Order"
    )
    res_order = validate_candidate(cand_order, ep_map, min_duration=5.0, max_duration=90.0)
    assert not res_order.is_valid
    assert "out of order" in res_order.reject_reason

def test_mid_sentence_snapping():
    # Construct episode where line L02 ends in comma and L03 completes it
    lines = [
        Line(episode=1, line_id="L01", start_s=0.0, end_s=5.0, kind="action", text="Action.", scene="SCENE 01"),
        Line(episode=1, line_id="L02", start_s=5.0, end_s=10.0, kind="dialogue", speaker="JULIANA", text="\"Wait Gerald, I thought-\"", scene="SCENE 01"),
        Line(episode=1, line_id="L03", start_s=10.0, end_s=15.0, kind="dialogue", speaker="JULIANA", text="\"you loved me.\"", scene="SCENE 01"),
        Line(episode=1, line_id="L04", start_s=15.0, end_s=30.0, kind="action", text="Shock.", scene="SCENE 01"),
    ]
    ep = Episode(number=1, logline="Test", continuity="Test", lines=lines, duration_s=30.0)
    ep_map = {1: ep}

    # Spec specifies up to L02, but L02 ends with '-' mid-sentence from JULIANA
    cand = CandidateProposal(
        segments=[SegmentSpec(episode=1, first_line_id="L01", last_line_id="L02")],
        hook_description="Snap test",
        cliffhanger_description="Snap test",
        rationale="Snap test"
    )
    res = validate_candidate(cand, ep_map, min_duration=10.0, max_duration=60.0)
    assert res.is_valid
    # The end_s should have snapped to L03 (15.0s)
    assert res.segments[0].end_s == 15.0
    assert "you loved me" in res.segments[0].last_line

def test_hook_establishing_shot_flagging():
    # Episode starting with only wide establishing camera shots
    lines = [
        Line(episode=1, line_id="L01", start_s=0.0, end_s=4.0, kind="camera", text="Wide tracking shot of the grand cathedral.", scene="SCENE 01"),
        Line(episode=1, line_id="L02", start_s=4.0, end_s=8.0, kind="action", text="Juliana steps in.", scene="SCENE 01"),
        Line(episode=1, line_id="L03", start_s=8.0, end_s=30.0, kind="dialogue", speaker="JULIANA", text="Hello.", scene="SCENE 01"),
    ]
    ep = Episode(number=1, logline="Test", continuity="Test", lines=lines, duration_s=30.0)
    ep_map = {1: ep}

    cand = CandidateProposal(
        segments=[SegmentSpec(episode=1, first_line_id="L01", last_line_id="L03")],
        hook_description="Hook",
        cliffhanger_description="Cliff",
        rationale="Why"
    )
    res = validate_candidate(cand, ep_map, min_duration=10.0, max_duration=60.0, hook_window=3.0)
    assert res.is_valid
    assert res.hook_flag == "establishing_shot_only"

