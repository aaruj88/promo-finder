import os
import sys
import json

sys.path.insert(0, ".")
from promofinder.pipeline import PipelineRunner

def run_stability_test(input_dir: str = "./data", limit_episodes: int = 10):
    runner = PipelineRunner(config_path="./config.yaml")

    out_run1 = "./out/stability_run1"
    out_run2 = "./out/stability_run2"

    print("Running Pipeline Run 1...")
    promos_run1 = runner.run(input_dir=input_dir, out_dir=out_run1, limit_episodes=limit_episodes)

    print("Running Pipeline Run 2...")
    promos_run2 = runner.run(input_dir=input_dir, out_dir=out_run2, limit_episodes=limit_episodes)

    ids1 = [p.promo_id for p in promos_run1[:10]]
    ids2 = [p.promo_id for p in promos_run2[:10]]

    # Cut point equivalence (matching episode and start/end timestamps)
    cuts1 = {(p.segments[0].episode, p.segments[0].start_ts, p.segments[0].end_ts) for p in promos_run1[:10]}
    cuts2 = {(p.segments[0].episode, p.segments[0].start_ts, p.segments[0].end_ts) for p in promos_run2[:10]}

    overlap_ids = set(ids1).intersection(set(ids2))
    overlap_cuts = cuts1.intersection(cuts2)

    jaccard_id = len(overlap_ids) / len(set(ids1).union(set(ids2))) if set(ids1).union(set(ids2)) else 1.0
    persistence_count = len(overlap_cuts)

    print("\n====================================================")
    print("STABILITY TEST RESULTS (TOP-10 PICKS PERSISTENCE)")
    print("====================================================")
    print(f"Top 10 Picks Run 1: {ids1}")
    print(f"Top 10 Picks Run 2: {ids2}")
    print(f"Persistent Picks Count: {persistence_count} / 10 ({persistence_count * 10.0}%)")
    print(f"Jaccard Similarity:     {jaccard_id:.4f}")
    print("====================================================")
    return persistence_count, jaccard_id

if __name__ == "__main__":
    run_stability_test()
