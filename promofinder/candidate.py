import os
import json
import logging
from promofinder.prompt_loader import load_prompt_file
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple, Dict
from promofinder.models import (
    Episode,
    ShowBible,
    CandidateProposal,
    CandidateGenerationOutput,
    SegmentSpec,
)
from promofinder.llm import LLMClient

logger = logging.getLogger("promofinder.candidate")

def render_transcript_with_line_ids(episode: Episode, start_time: Optional[float] = None, end_time: Optional[float] = None) -> str:
    """
    Renders lines with line_ids and timestamps:
    [L12 00:11.30-00:13.10] MATRIARCH (Cold): "You should turn around, Juliana."
    """
    lines_rendered = []
    current_scene = None
    
    for line in episode.lines:
        if start_time is not None and line.end_s < start_time:
            continue
        if end_time is not None and line.start_s > end_time:
            continue
            
        if line.scene != current_scene:
            current_scene = line.scene
            lines_rendered.append(f"\n--- {current_scene} ---")
            
        lines_rendered.append(line.format_for_prompt())
        
    return "\n".join(lines_rendered)

def generate_candidates_for_episode(
    episode: Episode,
    bible: ShowBible,
    llm: LLMClient,
    cache_dir: str = "./.cache/candidates"
) -> List[CandidateProposal]:
    """
    Stage 2: Generates 3-6 intra-episode candidate promos for a single episode.
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"ep_{episode.number:03d}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [CandidateProposal.model_validate(c) for c in data]
        except Exception as e:
            logger.warning(f"Error loading cached candidates for ep {episode.number}: {e}")

    transcript = render_transcript_with_line_ids(episode)
    
    system_prompt = load_prompt_file("prompts/candidate_generation.md")

    user_prompt = (
        f"SHOW PREMISE:\n{bible.premise}\n\n"
        f"EPISODE {episode.number} LOGLINE:\n{episode.logline}\n\n"
        f"CONTINUITY NOTES:\n{episode.continuity}\n\n"
        f"EPISODE TRANSCRIPT:\n{transcript}\n\n"
        f"Select 3 to 6 high-converting promo candidates for Episode {episode.number}. "
        "Remember: Output line IDs only (e.g. L05 to L25). Do NOT output timestamps. "
        "Target duration is 20-60 seconds."
    )

    try:
        output = llm.call_structured(
            schema=CandidateGenerationOutput,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=8192,
            temperature=0.3
        )
        candidates = output.candidates
    except Exception as e:
        logger.error(f"Failed to generate candidates for Ep {episode.number}: {e}")
        candidates = []

    # Cache results
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in candidates], f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to write candidate cache for ep {episode.number}: {e}")

    return candidates

def generate_cross_episode_candidate(
    ep_a: Episode,
    ep_b: Episode,
    bible: ShowBible,
    llm: LLMClient,
    tail_s: float = 40.0,
    head_s: float = 40.0,
    cache_dir: str = "./.cache/cross_candidates"
) -> Optional[CandidateProposal]:
    """
    Stage 2b: Evaluates cross-episode candidate for consecutive episodes (ep_a, ep_b).
    Takes last ~40s of ep_a and first ~40s of ep_b.
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"cross_{ep_a.number:03d}_{ep_b.number:03d}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data is None:
                return None
            return CandidateProposal.model_validate(data)
        except Exception as e:
            logger.warning(f"Error loading cached cross-episode candidate: {e}")

    ep_a_tail_start = max(0.0, ep_a.duration_s - tail_s)
    transcript_a = render_transcript_with_line_ids(ep_a, start_time=ep_a_tail_start)
    transcript_b = render_transcript_with_line_ids(ep_b, end_time=head_s)

    tmpl = load_prompt_file("prompts/cross_episode.md")

    system_prompt = tmpl.replace("{ep_a}", str(ep_a.number)).replace("{ep_b}", str(ep_b.number))

    user_prompt = (
        f"SHOW PREMISE:\n{bible.premise}\n\n"
        f"EPISODE {ep_a.number} (Final ~{tail_s}s):\n{transcript_a}\n\n"
        f"EPISODE {ep_b.number} (Opening ~{head_s}s):\n{transcript_b}\n\n"
        f"Determine if a joined candidate across Episode {ep_a.number} and {ep_b.number} "
        "is dramatically superior to any standalone clip. "
        "Target combined duration is 20-60s. Output line IDs only."
    )

    try:
        output = llm.call_structured(
            schema=CandidateGenerationOutput,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.2
        )
        cand = output.candidates[0] if output.candidates else None
    except Exception as e:
        logger.error(f"Failed cross-episode check for {ep_a.number}-{ep_b.number}: {e}")
        cand = None

    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cand.model_dump() if cand else None, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to cache cross-episode candidate: {e}")

    return cand

def generate_all_candidates(
    episodes: List[Episode],
    bible: ShowBible,
    llm: LLMClient,
    max_workers: int = 4
) -> Tuple[List[CandidateProposal], List[CandidateProposal]]:
    """
    Runs Stage 2 (intra-episode) and Stage 2b (cross-episode) with concurrency.
    """
    intra_candidates: List[CandidateProposal] = []
    cross_candidates: List[CandidateProposal] = []

    logger.info(f"Generating intra-episode candidates for {len(episodes)} episodes (concurrency={max_workers})...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(generate_candidates_for_episode, ep, bible, llm): ep.number
            for ep in episodes
        }
        for future in as_completed(futures):
            ep_num = futures[future]
            try:
                cands = future.result()
                intra_candidates.extend(cands)
            except Exception as e:
                logger.error(f"Episode {ep_num} candidate generation failed: {e}")

    logger.info(f"Generated {len(intra_candidates)} intra-episode candidates.")

    # Stage 2b: Cross-episode candidates for consecutive pairs
    consecutive_pairs = [(episodes[i], episodes[i+1]) for i in range(len(episodes) - 1)]
    logger.info(f"Evaluating {len(consecutive_pairs)} consecutive episode pairs for cross-episode candidates...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(generate_cross_episode_candidate, pair[0], pair[1], bible, llm): (pair[0].number, pair[1].number)
            for pair in consecutive_pairs
        }
        for future in as_completed(futures):
            pair_nums = futures[future]
            try:
                cand = future.result()
                if cand:
                    cross_candidates.append(cand)
            except Exception as e:
                logger.error(f"Cross-episode {pair_nums} failed: {e}")

    logger.info(f"Generated {len(cross_candidates)} cross-episode candidates.")
    return intra_candidates, cross_candidates
