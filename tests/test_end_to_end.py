import os
import json
import pytest
from promofinder.pipeline import PipelineRunner

def test_pipeline_end_to_end_3_episodes():
    out_dir = "./out/test_3_episodes"
    os.makedirs(out_dir, exist_ok=True)
    
    runner = PipelineRunner(config_path="./config.yaml")
    promos = runner.run(
        input_dir="./data",
        out_dir=out_dir,
        limit_episodes=3,
        enable_cold_viewer=True,
        enable_pairwise=True
    )

    assert len(promos) > 0, "Pipeline should return at least one ranked promo"
    
    # Check promos.json exists and is valid
    promos_json_file = os.path.join(out_dir, "promos.json")
    assert os.path.exists(promos_json_file)
    with open(promos_json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == len(promos)

    # Check report.md exists
    report_file = os.path.join(out_dir, "report.md")
    assert os.path.exists(report_file)
    with open(report_file, "r", encoding="utf-8") as f:
        report_text = f.read()
    assert "Executive Summary" in report_text
    assert "Top 3 Promos to Post First" in report_text

    # Validate output schema of top promo
    p0 = promos[0]
    assert p0.rank == 1
    assert p0.promo_id
    assert 20.0 <= p0.total_duration_s <= 60.0
    assert len(p0.segments) >= 1
    assert p0.hook
    assert p0.cliffhanger
    assert p0.why_it_works
    assert "total" in p0.scores
    assert "spoiler_risk" in p0.flags

    for seg in p0.segments:
        assert seg.episode in [1, 2, 3]
        assert seg.start_s < seg.end_s
        assert seg.start_ts
        assert seg.end_ts
        assert seg.first_line
        assert seg.last_line

