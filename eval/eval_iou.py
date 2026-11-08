import json
import argparse
from typing import List, Dict, Any, Tuple

def compute_segment_iou(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    """Computes Intersection-over-Union (IoU) between two 1D time ranges."""
    intersection = max(0.0, min(end_a, end_b) - max(start_a, start_b))
    union = max(end_a, end_b) - min(start_a, start_b)
    if union <= 0.0:
        return 0.0
    return round(intersection / union, 4)

def evaluate_iou(gold_path: str, pred_path: str, iou_threshold: float = 0.5) -> Dict[str, Any]:
    with open(gold_path, "r", encoding="utf-8") as f:
        gold_promos = json.load(f)

    with open(pred_path, "r", encoding="utf-8") as f:
        pred_promos = json.load(f)

    results = []
    hits = 0

    for gold in gold_promos:
        g_ep = gold["episode"]
        g_start = gold["start_s"]
        g_end = gold["end_s"]

        best_iou = 0.0
        best_pred = None

        # Compare against all predicted segments for this episode
        for pred in pred_promos:
            for seg in pred["segments"]:
                if seg["episode"] == g_ep:
                    iou = compute_segment_iou(g_start, g_end, seg["start_s"], seg["end_s"])
                    if iou > best_iou:
                        best_iou = iou
                        best_pred = pred

        is_hit = best_iou >= iou_threshold
        if is_hit:
            hits += 1

        results.append({
            "gold_id": gold["promo_id"],
            "episode": g_ep,
            "gold_range": f"{gold['start_ts']} - {gold['end_ts']} ({g_start}s - {g_end}s)",
            "best_matched_promo": best_pred["promo_id"] if best_pred else "NONE",
            "best_pred_range": f"{best_pred['segments'][0]['start_ts']} - {best_pred['segments'][0]['end_ts']}" if best_pred else "N/A",
            "iou": best_iou,
            "hit": is_hit
        })

    avg_iou = sum(r["iou"] for r in results) / len(results) if results else 0.0
    hit_rate = hits / len(results) if results else 0.0

    return {
        "gold_count": len(gold_promos),
        "hits_at_threshold": hits,
        "hit_rate": round(hit_rate, 4),
        "average_iou": round(avg_iou, 4),
        "threshold": iou_threshold,
        "details": results
    }

def main():
    parser = argparse.ArgumentParser(description="Evaluate time-range IoU between predicted promos and gold standard.")
    parser.add_argument("--gold", default="./eval/gold.json", help="Path to gold.json")
    parser.add_argument("--pred", default="./out/promos.json", help="Path to promos.json")
    parser.add_argument("--threshold", type=float, default=0.5, help="IoU hit threshold (default: 0.5)")
    args = parser.parse_args()

    eval_res = evaluate_iou(args.gold, args.pred, args.threshold)

    print("====================================================")
    print("PROMO FINDER GOLD EVALUATION (TIME-RANGE IoU)")
    print("====================================================")
    print(f"Total Gold Promos Evaluated: {eval_res['gold_count']}")
    print(f"Average IoU:                {eval_res['average_iou']:.4f}")
    print(f"Hit Rate (IoU >= {eval_res['threshold']}):      {eval_res['hit_rate']*100:.1f}% ({eval_res['hits_at_threshold']}/{eval_res['gold_count']})")
    print("----------------------------------------------------")
    print(f"{'Gold Promo ID':<28} | {'Ep':<3} | {'Best Promo':<15} | {'IoU':<6} | {'Hit?'}")
    print("----------------------------------------------------")
    for d in eval_res["details"]:
        hit_str = "YES" if d["hit"] else "NO"
        print(f"{d['gold_id']:<28} | {d['episode']:<3} | {d['best_matched_promo']:<15} | {d['iou']:<6.4f} | {hit_str}")
    print("====================================================")

if __name__ == "__main__":
    main()

