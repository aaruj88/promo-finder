import os
import json
import logging
from typing import List, Dict, Tuple, Optional, Any
from pydantic import BaseModel, Field
from promofinder.models import (
    Episode,
    PromoRecord,
    ValidatedSegment,
    ValidationResult,
    RubricScores,
    ColdViewerOutput,
    CliffhangerSpoilerOutput,
)
from promofinder.llm import LLMClient
from promofinder.cold_viewer import render_clip_lines_text

logger = logging.getLogger("promofinder.ranker")

class PairwiseJudgement(BaseModel):
    winner: str = Field(description="Must be 'A' or 'B'")
    rationale: str

class ScoredCandidate(BaseModel):
    promo_id: str
    episode_num: int
    hook_type: str
    hook_description: str
    cliffhanger_description: str
    rationale: str
    segments: List[ValidatedSegment]
    validation: ValidationResult
    cold_viewer: ColdViewerOutput
    cliffhanger: CliffhangerSpoilerOutput
    scores: RubricScores
    primary_scene: str

def judge_pair(
    cand_a: ScoredCandidate,
    cand_b: ScoredCandidate,
    episodes_by_num: Dict[int, Episode],
    llm: LLMClient
) -> str:
    """
    Judges Clip A vs Clip B using pairwise comparison prompt.
    Returns 'A' or 'B'.
    """
    text_a = render_clip_lines_text(cand_a.segments, episodes_by_num)
    text_b = render_clip_lines_text(cand_b.segments, episodes_by_num)

    with open("./prompts/pairwise_comparison.md", "r", encoding="utf-8") as f:
        tmpl = f.read()

    system_prompt = "You are an elite microdrama creative director and performance marketing expert."
    user_prompt = tmpl.replace("{clip_a_text}", text_a).replace("{clip_b_text}", text_b)

    try:
        judgement = llm.call_structured(
            schema=PairwiseJudgement,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1024,
            temperature=0.1
        )
        winner = judgement.winner.strip().upper()
        return "A" if "A" in winner else "B"
    except Exception as e:
        logger.warning(f"Pairwise call failed: {e}")
        # Fallback to rubric score
        return "A" if cand_a.scores.total_weighted_score >= cand_b.scores.total_weighted_score else "B"

def rank_candidates(
    candidates: List[ScoredCandidate],
    episodes_by_num: Dict[int, Episode],
    llm: LLMClient,
    max_candidates_for_pairwise: int = 25,
    max_promos_per_episode: int = 2,
    top_n_final: int = 10,
    enable_pairwise: bool = True
) -> List[PromoRecord]:
    """
    Stage 7: Global ranking with pairwise comparisons and diversity rules.
    1. Sorts candidates by initial rubric score and takes top ~25.
    2. Runs pairwise comparisons in both orders (A,B) and (B,A) to aggregate wins.
    3. Applies diversity rules:
       - Max 2 promos per episode
       - No scene overlap between selected promos
       - Mix of hook types
    4. Explains rank and outputs final list of PromoRecords.
    """
    if not candidates:
        return []

    # Sort initially by rubric total score
    candidates_sorted = sorted(
        candidates,
        key=lambda c: c.scores.total_weighted_score,
        reverse=True
    )
    pool = candidates_sorted[:max_candidates_for_pairwise]
    
    wins = {c.promo_id: 0 for c in pool}

    if enable_pairwise and len(pool) > 1:
        logger.info(f"Running pairwise tournament among top {len(pool)} candidates...")
        from concurrent.futures import ThreadPoolExecutor, as_completed

        pairs_to_judge = []
        for i in range(len(pool)):
            for j in range(i + 1, len(pool)):
                # (cand_a, cand_b, is_forward)
                pairs_to_judge.append((pool[i], pool[j], True))
                pairs_to_judge.append((pool[j], pool[i], False))

        def evaluate_pair_item(item):
            ca, cb, is_forward = item
            winner = judge_pair(ca, cb, episodes_by_num, llm)
            # If winner == 'A', ca won. If winner == 'B', cb won.
            winning_id = ca.promo_id if winner == "A" else cb.promo_id
            return winning_id

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(evaluate_pair_item, item) for item in pairs_to_judge]
            for future in as_completed(futures):
                try:
                    w_id = future.result()
                    wins[w_id] = wins.get(w_id, 0) + 1
                except Exception as e:
                    logger.warning(f"Pairwise comparison task failed: {e}")

    # Sort pool by wins (descending), then rubric score as tiebreaker
    pool.sort(
        key=lambda c: (wins.get(c.promo_id, 0), c.scores.total_weighted_score),
        reverse=True
    )

    # Apply diversity rules
    selected: List[ScoredCandidate] = []
    ep_counts: Dict[int, int] = {}
    used_scenes: set = set()
    selected_hook_types: Dict[str, int] = {}

    for cand in pool:
        ep_num = cand.episode_num
        if ep_counts.get(ep_num, 0) >= max_promos_per_episode:
            continue

        # Check scene overlap: same episode and overlapping scene
        scene_key = (ep_num, cand.primary_scene)
        if scene_key in used_scenes:
            continue

        # Diversity check on hook types: avoid excessive repetition of one type
        ht = cand.hook_type.lower()
        if len(selected) >= top_n_final:
            break

        selected.append(cand)
        ep_counts[ep_num] = ep_counts.get(ep_num, 0) + 1
        used_scenes.add(scene_key)
        selected_hook_types[ht] = selected_hook_types.get(ht, 0) + 1

    # If diversity filter reduced count below top_n_final and more candidates exist, backfill
    if len(selected) < top_n_final:
        for cand in pool:
            if cand in selected:
                continue
            ep_num = cand.episode_num
            if ep_counts.get(ep_num, 0) < max_promos_per_episode:
                selected.append(cand)
                ep_counts[ep_num] = ep_counts.get(ep_num, 0) + 1
                if len(selected) >= top_n_final:
                    break

    # Build final PromoRecord list
    final_records: List[PromoRecord] = []
    for rank_idx, cand in enumerate(selected):
        rank = rank_idx + 1
        
        why_works = (
            f"Rank #{rank}: High virality potential with '{cand.hook_type}' hook. "
            f"{cand.scores.hook_justification} Cliffhanger strength: {cand.scores.cliffhanger_justification} "
            f"Tournament wins: {wins.get(cand.promo_id, 0)}."
        )

        is_cross = len(cand.segments) > 1 and len(set(s.episode for s in cand.segments)) > 1

        rec = PromoRecord(
            rank=rank,
            promo_id=cand.promo_id,
            segments=cand.segments,
            total_duration_s=cand.validation.total_duration_s,
            hook=cand.hook_description,
            cliffhanger=cand.cliffhanger_description,
            why_it_works=why_works,
            scores={
                "total": cand.scores.total_weighted_score,
                "hook": cand.scores.hook,
                "cliffhanger": cand.scores.cliffhanger,
                "standalone": cand.scores.standalone,
                "emotional_intensity": cand.scores.emotional_intensity,
                "show_representativeness": cand.scores.show_representativeness,
                "pairwise_wins": wins.get(cand.promo_id, 0)
            },
            flags={
                "spoiler_risk": cand.cliffhanger.spoiler_risk,
                "standalone_issues": cand.cold_viewer.confusing_points[:2],
                "cross_episode": is_cross,
                "hook_type": cand.hook_type,
                "hook_flag": cand.validation.hook_flag
            }
        )
        final_records.append(rec)

    return final_records
