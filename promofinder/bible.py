import os
import json
import logging
from typing import List, Optional
from promofinder.models import ShowBible, Episode
from promofinder.llm import LLMClient

logger = logging.getLogger("promofinder.bible")

def load_prompt_template(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def generate_show_bible(
    episodes: List[Episode],
    llm: Optional[LLMClient] = None,
    cache_path: str = "./.cache/show_bible.json"
) -> ShowBible:
    """
    Stage 1: Generates or loads the Show Bible covering all 50 episodes.
    Uses loglines + continuity notes to identify characters, relationships, premise,
    seasonal arc, and major reveals with episode numbers.
    """
    # Check multiple candidate cache locations
    candidate_paths = [
        cache_path,
        "./.cache/show_bible.json",
        "./submission/raw_outputs/show_bible.json",
        os.path.join(os.path.dirname(__file__), "..", "submission", "raw_outputs", "show_bible.json")
    ]
    for cp in candidate_paths:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Loaded Show Bible from cache: {cp}")
                return ShowBible.model_validate(data)
            except Exception as e:
                logger.warning(f"Failed to load cached Show Bible from {cp}: {e}")

    llm_client = llm or LLMClient()
    prompt_path = "./prompts/show_bible.md"
    if not os.path.exists(prompt_path):
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "show_bible.md")
    prompt_template = load_prompt_template(prompt_path)

    # Compile loglines & continuity notes across all 50 episodes
    episodes_summary = []
    for ep in episodes:
        episodes_summary.append(
            f"Episode {ep.number}:\n"
            f"LOGLINE: {ep.logline}\n"
            f"CONTINUITY NOTES: {ep.continuity}\n"
        )
    episodes_text = "\n".join(episodes_summary)

    user_prompt = (
        "Here are the loglines and continuity notes for all 50 episodes of the microdrama:\n\n"
        f"{episodes_text}\n\n"
        "Extract the complete Show Bible matching the schema."
    )

    logger.info("Calling LLM to generate Show Bible for 50 episodes...")
    bible = llm_client.call_structured(
        schema=ShowBible,
        system_prompt=prompt_template,
        user_prompt=user_prompt,
        max_tokens=8192,
        temperature=0.1
    )

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(bible.model_dump_json(indent=2))
    logger.info(f"Show Bible generated and saved to {cache_path}")

    return bible
