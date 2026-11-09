import os
import json
import logging
from typing import List, Dict, Optional
from promofinder.models import (
    Episode,
    ValidatedSegment,
    ShowBible,
    CliffhangerSpoilerOutput,
)
from promofinder.llm import LLMClient
from promofinder.cold_viewer import render_clip_lines_text
from promofinder.prompt_loader import load_prompt_file

logger = logging.getLogger("promofinder.cliffhanger")

def get_next_screenplay_lines(
    last_seg: ValidatedSegment,
    episodes_by_num: Dict[int, Episode],
    num_lines: int = 15
) -> str:
    """
    Retrieves the next ~15 lines from the screenplay immediately following the cut point.
    """
    ep = episodes_by_num.get(last_seg.episode)
    if not ep:
        return ""
    
    # Lines with start_s >= last_seg.end_s
    subsequent = [l for l in ep.lines if l.start_s >= last_seg.end_s]
    if not subsequent and last_seg.episode + 1 in episodes_by_num:
        # Check start of next episode if at the very end of episode
        next_ep = episodes_by_num[last_seg.episode + 1]
        subsequent = next_ep.lines[:num_lines]
    else:
        subsequent = subsequent[:num_lines]

    rendered = []
    for l in subsequent:
        rendered.append(l.format_for_prompt())
    return "\n".join(rendered)

def run_cliffhanger_spoiler_check(
    segments: List[ValidatedSegment],
    episodes_by_num: Dict[int, Episode],
    bible: ShowBible,
    llm: LLMClient
) -> CliffhangerSpoilerOutput:
    """
    Stage 5: Cliffhanger and spoiler risk analysis.
    Evaluates clip text + next ~15 lines after cut + bible's major reveals.
    """
    clip_text = render_clip_lines_text(segments, episodes_by_num)
    next_lines = get_next_screenplay_lines(segments[-1], episodes_by_num, num_lines=15)
    
    # Format major reveals
    reveals_summary = []
    for rev in bible.major_reveals:
        reveals_summary.append(f"- Episode {rev.episode}: {rev.reveal} (Major Spoiler: {rev.is_spoiler})")
    reveals_text = "\n".join(reveals_summary)

    system_prompt = load_prompt_file("prompts/cliffhanger_spoiler.md")

    user_prompt = (
        f"PROPOSED PROMO CLIP:\n{clip_text}\n\n"
        f"NEXT 15 SCREENPLAY LINES AFTER CUT:\n{next_lines}\n\n"
        f"SHOW BIBLE MAJOR REVEALS:\n{reveals_text}\n\n"
        "Analyze whether the cut is genuinely unresolved and check for spoiler risks."
    )

    try:
        output = llm.call_structured(
            schema=CliffhangerSpoilerOutput,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.2
        )
        return output
    except Exception as e:
        logger.error(f"Cliffhanger/spoiler check failed: {e}")
        return CliffhangerSpoilerOutput(
            unresolved_cliffhanger_score=0.5,
            cliffhanger_analysis=f"Evaluation failed: {e}",
            is_unresolved=True,
            spoiler_risk="none",
            spoiler_analysis="Analysis unavailable"
        )

