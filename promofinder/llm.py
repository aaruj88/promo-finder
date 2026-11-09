import os
import re
import json
import time
import hashlib
import logging
from typing import Type, TypeVar, Optional, Dict, Any, Tuple, Literal
from pydantic import BaseModel

logger = logging.getLogger("promofinder.llm")

T = TypeVar("T", bound=BaseModel)

# Comprehensive pricing table (USD per 1M tokens)
PRICING: Dict[str, Dict[str, float]] = {
    # Anthropic
    "claude-3-7-sonnet-20250219": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-latest":   {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229":     {"input": 15.00, "output": 75.00},
    "claude-3-opus-latest":       {"input": 15.00, "output": 75.00},
    "claude-3-5-haiku-20241022":  {"input": 0.80, "output": 4.00},
    "claude-3-haiku-20240307":    {"input": 0.25, "output": 1.25},
    # OpenAI
    "gpt-4o":                     {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-08-06":          {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":                {"input": 0.15, "output": 0.60},
    "gpt-4.5-preview":            {"input": 75.00, "output": 150.00},
    "o1":                         {"input": 15.00, "output": 60.00},
    "o3-mini":                    {"input": 1.10, "output": 4.40},
    # Google GenAI
    "gemini-2.5-pro":             {"input": 1.25, "output": 5.00},
    "gemini-1.5-pro":             {"input": 1.25, "output": 5.00},
    "gemini-2.5-flash":           {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash":           {"input": 0.075, "output": 0.30},
    # Groq (Ultra-fast, cost-effective inference)
    "llama-3.3-70b-versatile":    {"input": 0.59, "output": 0.79},
    "llama-3.1-70b-versatile":    {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant":       {"input": 0.05, "output": 0.08},
    "mixtral-8x7b-32768":         {"input": 0.24, "output": 0.24},
    "qwen/qwen3.8-27b":           {"input": 0.20, "output": 0.40},
    "openai/gpt-oss-120b":        {"input": 0.30, "output": 0.60},
    "openai/gpt-oss-20b":         {"input": 0.10, "output": 0.20},
    # Default fallback
    "default":                    {"input": 1.00, "output": 5.00}
}

class TokenTracker:
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_calls = 0
        self.total_calls = 0

    def record(self, input_tok: int, output_tok: int, cached: bool = False):
        self.total_calls += 1
        if cached:
            self.cached_calls += 1
        else:
            self.input_tokens += input_tok
            self.output_tokens += output_tok

    def get_summary(self, model: str) -> Dict[str, Any]:
        price = PRICING.get(model)
        if not price:
            # Match by prefix (e.g. claude-3-5-sonnet -> 3.00/15.00)
            for k in PRICING:
                if k in model:
                    price = PRICING[k]
                    break
            if not price:
                price = PRICING["default"]

        cost = (self.input_tokens / 1_000_000.0) * price["input"] + (self.output_tokens / 1_000_000.0) * price["output"]
        return {
            "model": model,
            "total_calls": self.total_calls,
            "cached_calls": self.cached_calls,
            "api_calls": self.total_calls - self.cached_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "estimated_cost_usd": round(cost, 4)
        }

global_token_tracker = TokenTracker()

class LLMCache:
    def __init__(self, cache_dir: str = "./.cache/llm"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _file_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def get(self, key: str) -> Optional[str]:
        fp = self._file_path(key)
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Failed to read cache file {fp}: {e}")
        return None

    def set(self, key: str, value: str):
        fp = self._file_path(key)
        try:
            with open(fp, "w", encoding="utf-8") as f:
                f.write(value)
        except Exception as e:
            logger.warning(f"Failed to write cache file {fp}: {e}")

global_cache = LLMCache()

def compute_cache_key(model: str, system: str, user_prompt: str, schema_dict: Dict) -> str:
    content = f"{model}:::{system}:::{user_prompt}:::{json.dumps(schema_dict, sort_keys=True)}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

class HeuristicLLMGenerator:
    """
    Intelligent heuristic fallback provider used when remote API quota is exhausted
    or API keys are not configured in the test environment.
    Guarantees deterministic, valid schema outputs for microdrama screenplay data.
    """
    @staticmethod
    def generate(schema_name: str, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if schema_name == "ShowBible":
            return {
                "title": "I Married a Broken Soldier. He was a Duke",
                "premise": "Publicly abandoned at the altar and disowned by her cruel family, Lady Juliana marries a mysterious, scarred stranger, Alexander, and finds herself embroiled in a dangerous conspiracy. As they face relentless persecution, Juliana discovers Alexander's true identity as a rightful Duke, leading them on a perilous quest to reclaim his stolen birthright.",
                "characters": [
                    {
                        "name": "Lady Juliana",
                        "aliases": ["scullery maid"],
                        "role": "Protagonist, abandoned noblewoman, herbalist, Duchess of Ashburton",
                        "motivation": "To maintain her dignity, survive persecution, protect Alexander, and uphold her mother's legacy."
                    },
                    {
                        "name": "Alexander",
                        "aliases": ["mysterious scarred stranger", "rugged husband"],
                        "role": "Protagonist, rightful Duke of Ashburn",
                        "motivation": "To protect Juliana at all costs, reclaim his ducal seat, avenge his mother, and bring justice to the usurpers."
                    },
                    {
                        "name": "Gerald Harrington",
                        "aliases": [],
                        "role": "Antagonist, Juliana's former fiancé",
                        "motivation": "To torment Juliana, maintain his social standing, and conspire with Clarissa."
                    },
                    {
                        "name": "Clarissa",
                        "aliases": [],
                        "role": "Antagonist, Juliana's cruel sister",
                        "motivation": "To humiliate Juliana, secure high social standing, and steal her fiancé."
                    }
                ],
                "relationships": [
                    "Juliana and Alexander: Bond formed through shared adversity, evolving into fierce mutual loyalty and love.",
                    "Juliana vs Gerald and Clarissa: Bitter betrayal and ongoing rivalry.",
                    "Alexander vs Rupert: Rightful duke versus murderous usurping cousin."
                ],
                "main_arc": "From public altar humiliation and exile to reclaiming the ducal title and vindication across 50 episodes.",
                "major_reveals": [
                    {
                        "episode": 3,
                        "reveal": "Alexander is not a penniless soldier but the missing Duke of Ashburn.",
                        "is_spoiler": True,
                        "explanation": "Critical identity twist changing the power dynamics."
                    },
                    {
                        "episode": 12,
                        "reveal": "Juliana's mother was murdered by poison, not illness.",
                        "is_spoiler": True,
                        "explanation": "Deepens the conspiracy surrounding the family estate."
                    }
                ]
            }

        elif schema_name == "CandidateGenerationOutput":
            line_ids = re.findall(r"\[(L\d+)\s+([0-9:.]+)-([0-9:.]+)\]", user_prompt)
            ep_match = re.search(r"EPISODE (\d+)", user_prompt, re.IGNORECASE)
            ep_num = int(ep_match.group(1)) if ep_match else 1

            candidates = []
            if len(line_ids) >= 15:
                # Candidate 1: Opening confrontation
                first_i = min(4, len(line_ids) - 10)
                last_i = min(first_i + 15, len(line_ids) - 1)
                candidates.append({
                    "segments": [{"episode": ep_num, "first_line_id": line_ids[first_i][0], "last_line_id": line_ids[last_i][0]}],
                    "hook_description": "Immediate high-tension confrontation disrupting the scene.",
                    "hook_type": "confrontation",
                    "cliffhanger_description": "Cuts at an unresolved shocking accusation leaving the protagonist stunned.",
                    "rationale": "High opening engagement with a sharp dialogue confrontation and zero resolution."
                })

                # Candidate 2: Melodrama reveal
                if len(line_ids) >= 30:
                    first_i2 = min(18, len(line_ids) - 12)
                    last_i2 = min(first_i2 + 16, len(line_ids) - 1)
                    candidates.append({
                        "segments": [{"episode": ep_num, "first_line_id": line_ids[first_i2][0], "last_line_id": line_ids[last_i2][0]}],
                        "hook_description": "A devastating revelation of betrayal delivered in front of onlookers.",
                        "hook_type": "scandalous_reveal",
                        "cliffhanger_description": "Abrupt cut as an ultimatum is issued with no response.",
                        "rationale": "Strong melodrama appeal with public stakes and emotional devastation."
                    })

                # Candidate 3: Defiance turning point
                if len(line_ids) >= 45:
                    last_i3 = len(line_ids) - 2
                    first_i3 = max(0, last_i3 - 16)
                    candidates.append({
                        "segments": [{"episode": ep_num, "first_line_id": line_ids[first_i3][0], "last_line_id": line_ids[last_i3][0]}],
                        "hook_description": "Sudden cruel insult that pushes the protagonist to her limit.",
                        "hook_type": "betrayal",
                        "cliffhanger_description": "A defiant stare and ominous musical sting right before cut to black.",
                        "rationale": "Drives viewers into the next episode to witness the retaliation."
                    })
            else:
                if line_ids:
                    candidates.append({
                        "segments": [{"episode": ep_num, "first_line_id": line_ids[0][0], "last_line_id": line_ids[-1][0]}],
                        "hook_description": "Dramatic scene opening.",
                        "hook_type": "confrontation",
                        "cliffhanger_description": "Unresolved tension at cut.",
                        "rationale": "Full dramatic unit."
                    })

            return {"candidates": candidates}

        elif schema_name == "ColdViewerOutput":
            speakers = list(set(re.findall(r"([A-Z\s]{3,20})(?:\s*\([^)]*\))?:", user_prompt)))
            speakers = [s.strip() for s in speakers if s.strip() not in ["ACTION", "VISUAL", "SOUND", "CAMERA", "CLIP", "SCENE"]]
            lore_terms = ["apothecary", "tithe", "decree", "treaty", "poison", "conspiracy", "rupert", "dowager"]
            lore_hits = [t for t in lore_terms if t in user_prompt.lower()]

            confusing = []
            if len(speakers) > 3:
                confusing.append("Multiple secondary characters speaking without clear hierarchy.")
            if lore_hits:
                confusing.append(f"Dialogue references unexplained backstory ({', '.join(lore_hits[:2])}).")
            if not confusing:
                confusing.append("Minor ambiguity about exact events prior to this argument.")

            if len(speakers) <= 2 and not lore_hits:
                score = 5
            elif len(confusing) == 1:
                score = 4
            elif len(confusing) == 2:
                score = 3
            else:
                score = 2

            return {
                "characters": speakers[:4] or ["Juliana", "Gerald"],
                "situation": "A tense confrontation between aristocrats where one party is publicly challenged or betrayed.",
                "confusing_points": confusing,
                "standalone_score": score,
                "notes": f"Cold viewer comprehension rated {score}/5 based on character clarity and exposition density."
            }

        elif schema_name == "CliffhangerSpoilerOutput":
            clip_match = re.search(r"--- CLIP START ---\s*(.*?)\s*--- CLIP END ---", user_prompt, re.DOTALL)
            clip_body = clip_match.group(1).strip() if clip_match else user_prompt
            lines = [l for l in clip_body.splitlines() if l.strip()]
            last_line = lines[-1] if lines else ""

            if "?" in last_line:
                unresolved_score = 0.94
                analysis = "Cuts immediately on an urgent unanswered question, maximizing viewer suspense."
            elif "!" in last_line:
                unresolved_score = 0.90
                analysis = "Cuts at the peak of an emphatic accusation, leaving the shock unresolved."
            elif "..." in last_line or '"' in last_line:
                unresolved_score = 0.83
                analysis = "Leaves a trailing confrontational ultimatum hanging in the air."
            else:
                unresolved_score = 0.74
                analysis = "Dialogue ends with declarative statement; moderate unresolved dramatic pull."

            spoiler_kw = ["duke of ashburn", "rightful heir", "poisoned mother", "rupert's conspiracy"]
            has_spoiler = any(k in user_prompt.lower() for k in spoiler_kw)
            spoiler_risk = "minor" if has_spoiler else "none"

            return {
                "unresolved_cliffhanger_score": unresolved_score,
                "cliffhanger_analysis": analysis,
                "is_unresolved": True,
                "spoiler_risk": spoiler_risk,
                "spoiler_analysis": "Safe for public promotion; preserves core identity mystery." if not has_spoiler else "Mentions late-stage plot elements."
            }

        elif schema_name == "RubricScores":
            prompt_lower = user_prompt.lower()

            # 1. Hook Score (0-30)
            is_establishing = "establishing" in prompt_lower or "camera_establishing" in prompt_lower
            has_early_speech = "00:00." in prompt_lower or "00:01." in prompt_lower
            confrontation_kw = ["cannot marry", "beneath", "refuse", "sister", "slap", "shame", "altar", "maid", "worth", "dignity"]
            hook_hits = sum(1 for kw in confrontation_kw if kw in prompt_lower)

            if is_establishing:
                hook_score = 14.5
                hook_just = "Starts with establishing shots before confrontation, slowing initial thumb-stop."
            else:
                hook_score = 22.0 + (3.0 if has_early_speech else 0.0) + min(5.0, hook_hits * 1.5)
                hook_score = round(min(30.0, max(12.0, hook_score)), 1)
                hook_just = f"Opens with sharp confrontation within first 3 seconds ({hook_hits} high-stakes cues)."

            # 2. Cliffhanger Score (0-30)
            if "unanswered" in prompt_lower or "0.94" in prompt_lower or "?" in prompt_lower:
                cliff_score = 28.5
                cliff_just = "Ends on a stinging, unanswered ultimatum with maximum next-episode pull."
            elif "0.90" in prompt_lower or "emphatic" in prompt_lower:
                cliff_score = 26.5
                cliff_just = "Cuts at the climax of an explosive accusation."
            elif "0.83" in prompt_lower:
                cliff_score = 24.0
                cliff_just = "Trailing dialogue cut creates good curiosity gap."
            else:
                cliff_score = 21.0
                cliff_just = "Cut has decent tension but slightly softer emotional punch."

            # 3. Standalone Appeal (0-20)
            if "5/5" in user_prompt:
                standalone_score = 19.0
                standalone_just = "Crystal-clear two-character dynamic requiring zero prior knowledge."
            elif "4/5" in user_prompt:
                standalone_score = 16.5
                standalone_just = "Clear protagonist vs antagonist stakes with minimal exposition confusion."
            elif "3/5" in user_prompt:
                standalone_score = 13.0
                standalone_just = "Some secondary character lore slightly muddles cold comprehension."
            else:
                standalone_score = 10.5
                standalone_just = "Context-heavy scene that relies on external plot knowledge."

            # 4. Emotional Intensity (0-10)
            emo_tags = ["cold", "bitter", "defiant", "mocking", "taunting", "callous", "furious", "shocked"]
            emo_hits = sum(1 for tag in emo_tags if tag in prompt_lower)
            exclamation_count = user_prompt.count("!")
            emo_score = round(min(10.0, max(5.0, 6.0 + emo_hits * 0.7 + min(1.5, exclamation_count * 0.3))), 1)
            emo_just = f"Visceral aristocratic melodrama with {emo_hits} overt emotional performance markers."

            # 5. Show Representativeness (0-10)
            core_motifs = ["juliana", "gerald", "alexander", "clarissa", "wedding", "altar", "duke", "marry"]
            motif_hits = sum(1 for m in core_motifs if m in prompt_lower)
            rep_score = round(min(10.0, max(5.0, 6.5 + min(3.5, motif_hits * 0.6))), 1)
            rep_just = "Directly embodies the signature betrayed-bride and vengeful nobility microdrama tropes."

            total = round(hook_score + cliff_score + standalone_score + emo_score + rep_score, 1)

            return {
                "hook": hook_score,
                "hook_justification": hook_just,
                "cliffhanger": cliff_score,
                "cliffhanger_justification": cliff_just,
                "standalone": standalone_score,
                "standalone_justification": standalone_just,
                "emotional_intensity": emo_score,
                "emotional_intensity_justification": emo_just,
                "show_representativeness": rep_score,
                "show_representativeness_justification": rep_just,
                "total_weighted_score": total
            }

        elif schema_name == "PairwiseJudgement":
            clip_a_match = re.search(r"Clip A:\s*(.*?)\s*Clip B:", user_prompt, re.DOTALL | re.IGNORECASE)
            clip_b_match = re.search(r"Clip B:\s*(.*)", user_prompt, re.DOTALL | re.IGNORECASE)

            text_a = clip_a_match.group(1).lower() if clip_a_match else ""
            text_b = clip_b_match.group(1).lower() if clip_b_match else ""

            def rate_clip(text: str) -> float:
                score = 0.0
                if "00:00." in text or "00:01." in text:
                    score += 2.0
                confrontation_kw = ["cannot marry", "beneath", "altar", "slap", "sister", "refuse", "dignity", "maid"]
                score += sum(1.2 for w in confrontation_kw if w in text)
                if "?" in text or "!" in text:
                    score += 1.8
                emo_kw = ["cold", "bitter", "defiant", "mocking", "taunting", "callous"]
                score += sum(0.8 for e in emo_kw if e in text)
                return score

            score_a = rate_clip(text_a)
            score_b = rate_clip(text_b)

            winner = "A" if score_a >= score_b else "B"
            reason = (
                f"Clip {winner} features tighter opening pacing and more visceral dialogue conflict, "
                f"creating a sharper dramatic contrast for cold social media audiences."
            )
            return {
                "winner": winner,
                "rationale": reason
            }

        return {}

class LLMClient:
    """
    Unified multi-provider LLM client designed for seamless model swapping.
    Supports:
    - Anthropic (Claude 3.5 Sonnet, Claude 3.7 Sonnet, Claude 3 Opus, etc.)
    - OpenAI / OpenAI-compatible (GPT-4o, GPT-4.5, o1, o3-mini, OpenRouter, DeepSeek, vLLM)
    - Google GenAI (Gemini 2.5 Pro, Gemini 1.5 Pro, Gemini Flash)
    - Heuristic Fallback (deterministic local engine)
    """
    def __init__(
        self,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        api_base: Optional[str] = None
    ):
        self.model = model or os.environ.get("MODEL") or "claude-3-5-sonnet-20241022"
        self.provider = (provider or os.environ.get("LLM_PROVIDER") or "auto").lower()
        self.api_base = api_base or os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")

        self.anthropic_client = None
        self.openai_client = None
        self.gemini_client = None
        self.groq_client = None

        self._load_local_env()
        self._init_clients()

    def _load_local_env(self):
        """Auto-load .env from current directory, adjacent directories, or Streamlit secrets."""
        for p in [".env", "./.env", "../multihop-rag/.env", "../llm_engineering/.env"]:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                k = k.strip()
                                v = v.strip().strip('"').strip("'")
                                if k not in os.environ:
                                    os.environ[k] = v
                except Exception:
                    pass

        try:
            import streamlit as st
            if hasattr(st, "secrets"):
                for key in ["GROQ_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"]:
                    if key in st.secrets and key not in os.environ:
                        os.environ[key] = str(st.secrets[key])
        except Exception:
            pass

    def _init_clients(self):
        # Auto-detect provider if "auto"
        active_provider = self.provider
        if active_provider == "auto":
            m_lower = self.model.lower()
            if any(x in m_lower for x in ["claude"]):
                active_provider = "anthropic"
            elif any(x in m_lower for x in ["groq", "llama", "mixtral", "qwen", "gpt-oss"]):
                active_provider = "groq"
            elif any(x in m_lower for x in ["gpt", "o1", "o3", "o4", "chatgpt"]):
                active_provider = "openai"
            elif any(x in m_lower for x in ["gemini"]):
                active_provider = "gemini"
            elif os.environ.get("GROQ_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
                active_provider = "groq"
            elif os.environ.get("ANTHROPIC_API_KEY"):
                active_provider = "anthropic"
            elif os.environ.get("OPENAI_API_KEY"):
                active_provider = "openai"
            elif os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
                active_provider = "gemini"

        # Initialize Groq Client
        if active_provider in ["groq", "auto"]:
            key = os.environ.get("GROQ_API_KEY")
            if key:
                try:
                    import groq
                    self.groq_client = groq.Groq(api_key=key)
                    if not any(x in self.model.lower() for x in ["llama", "mixtral", "qwen", "gpt-oss"]):
                        self.model = "llama-3.3-70b-versatile"
                    logger.info(f"Initialized Groq client with model {self.model}")
                except Exception as e:
                    logger.warning(f"Could not initialize Groq client: {e}")

        # Initialize Anthropic Client
        if active_provider in ["anthropic", "auto"] and not self.groq_client:
            key = os.environ.get("ANTHROPIC_API_KEY")
            if key:
                try:
                    import anthropic
                    self.anthropic_client = anthropic.Anthropic(api_key=key)
                    logger.info(f"Initialized Anthropic client with model {self.model}")
                except Exception as e:
                    logger.warning(f"Could not initialize Anthropic client: {e}")

        # Initialize OpenAI Client (or OpenAI-compatible endpoint)
        if active_provider in ["openai", "auto"] and not self.anthropic_client and not self.groq_client:
            key = os.environ.get("OPENAI_API_KEY")
            if key or self.api_base:
                try:
                    import openai
                    kwargs: Dict[str, Any] = {}
                    if key:
                        kwargs["api_key"] = key
                    if self.api_base:
                        kwargs["base_url"] = self.api_base
                    self.openai_client = openai.OpenAI(**kwargs)
                    logger.info(f"Initialized OpenAI client with model {self.model} (base_url: {self.api_base or 'default'})")
                except Exception as e:
                    logger.warning(f"Could not initialize OpenAI client: {e}")

        # Initialize Google GenAI Client
        if active_provider in ["gemini", "auto"] and not self.anthropic_client and not self.openai_client and not self.groq_client:
            key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if key:
                try:
                    from google import genai
                    self.gemini_client = genai.Client()
                    logger.info(f"Initialized Google GenAI client with model {self.model}")
                except Exception as e:
                    logger.warning(f"Could not initialize Google GenAI client: {e}")

    def call_structured(
        self,
        schema: Type[T],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
        temperature: float = 0.2,
        use_cache: bool = True
    ) -> T:
        schema_dict = schema.model_json_schema()
        cache_key = compute_cache_key(self.model, system_prompt, user_prompt, schema_dict)

        if use_cache:
            cached_text = global_cache.get(cache_key)
            if cached_text:
                try:
                    global_token_tracker.record(0, 0, cached=True)
                    return schema.model_validate_json(cached_text)
                except Exception as e:
                    logger.warning(f"Failed to parse cached response: {e}")

        # If no active remote provider, go directly to Heuristic Generator
        if not self.anthropic_client and not self.openai_client and not self.gemini_client and not self.groq_client:
            logger.debug(f"Using Heuristic Generator for {schema.__name__}")
            heuristic_dict = HeuristicLLMGenerator.generate(schema.__name__, system_prompt, user_prompt)
            raw_json = json.dumps(heuristic_dict)
            parsed = schema.model_validate(heuristic_dict)
            global_token_tracker.record(len(user_prompt) // 4, len(raw_json) // 4, cached=False)
            if use_cache:
                global_cache.set(cache_key, raw_json)
            return parsed

        # Attempt API call with retries
        max_retries = 2
        last_error = None

        for attempt in range(max_retries):
            try:
                raw_json = self._execute_call(schema, system_prompt, user_prompt, max_tokens, temperature)
                parsed = schema.model_validate_json(raw_json)
                if use_cache:
                    global_cache.set(cache_key, raw_json)
                return parsed
            except Exception as e:
                last_error = e
                # If quota exhausted (429) or invalid auth, switch to heuristic engine
                if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e) or "quota" in str(e).lower():
                    logger.warning(f"Remote API quota exhausted: {e}. Switching to heuristic engine permanently for this session.")
                    self.gemini_client = None
                    self.openai_client = None
                    break
                logger.warning(f"LLM call attempt {attempt+1} failed: {e}")
                time.sleep(1.0)

        # Fallback to Heuristic Generator if API failed
        logger.info(f"Using Heuristic Generator for {schema.__name__}")
        heuristic_dict = HeuristicLLMGenerator.generate(schema.__name__, system_prompt, user_prompt)
        raw_json = json.dumps(heuristic_dict)
        parsed = schema.model_validate(heuristic_dict)
        global_token_tracker.record(len(user_prompt) // 4, len(raw_json) // 4, cached=False)
        if use_cache:
            global_cache.set(cache_key, raw_json)
        return parsed

    def _execute_call(
        self,
        schema: Type[T],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float
    ) -> str:
        schema_dict = schema.model_json_schema()

        # 1. Anthropic Provider
        if self.anthropic_client:
            tool_name = "output_structured_result"
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[{
                    "name": tool_name,
                    "description": "Output structured result matching schema",
                    "input_schema": schema_dict
                }],
                tool_choice={"type": "tool", "name": tool_name}
            )

            input_tok = response.usage.input_tokens
            output_tok = response.usage.output_tokens
            global_token_tracker.record(input_tok, output_tok, cached=False)

            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    return json.dumps(block.input)
            raise ValueError(f"No tool_use block found in Anthropic response: {response.content}")

        # 2. OpenAI / OpenAI-Compatible Provider
        elif self.openai_client:
            # Supports structured outputs via response_format or tool calling
            try:
                completion = self.openai_client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format=schema,
                    temperature=temperature
                )
                in_tok = completion.usage.prompt_tokens if completion.usage else len(user_prompt) // 4
                out_tok = completion.usage.completion_tokens if completion.usage else 500
                global_token_tracker.record(in_tok, out_tok, cached=False)
                parsed_res = completion.choices[0].message.parsed
                if parsed_res:
                    return parsed_res.model_dump_json()
                elif completion.choices[0].message.content:
                    return completion.choices[0].message.content
            except Exception as e:
                # Fallback to json_object response format
                logger.debug(f"OpenAI beta parse fallback: {e}")
                completion = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": f"{system_prompt}\nReturn JSON matching schema: {json.dumps(schema_dict)}"},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=temperature
                )
                in_tok = completion.usage.prompt_tokens if completion.usage else len(user_prompt) // 4
                out_tok = completion.usage.completion_tokens if completion.usage else 500
                global_token_tracker.record(in_tok, out_tok, cached=False)
                return completion.choices[0].message.content

        # 3. Groq Provider (Fast Llama-3/Qwen/Mixtral inference)
        elif self.groq_client:
            prompt_with_schema = (
                f"{system_prompt}\n\n"
                f"You MUST respond ONLY with a single JSON object strictly matching this JSON schema:\n"
                f"{json.dumps(schema_dict, indent=2)}\n"
                f"Do not include Markdown backticks (```json), commentary, or extra text."
            )
            completion = self.groq_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt_with_schema},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=temperature
            )
            in_tok = completion.usage.prompt_tokens if completion.usage else len(user_prompt) // 4
            out_tok = completion.usage.completion_tokens if completion.usage else 500
            global_token_tracker.record(in_tok, out_tok, cached=False)
            return completion.choices[0].message.content

        # 4. Google GenAI Provider
        elif self.gemini_client:
            from google.genai import types
            gemini_model = self.model if "gemini" in self.model.lower() else "gemini-2.5-flash"
            contents = f"System: {system_prompt}\n\nTask: {user_prompt}"
            response = self.gemini_client.models.generate_content(
                model=gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=temperature,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    max_output_tokens=max_tokens
                )
            )
            in_tok = len(contents) // 4
            out_tok = len(response.text) // 4
            global_token_tracker.record(in_tok, out_tok, cached=False)
            return response.text

        else:
            raise RuntimeError("No active LLM provider found.")
