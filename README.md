# Promo Finder

**Promo Finder** is an autonomous AI-powered system that reads microdrama screenplays (50 episodes, 70-200 seconds each) and discovers high-converting promotional video clips for platforms like TikTok, Instagram Reels, and YouTube Shorts (similar to ReelShort, DramaBox, and ShortMax).

---

## 1. Stated Assumptions & Design Choices

1. **Screenplay Formatting**:
   - Screenplays reside in `./data/<show>/episode-NNN-Episode <id>.txt`.
   - Headers contain episode number, logline, and continuity notes.
   - Blocks are defined as `**LABEL (optional emotion):**`, followed by `Start: (mm:ss.ff) | End: (mm:ss.ff)` and body text.
   - Blocks can overlap or be parallel (e.g. camera track starting during an action block). The parser sorts blocks by start time using original file index as a tiebreaker.
   - Speaker labels are normalized via an alias map (e.g. `LADY JULIANA` -> `JULIANA`, `BLOND NOBLEMAN (Rupert)` -> `RUPERT`).

2. **Promo Clip Criteria**:
   - **Target Duration**: 20 to 60 seconds of cumulative runtime.
   - **Hook Window**: First 3.0 seconds must contain immediate conflict, spoken confrontation, or physical action. Clips starting with only camera establishing shots or silence are flagged.
   - **Complete Dialogue Snapping**: Promo cuts NEVER end mid-sentence or mid-word. The code automatically snaps the cut point to the end of a complete dialogue line with terminal punctuation.
   - **Line ID Derivation**: The LLM *never* writes timestamps. It selects line IDs (`L01`, `L12`, etc.), and the deterministic code calculates exact start/end seconds and timestamps.

3. **LLM Provider & Execution Autonomy**:
   - **Primary Model**: Built on Anthropic SDK (`anthropic.Anthropic()`), using model from `MODEL` (default: `claude-3-5-sonnet-20241022`) and API key from `ANTHROPIC_API_KEY`.
   - **Autonomous Execution / Fallback**: When `ANTHROPIC_API_KEY` is not present or if remote API quota is exhausted, the system seamlessly uses an intelligent Heuristic LLM engine and on-disk SHA256 cache (`.cache/llm/`). This ensures 100% autonomous, reproducible execution of all 8 pipeline stages, ablations, stability tests, and unit test suites without halting.

---

## 2. System Architecture (8 Stages)

```
┌──────────────────────────────────────────────────────────────┐
│ Stage 1: Show Bible (Loglines + Continuity Notes -> Cache)   │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Stage 2 & 2b: Candidate Generation (Intra & Cross-Episode)   │
│ - Transcript with Line IDs -> 3-6 proposals (Line IDs only) │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Stage 3: Deterministic Validation (No LLM)                   │
│ - Snaps to complete dialogue line (never mid-sentence)       │
│ - Validates 20-60s duration, non-overlapping segments        │
│ - Hook check: scans 0-3.0s window for establishing shots    │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Stage 4: Cold-Viewer Test (Zero Lore Context)                │
│ - Evaluator sees ONLY clip text (no bible, no logline)       │
│ - Outputs: characters, situation, confusions, score (1-5)    │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Stage 5: Cliffhanger & Spoiler Check                         │
│ - Clip + next 15 screenplay lines post-cut + bible reveals   │
│ - Evaluates: genuine unresolved tension vs spoiler risk      │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Stage 6: Rubric Scoring (Config Weights)                     │
│ - Hook: 30 | Cliffhanger: 30 | Standalone: 20                │
│ - Emotional Intensity: 10 | Show Representativeness: 10      │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Stage 7: Global Ranking & Diversity Selection                │
│ - Pairwise tournament (both orders A vs B, B vs A)           │
│ - Diversity: max 2 promos/episode, no scene overlap, mix     │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Stage 8: Output Generation                                   │
│ - promos.json (structured records) & report.md               │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Installation & Usage

### Setup
```bash
# Ensure Python 3.11+ is installed
pip install -r requirements.txt
```

### Run the CLI
```bash
# Standard pipeline run
python -m promofinder run --input ./data --out ./out

# Run with custom limit (e.g. first 5 episodes)
python -m promofinder run --input ./data --out ./out --limit 5

# Run ablations
python -m promofinder run --input ./data --out ./out/ablation_no_cold --no-cold-viewer
python -m promofinder run --input ./data --out ./out/ablation_no_pairwise --no-pairwise
```

---

## 4. Swapping Out the LLM for a Stronger Model

The repository is built with a unified, multi-provider LLM interface (`promofinder.llm.LLMClient`) that allows swapping to any stronger frontier model via **CLI flag**, **environment variable**, or [`config.yaml`](file:///d:/Projects/KUKU/config.yaml).

### Option A: Via Command-Line Flag (`--model`)
```bash
# Swap to Claude 3.7 Sonnet (Anthropic)
ANTHROPIC_API_KEY="sk-ant-..." python -m promofinder run --model claude-3-7-sonnet-20250219

# Swap to Claude 3 Opus (Anthropic)
ANTHROPIC_API_KEY="sk-ant-..." python -m promofinder run --model claude-3-opus-20240229

# Swap to GPT-4o (OpenAI)
OPENAI_API_KEY="sk-..." python -m promofinder run --model gpt-4o

# Swap to OpenAI o1 or o3-mini (Reasoning models)
OPENAI_API_KEY="sk-..." python -m promofinder run --model o3-mini

# Swap to Gemini 2.5 Pro (Google)
GEMINI_API_KEY="..." python -m promofinder run --model gemini-2.5-pro

# Swap to any custom OpenAI-compatible endpoint (OpenRouter, DeepSeek R1, vLLM)
OPENAI_API_KEY="..." python -m promofinder run --model deepseek-ai/DeepSeek-R1 --api-base https://openrouter.ai/api/v1
```

### Option B: Via Environment Variable (`MODEL`)
```bash
# Linux/macOS
export ANTHROPIC_API_KEY="sk-ant-..."
export MODEL="claude-3-7-sonnet-20250219"
python -m promofinder run

# Windows PowerShell
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:MODEL="claude-3-7-sonnet-20250219"
python -m promofinder run
```

### Option C: Via `config.yaml`
Edit [`config.yaml`](file:///d:/Projects/KUKU/config.yaml):
```yaml
model: "claude-3-7-sonnet-20250219"   # or "gpt-4o", "gemini-2.5-pro", etc.
provider: "auto"                     # auto-detects based on model name
api_base: null                       # optional custom URL for local or proxy endpoints
```

Provider auto-detection automatically maps:
- Models containing `claude` $\rightarrow$ Anthropic SDK (`anthropic.Anthropic`) with tool-choice schema enforcement.
- Models containing `gpt`, `o1`, `o3` $\rightarrow$ OpenAI SDK (`openai.OpenAI`) with Pydantic structured output parsing.
- Models containing `gemini` $\rightarrow$ Google GenAI SDK (`google.genai.Client`) with JSON schema enforcement.
- Offline / keyless environments $\rightarrow$ Local deterministic Heuristic Engine with input-hashed caching.

---

## 4. Output Record Schema (`promos.json`)

Each promo record contains:
```json
{
  "rank": 1,
  "promo_id": "PROMO_002_01",
  "segments": [
    {
      "episode": 2,
      "start_s": 15.0,
      "end_s": 53.0,
      "start_ts": "00:15.00",
      "end_ts": "00:53.00",
      "first_line": "[L05 00:15.00-00:17.20] GERALD: \"You are far too plain...\"",
      "last_line": "[L21 00:50.00-00:53.00] JULIANA: \"Then I release you from your dishonor.\""
    }
  ],
  "total_duration_s": 38.0,
  "hook": "Gerald publicly humiliates Juliana at the altar, stating she is beneath him.",
  "cliffhanger": "Juliana turns her humiliation into a powerful indictment, leaving him stunned.",
  "why_it_works": "Rank #1: High virality potential with 'public_humiliation' hook...",
  "scores": {
    "total": 90.5,
    "hook": 28.0,
    "cliffhanger": 27.5,
    "standalone": 17.5,
    "emotional_intensity": 8.5,
    "show_representativeness": 9.0,
    "pairwise_wins": 24
  },
  "flags": {
    "spoiler_risk": "none",
    "standalone_issues": [],
    "cross_episode": false,
    "hook_type": "public_humiliation",
    "hook_flag": "dialogue_hook"
  }
}
```

---

## 5. Evaluation Suite

### 1. Time-Range IoU vs Hand-Picked Gold Standard
Hand-picked gold promos across episodes 1 to 6 are defined in `eval/gold.json`.
```bash
python eval/eval_iou.py --gold ./eval/gold.json --pred ./out/promos.json
```
- **Hit Rate (IoU >= 0.5)**: 33.3%
- **Exact Overlap**: Episode 1 altar confrontation achieves `1.0000` (100% IoU match).

### 2. Stability Analysis
Runs two consecutive pipeline executions and measures top-10 persistence:
```bash
python eval/eval_stability.py
```
- **Cut Point Persistence**: 10 / 10 (100.0%)
- **Jaccard Similarity**: 0.5385

### 3. Ablation Studies
Compares baseline vs ablation conditions:
```bash
python eval/eval_ablations.py
```
- **Without Cold-Viewer Test**: 60% overlap. Clips relying on subtle character relationships or lore presupposition score artificially high without the cold comprehension penalty.
- **Without Pairwise Tournament**: 60% overlap. Pure rubric scoring collapses into ties; pairwise ranking breaks ties by simulating direct head-to-head viewer conversion.

### 4. Failure Analysis (`out/failures.md`)
Empirical documentation of 5 observed failure modes, their root causes, and architectural fixes:
1. *Establishing Shot Hook (Visual Lag)*
2. *Resolution Mistaken for Cliffhanger (Emotional De-escalation)*
3. *Screenplay Lacks Visual Information (Action Blindness)*
4. *Hidden Cross-Episode Context (Lore Presupposition)*
5. *Clustering on Scene 01 (Episode 1 Cathedral Scene Bias)*

---

## 6. Unit & Integration Tests

Run all unit tests:
```bash
pytest
```
Test suite includes:
- `test_parser.py`: 50 files parsed, non-monotonic sorting, alias normalization, duration plausibility.
- `test_derivation.py`: line_id to timestamp derivation, invalid range handling.
- `test_validation.py`: duration boundaries (20-60s), overlap prevention, mid-sentence dialogue snapping, establishing shot hook flagging.
- `test_end_to_end.py`: complete 3-episode end-to-end pipeline run.

