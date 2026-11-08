import os
import json
import logging
import yaml
from typing import List, Dict, Optional, Any
from promofinder.models import (
    Episode,
    ValidatedSegment,
    ValidationResult,
    ColdViewerOutput,
    CliffhangerSpoilerOutput,
    RubricScores,
)
from promofinder.llm import LLMClient
from promofinder.cold_viewer import render_clip_lines_text

logger = logging.getLogger("promofinder.scorer")

def load_config_weights(config_path: str = "./config.yaml") -> Dict[str, float]:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            return cfg.get("scoring_weights", {
                "hook": 30.0,
                "cliffhanger": 30.0,
                "standalone": 20.0,
                "emotional_intensity": 10.0,
                "show_representativeness": 10.0
            })
    except Exception as e:
        logger.warning(f"Could not load config.yaml, using default weights: {e}")
        return {
            "hook": 30.0,
            "cliffhanger": 30.0,
            "standalone": 20.0,
            "emotional_intensity": 10.0,
            "show_representativeness": 10.0
        }

def score_candidate_promo(
    segments: List[ValidatedSegment],
    val_res: ValidationResult,
    cold_viewer: ColdViewerOutput,
    cliff_spoiler: CliffhangerSpoilerOutput,
    episodes_by_num: Dict[int, Episode],
    llm: LLMClient,
    config_path: str = "./config.yaml"
) -> RubricScores:
    """
    Stage 6: Rubric scoring.
    Scores:
    - hook (0-30)
    - cliffhanger (0-30)
    - standalone (0-20)
    - emotional intensity (0-10)
    - show representativeness (0-10)
    Each with exactly one-sentence justification.
    """
    weights = load_config_weights(config_path)
    clip_text = render_clip_lines_text(segments, episodes_by_num)

    with open("./prompts/rubric_scoring.md", "r", encoding="utf-8") as f:
        system_prompt = f.read()

    user_prompt = (
        f"PROPOSED PROMO CLIP:\n{clip_text}\n\n"
        f"TOTAL DURATION: {val_res.total_duration_s:.1f}s\n"
        f"FIRST 3-SECOND EVENTS:\n{val_res.hook_events_0_to_3s}\n"
        f"HOOK FLAG: {val_res.hook_flag}\n\n"
        f"COLD VIEWER ANALYSIS:\n"
        f"- Perceived Characters: {cold_viewer.characters}\n"
        f"- Perceived Situation: {cold_viewer.situation}\n"
        f"- Confusions: {cold_viewer.confusing_points}\n"
        f"- Standalone Rating: {cold_viewer.standalone_score}/5\n\n"
        f"CLIFFHANGER & SPOILER ANALYSIS:\n"
        f"- Cliffhanger Analysis: {cliff_spoiler.cliffhanger_analysis}\n"
        f"- Is Unresolved: {cliff_spoiler.is_unresolved}\n"
        f"- Spoiler Risk: {cliff_spoiler.spoiler_risk}\n\n"
        "Evaluate and score this promo clip across all 5 dimensions. Provide exactly one sentence justification for each."
    )

    try:
        scores = llm.call_structured(
            schema=RubricScores,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.2
        )
        # Ensure clamp to allowed bounds
        scores.hook = max(0.0, min(float(weights.get("hook", 30)), scores.hook))
        scores.cliffhanger = max(0.0, min(float(weights.get("cliffhanger", 30)), scores.cliffhanger))
        scores.standalone = max(0.0, min(float(weights.get("standalone", 20)), scores.standalone))
        scores.emotional_intensity = max(0.0, min(float(weights.get("emotional_intensity", 10)), scores.emotional_intensity))
        scores.show_representativeness = max(0.0, min(float(weights.get("show_representativeness", 10)), scores.show_representativeness))
        scores.total_weighted_score = round(
            scores.hook + scores.cliffhanger + scores.standalone + scores.emotional_intensity + scores.show_representativeness,
            2
        )
        return scores
    except Exception as e:
        logger.error(f"Rubric scoring failed: {e}")
        return RubricScores(
            hook=15.0,
            hook_justification="Fallback score due to scoring error.",
            cliffhanger=15.0,
            cliffhanger_justification="Fallback score due to scoring error.",
            standalone=10.0,
            standalone_justification="Fallback score due to scoring error.",
            emotional_intensity=5.0,
            emotional_intensity_justification="Fallback score due to scoring error.",
            show_representativeness=5.0,
            show_representativeness_justification="Fallback score due to scoring error.",
            total_weighted_score=50.0
        )

