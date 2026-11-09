import os
import pytest
from promofinder.llm import LLMClient, PRICING, global_token_tracker
from promofinder.pipeline import PipelineRunner
from promofinder.models import ColdViewerOutput

def test_model_auto_detection_and_swapping():
    # Test Anthropic model resolution
    client_claude = LLMClient(model="claude-3-7-sonnet-20250219")
    assert client_claude.model == "claude-3-7-sonnet-20250219"

    # Test OpenAI model resolution
    client_gpt = LLMClient(model="gpt-4o")
    assert client_gpt.model == "gpt-4o"

    # Test Gemini model resolution
    client_gemini = LLMClient(model="gemini-2.5-pro")
    assert client_gemini.model == "gemini-2.5-pro"

    # Test Groq model resolution
    client_groq = LLMClient(model="llama-3.3-70b-versatile", provider="groq")
    assert client_groq.model == "llama-3.3-70b-versatile"

def test_pricing_coverage_for_stronger_models():
    # Verify pricing is defined for leading strong models
    assert "claude-3-7-sonnet-20250219" in PRICING
    assert "claude-3-opus-20240229" in PRICING
    assert "gpt-4o" in PRICING
    assert "gpt-4.5-preview" in PRICING
    assert "o1" in PRICING
    assert "gemini-2.5-pro" in PRICING

    summary = global_token_tracker.get_summary("claude-3-7-sonnet-20250219")
    assert "estimated_cost_usd" in summary

def test_pipeline_runner_model_override():
    # Verify PipelineRunner properly overrides config when model is passed
    runner = PipelineRunner(config_path="./config.yaml", model="claude-3-7-sonnet-20250219")
    assert runner.llm.model == "claude-3-7-sonnet-20250219"

    runner_gpt = PipelineRunner(config_path="./config.yaml", model="gpt-4o", provider="openai")
    assert runner_gpt.llm.model == "gpt-4o"
    assert runner_gpt.llm.provider == "openai"

def test_heuristic_generator_compatibility_across_swapped_models():
    # Verify schema generation works deterministically regardless of model string
    client = LLMClient(model="custom-future-strong-model-v1", provider="heuristic")
    res = client.call_structured(
        schema=ColdViewerOutput,
        system_prompt="Test system",
        user_prompt="JULIANA: Where is Gerald? MATRIARCH: Turn around.",
        use_cache=False
    )
    assert res.standalone_score >= 1
    assert len(res.characters) > 0

