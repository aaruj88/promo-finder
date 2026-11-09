import argparse
import sys
import logging
from promofinder.pipeline import PipelineRunner

def main():
    parser = argparse.ArgumentParser(
        prog="promofinder",
        description="Promo Finder: Autonomous microdrama screenplay promo clip detector"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    run_parser = subparsers.add_parser("run", help="Run promo discovery pipeline")
    run_parser.add_argument("--input", default="./data", help="Path to microdrama data directory")
    run_parser.add_argument("--out", default="./out", help="Path to output directory")
    run_parser.add_argument("--limit", type=int, default=None, help="Limit number of episodes to process")
    run_parser.add_argument("--config", default="./config.yaml", help="Path to config.yaml")
    run_parser.add_argument("--model", default=None, help="Swap LLM model (e.g. claude-3-7-sonnet-20250219, gpt-4o, gemini-2.5-pro)")
    run_parser.add_argument("--provider", default=None, choices=["auto", "anthropic", "openai", "gemini", "groq", "heuristic"], help="LLM provider (default: auto)")
    run_parser.add_argument("--api-base", default=None, help="Custom API base URL (e.g. for OpenRouter, vLLM, DeepSeek)")
    run_parser.add_argument("--no-pairwise", action="store_true", help="Disable pairwise LLM comparisons (ablation)")
    run_parser.add_argument("--no-cold-viewer", action="store_true", help="Disable cold viewer test (ablation)")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    if args.command == "run":
        log_level = logging.DEBUG if args.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

        runner = PipelineRunner(
            config_path=args.config,
            model=args.model,
            provider=args.provider,
            api_base=args.api_base
        )
        runner.run(
            input_dir=args.input,
            out_dir=args.out,
            limit_episodes=args.limit,
            enable_cold_viewer=not args.no_cold_viewer,
            enable_pairwise=not args.no_pairwise
        )
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()

