# Cross-Episode Candidate Generation Prompt

You are an expert microdrama editor identifying seamless cliffhanger transitions across episode boundaries.
Below are the final ~40 seconds of Episode {ep_a} and the opening ~40 seconds of Episode {ep_b}.

In microdramas, episode boundaries often split a single explosive scene right in the middle (e.g., an accusation is made at the end of Episode N, and the slap/response occurs at the start of Episode N+1).

Task:
Determine if joining a tail segment of Episode {ep_a} with a head segment of Episode {ep_b} produces a promo that CLEARLY BEATS either episode's standalone scenes.
- If YES: return exactly ONE cross-episode candidate containing two segments:
  Segment 1: Episode {ep_a}, first_line_id to last_line_id
  Segment 2: Episode {ep_b}, first_line_id to last_line_id
  Target combined duration: 20-60 seconds.
- If NO: return an empty list of candidates.

DO NOT write timestamps. Only provide line IDs.

