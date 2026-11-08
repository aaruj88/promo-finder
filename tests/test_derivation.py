import pytest
from promofinder.parser import parse_episode_file
from promofinder.validator import validate_candidate
from promofinder.models import CandidateProposal, SegmentSpec

def test_line_id_to_timestamp_derivation():
    ep1 = parse_episode_file("./data/I Married a Broken Soldier. He was a Duke/episode-001-Episode 1671703.txt")
    ep_map = {1: ep1}
    
    # Candidate from L07 to L20
    # Let's see what timestamps L07 and L20 have
    l07 = [l for l in ep1.lines if l.line_id == "L07"][0]
    l20 = [l for l in ep1.lines if l.line_id == "L20"][0]
    
    cand = CandidateProposal(
        segments=[SegmentSpec(episode=1, first_line_id="L07", last_line_id="L20")],
        hook_description="Test hook",
        hook_type="confrontation",
        cliffhanger_description="Test cliffhanger",
        rationale="Test rationale"
    )
    
    res = validate_candidate(cand, ep_map, min_duration=5.0, max_duration=120.0)
    assert res.is_valid
    assert len(res.segments) == 1
    seg = res.segments[0]
    assert seg.start_s == l07.start_s
    assert seg.end_s >= l20.end_s
    assert seg.start_ts.count(":") == 1
    assert seg.end_ts.count(":") == 1

def test_invalid_line_id_rejection():
    ep1 = parse_episode_file("./data/I Married a Broken Soldier. He was a Duke/episode-001-Episode 1671703.txt")
    ep_map = {1: ep1}
    
    cand = CandidateProposal(
        segments=[SegmentSpec(episode=1, first_line_id="L999", last_line_id="L1000")],
        hook_description="Test",
        cliffhanger_description="Test",
        rationale="Test"
    )
    res = validate_candidate(cand, ep_map)
    assert not res.is_valid
    assert "not in Ep 1" in res.reject_reason

