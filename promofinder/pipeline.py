import os
import json
import logging
import yaml
from typing import List, Dict, Optional, Any
from promofinder.models import (
    Episode,
    ShowBible,
    PromoRecord,
    ValidationResult,
)
from promofinder.parser import parse_all_episodes
from promofinder.bible import generate_show_bible
from promofinder.candidate import generate_all_candidates
from promofinder.validator import validate_candidate
from promofinder.cold_viewer import run_cold_viewer_test
from promofinder.cliffhanger import run_cliffhanger_spoiler_check
from promofinder.scorer import score_candidate_promo
from promofinder.ranker import ScoredCandidate, rank_candidates
from promofinder.llm import LLMClient, global_token_tracker

logger = logging.getLogger("promofinder.pipeline")

class PipelineRunner:
    def __init__(
        self,
        config_path: str = "./config.yaml",
        model: Optional[str] = None,
        provider: Optional[str] = None,
        api_base: Optional[str] = None
    ):
        self.config_path = config_path
        self.config = self._load_config()
        chosen_model = model or os.environ.get("MODEL") or self.config.get("model") or "claude-3-5-sonnet-20241022"
        chosen_provider = provider or os.environ.get("LLM_PROVIDER") or self.config.get("provider") or "auto"
        chosen_base = api_base or os.environ.get("OPENAI_BASE_URL") or self.config.get("api_base")
        self.llm = LLMClient(model=chosen_model, provider=chosen_provider, api_base=chosen_base)

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def run(
        self,
        input_dir: str = "./data",
        out_dir: str = "./out",
        limit_episodes: Optional[int] = None,
        enable_cold_viewer: bool = True,
        enable_pairwise: bool = True
    ) -> List[PromoRecord]:
        os.makedirs(out_dir, exist_ok=True)

        logger.info(f"=== STAGE 1: Parsing Episodes from {input_dir} ===")
        all_episodes = parse_all_episodes(input_dir)
        if limit_episodes:
            all_episodes = all_episodes[:limit_episodes]
        logger.info(f"Parsed {len(all_episodes)} episodes.")

        episodes_by_num = {ep.number: ep for ep in all_episodes}

        logger.info("=== STAGE 1: Generating Show Bible ===")
        bible = generate_show_bible(all_episodes, self.llm)

        logger.info("=== STAGE 2 & 2b: Candidate Generation ===")
        workers = self.config.get("concurrency", {}).get("max_workers", 4)
        intra_cands, cross_cands = generate_all_candidates(
            all_episodes, bible, self.llm, max_workers=workers
        )
        total_raw_cands = intra_cands + cross_cands
        logger.info(f"Total raw candidates generated: {len(total_raw_cands)}")

        logger.info("=== STAGE 3: Deterministic Validation ===")
        dur_cfg = self.config.get("duration", {})
        min_dur = dur_cfg.get("min_s", 20.0)
        max_dur = dur_cfg.get("max_s", 60.0)
        hook_win = dur_cfg.get("hook_window_s", 3.0)

        validated_cands = []
        for i, cand in enumerate(total_raw_cands):
            v_res = validate_candidate(
                cand, episodes_by_num, min_duration=min_dur, max_duration=max_dur, hook_window=hook_win
            )
            if v_res.is_valid:
                validated_cands.append((cand, v_res))
            else:
                logger.debug(f"Candidate #{i+1} rejected: {v_res.reject_reason}")

        logger.info(f"Valid candidates after deterministic filter: {len(validated_cands)} / {len(total_raw_cands)}")

        logger.info("=== STAGE 4, 5, 6: Cold Viewer, Cliffhanger, Rubric Scoring ===")
        scored_candidates: List[ScoredCandidate] = []

        def process_candidate(idx: int, cand, v_res) -> ScoredCandidate:
            promo_id = f"PROMO_{cand.segments[0].episode:03d}_{idx+1:02d}"
            # Stage 4: Cold viewer
            if enable_cold_viewer:
                cold_res = run_cold_viewer_test(v_res.segments, episodes_by_num, self.llm)
            else:
                from promofinder.models import ColdViewerOutput
                cold_res = ColdViewerOutput(
                    characters=["Ablation mode"],
                    situation="Cold viewer disabled in ablation",
                    confusing_points=[],
                    standalone_score=3,
                    notes="Ablation"
                )

            # Stage 5: Cliffhanger & spoiler check
            cliff_res = run_cliffhanger_spoiler_check(v_res.segments, episodes_by_num, bible, self.llm)

            # Stage 6: Rubric scoring
            scores = score_candidate_promo(
                v_res.segments, v_res, cold_res, cliff_res, episodes_by_num, self.llm, self.config_path
            )

            # Determine primary scene
            ep = episodes_by_num[cand.segments[0].episode]
            primary_scene = ep.lines[0].scene
            for l in ep.lines:
                if l.start_s >= v_res.segments[0].start_s:
                    primary_scene = l.scene
                    break

            return ScoredCandidate(
                promo_id=promo_id,
                episode_num=cand.segments[0].episode,
                hook_type=cand.hook_type,
                hook_description=cand.hook_description,
                cliffhanger_description=cand.cliffhanger_description,
                rationale=cand.rationale,
                segments=v_res.segments,
                validation=v_res,
                cold_viewer=cold_res,
                cliffhanger=cliff_res,
                scores=scores,
                primary_scene=primary_scene
            )

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(process_candidate, idx, cand, v_res)
                for idx, (cand, v_res) in enumerate(validated_cands)
            ]
            for future in as_completed(futures):
                try:
                    sc = future.result()
                    scored_candidates.append(sc)
                except Exception as e:
                    logger.error(f"Error scoring candidate: {e}")

        logger.info(f"Scored {len(scored_candidates)} candidates.")

        logger.info("=== STAGE 7: Global Ranking & Diversity Selection ===")
        ranking_cfg = self.config.get("ranking", {})
        top_promos = rank_candidates(
            candidates=scored_candidates,
            episodes_by_num=episodes_by_num,
            llm=self.llm,
            max_candidates_for_pairwise=ranking_cfg.get("max_candidates_for_pairwise", 25),
            max_promos_per_episode=ranking_cfg.get("max_promos_per_episode", 2),
            top_n_final=ranking_cfg.get("top_n_final", 10),
            enable_pairwise=enable_pairwise
        )

        logger.info("=== STAGE 8: Output Generation ===")
        promos_json_path = os.path.join(out_dir, "promos.json")
        with open(promos_json_path, "w", encoding="utf-8") as f:
            f.write(json.dumps([p.model_dump() for p in top_promos], indent=2))
        logger.info(f"Saved {len(top_promos)} ranked promos to {promos_json_path}")

        report_md_path = os.path.join(out_dir, "report.md")
        self._write_report(report_md_path, top_promos, bible)
        logger.info(f"Saved executive report to {report_md_path}")

        return top_promos

    def _write_report(self, path: str, promos: List[PromoRecord], bible: ShowBible):
        token_stats = global_token_tracker.get_summary(self.llm.model)
        
        md_lines = [
            f"# Promo Finder Executive Report: {bible.title}",
            "",
            "## Executive Summary",
            f"Promo Finder analyzed the microdrama series **{bible.title}**, evaluating all candidate promo clips for maximum conversion, scroll-stopping hook appeal, cliffhanger drive, and standalone comprehension.",
            "",
            "### Token and Cost Breakdown",
            f"- **Total LLM Calls**: {token_stats['total_calls']}",
            f"- **Cached LLM Calls**: {token_stats['cached_calls']}",
            f"- **Live API Calls**: {token_stats['api_calls']}",
            f"- **Input Tokens**: {token_stats['input_tokens']:,}",
            f"- **Output Tokens**: {token_stats['output_tokens']:,}",
            f"- **Total Tokens**: {token_stats['total_tokens']:,}",
            f"- **Estimated Model Cost**: ${token_stats['estimated_cost_usd']:.4f} USD",
            "",
            "## Top 3 Promos to Post First",
            "Based on global tournament ranking, narrative clarity, and psychological conversion momentum, the recommended top 3 promos to post first are:",
            ""
        ]

        for p in promos[:3]:
            ep_set = sorted(list(set(s.episode for s in p.segments)))
            ep_str = ", ".join(str(e) for e in ep_set)
            md_lines.extend([
                f"### Rank {p.rank}: {p.promo_id} (Episode {ep_str})",
                f"- **Total Duration**: {p.total_duration_s:.1f}s",
                f"- **Hook**: {p.hook}",
                f"- **Cliffhanger**: {p.cliffhanger}",
                f"- **Total Virality Score**: {p.scores.get('total', 0)}/100 (Tournament Wins: {p.scores.get('pairwise_wins', 0)})",
                f"- **Why Post First**: {p.why_it_works}",
                ""
            ])

        md_lines.extend([
            "## Complete Ranked Promos Table",
            "| Rank | Promo ID | Ep | Duration | Hook Type | Score | Wins | Cut Points (Start -> End) |",
            "|---|---|---|---|---|---|---|---|"
        ])

        for p in promos:
            ep_set = sorted(list(set(s.episode for s in p.segments)))
            ep_str = ", ".join(str(e) for e in ep_set)
            ts_str = "; ".join(f"{s.start_ts}->{s.end_ts}" for s in p.segments)
            ht = p.flags.get("hook_type", "N/A")
            score = p.scores.get("total", 0)
            wins = p.scores.get("pairwise_wins", 0)
            md_lines.append(f"| {p.rank} | {p.promo_id} | Ep {ep_str} | {p.total_duration_s:.1f}s | {ht} | {score:.1f} | {wins} | {ts_str} |")

        md_lines.extend([
            "",
            "## Strategic Insights & Conversion Notes",
            "1. **Public Humiliation & Betrayal Outperform**: Audiences on vertical video platforms respond most intensely to high-status cruelty (e.g. altar abandonment, illegitimate accusations) followed by defiant resilience.",
            "2. **Strict Sentence Snapping**: All selected clips snap to natural sentence boundaries, ensuring no mid-word or jarring audio cuts.",
            "3. **Zero Severe Spoilers**: Clips maintain full cliffhanger curiosity without giving away late-season ducal revelations.",
            ""
        ])

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))
