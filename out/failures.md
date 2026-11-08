# Failure Analysis: Observed Bad Picks, Root Causes, and Fixes

During empirical validation of the Promo Finder pipeline on the 50-episode microdrama screenplay dataset (*"I Married a Broken Soldier. He was a Duke"*), several candidate selections exhibited failure modes characteristic of vertical video marketing. Below is the documentation of 5 observed failure modes, their root causes, and how our architecture addresses or proposes to fix them.

---

### Failure 1: Establishing Shot Hook (Visual Lag)
- **Observed Promo**: Candidate starting at Episode 1, Line `L01` (00:00.00 to 00:04.80: *"CAMERA: Symmetrical framing on the heavy church doors as they slowly part, pushing in slightly as Juliana stands framed in the light..."*).
- **What Went Wrong**: On Instagram Reels and TikTok, the first 3 seconds dictate whether a user scrolls past or watches. A promo starting with 4.8 seconds of doors opening and silent architectural framing has near-zero thumb-stopping power, despite being cinematic in a traditional film sense.
- **Root Cause**: Screenplays naturally begin scenes with establishing visual blocks (`CAMERA` and `ACTION`). When an LLM selects a clip from the scene start, it mistakes cinematic pacing for social video virality.
- **Implemented & Proposed Fix**:
  1. *Deterministic Hook Inspection*: In Stage 3, we analyze all events in the `0-3.0s` window. If only `CAMERA` or establishing scenery occurs (`establishing_shot_only`), the candidate is flagged.
  2. *Automatic Hook Trimming*: Snap the promo start forward to the first spoken confrontation or disruptive action (e.g. fast-forwarding from 00:00.00 to 00:11.00 where the Matriarch steps into the foreground saying *"You should turn around, Juliana"*).

---

### Failure 2: Resolution Mistaken for Cliffhanger (Emotional De-escalation)
- **Observed Promo**: Candidate ending at Episode 25, lines 02:42.50 to 02:48.00 (*"Alexander turns, falling into step beside Juliana. Together, side by side, they begin their quiet walk down the darkening forest path into the twilight as emotional strings swell to a resolving chord."*).
- **What Went Wrong**: The clip terminates on resolution, emotional reconciliation, and visual closure. Viewers feel satisfied and experience closure, completely extinguishing the urgency to click "Watch Next Episode" or download the microdrama app.
- **Root Cause**: The preceding dialogue in Episode 25 contained intense melodrama regarding arsenic poisoning. The candidate generation prompt rewarded the high emotional intensity of the scene overall, failing to differentiate between peak tension cut points versus resolution tail cut points.
- **Implemented & Proposed Fix**:
  1. *Post-Cut Inspection (Stage 5)*: We feed the promo text along with the *next 15 lines after the cut* to an LLM evaluator. If the scene resolves into consensus, peaceful exit, or emotional resolution chords, `is_unresolved` is set to `False` and the cliffhanger score is heavily penalized.
  2. *Negative Prompting*: Explicitly prompt candidate generators: *"Never end on characters walking away, resolving their dispute, or emotional closure."*

---

### Failure 3: Screenplay Lacks Visual Information (Action Blindness)
- **Observed Promo**: Candidate from Episode 1 where Gerald holds the hand of the "Lady in Gold Gown" (Clarissa). Juliana asks: *"Why?"* (00:13.50).
- **What Went Wrong**: In the text screenplay, the action note states: *"Gerald in his dark tailcoat holding the gloved hand of the Lady in Gold Gown."* However, in spoken audio, Juliana only says *"Why? Gerald is waiting for me."* The audience hearing the promo does not learn that the woman in gold is her cruel sister Clarissa until 25 seconds later.
- **Root Cause**: Screenplay action lines convey narrative facts to the film crew that may not be immediately audible to a social media viewer listening to speech. Without dialogue reinforcement, the initial conflict is ambiguous.
- **Implemented & Proposed Fix**:
  1. *Cold-Viewer Test (Stage 4)*: The cold-viewer evaluator sees only the transcript text without loglines. If the character dynamic cannot be deduced from spoken lines and visible actions within the first 5 seconds, the standalone score drops to 2 or 3.
  2. *Dialogue Anchor Requirement*: Prioritize candidate segments where the visual action is immediately echoed by spoken dialogue (e.g. Clarissa's spoken declaration: *"Because he is marrying me"*).

---

### Failure 4: Hidden Cross-Episode Context (Lore Presupposition)
- **Observed Promo**: Candidate from Episode 16 focusing on Gerald Harrington disputing the apothecary garden harvest.
- **What Went Wrong**: For a cold TikTok viewer, an argument about medicinal herbs and apothecary licensing lacks obvious high-stakes punch. The viewer does not know Juliana's late mother was an herbalist, nor that the poison threatening the Duchess is hidden in plain sight.
- **Root Cause**: The model generated candidates while holding the full Show Bible and logline in its prompt context. It suffered from "curse of knowledge," assuming the audience understands the underlying conspiracy.
- **Implemented & Proposed Fix**:
  1. *Context-Blind Standalone Evaluation*: In Stage 4, the cold-viewer model has zero access to the show bible, loglines, or character dossiers. If the stakes appear trivial or baffling to an uninformed viewer, `standalone_score` is marked low, preventing the candidate from surviving global ranking.

---

### Failure 5: Clustering on Scene 01 (Episode 1 Wedding Scene Bias)
- **Observed Promo**: Multiple candidates generated across Episode 1: Candidate 1 (`L07-L27`), Candidate 2 (`L27-L62`), and Candidate 3 (`L52-L93`), all originating in the cathedral nave during the altar abandonment.
- **What Went Wrong**: Without diversity intervention, the platform ad account would post three almost identical clips from the same 2-minute scene in the same cathedral. This causes creative fatigue, ad cannibalization, and poor platform audience retention.
- **Root Cause**: Pilot episodes of microdramas concentrate explosive conflict into the opening scene, resulting in high rubric scores for every sub-slice of that scene.
- **Implemented & Proposed Fix**:
  1. *Episode & Scene Diversity Filter (Stage 7)*:
     - Enforce a strict maximum of 2 promos per episode (`max_promos_per_episode = 2`).
     - Enforce scene uniqueness: once a promo from `SCENE 01: INT. CATHEDRAL` is selected, subsequent candidates from the same scene are disqualified in favor of candidates from different scenes or episodes.
  2. *Hook Type Diversity*: Enforce a mix of hook types (e.g. `public_humiliation`, `confrontation`, `physical_action`, `scandalous_reveal`).

