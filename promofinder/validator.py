import re
from typing import List, Dict, Optional, Tuple
from promofinder.models import (
    Episode,
    Line,
    CandidateProposal,
    SegmentSpec,
    ValidatedSegment,
    ValidationResult,
)

ESTABLISHING_KEYWORDS = [
    "establishing", "exterior", "wide tracking shot", "wide shot", "panoramic",
    "aerial", "high wide", "symmetrical framing on the heavy", "distant", "scenery"
]

def format_seconds_to_ts(seconds: float) -> str:
    m, s = divmod(seconds, 60.0)
    return f"{int(m):02d}:{s:05.2f}"

def validate_candidate(
    candidate: CandidateProposal,
    episodes_by_num: Dict[int, Episode],
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    hook_window: float = 3.0
) -> ValidationResult:
    """
    Stage 3: Deterministic validation of candidate promo clips.
    - Derives start = min start_s, end = max end_s of line_id range.
    - Snaps clip end to complete dialogue line (never mid-sentence).
    - Checks 20-60s total duration.
    - Checks ordering and non-overlapping segments.
    - Performs hook check for 0-3.0s window.
    """
    if not candidate.segments:
        return ValidationResult(is_valid=False, reject_reason="No segments provided")

    validated_segs: List[ValidatedSegment] = []
    all_hook_events: List[str] = []
    first_seg_hook_flag = None

    for seg_idx, seg in enumerate(candidate.segments):
        ep = episodes_by_num.get(seg.episode)
        if not ep:
            return ValidationResult(is_valid=False, reject_reason=f"Episode {seg.episode} not found")

        # Find line index range
        line_map = {l.line_id: l for l in ep.lines}
        if seg.first_line_id not in line_map:
            return ValidationResult(is_valid=False, reject_reason=f"Line {seg.first_line_id} not in Ep {seg.episode}")
        if seg.last_line_id not in line_map:
            return ValidationResult(is_valid=False, reject_reason=f"Line {seg.last_line_id} not in Ep {seg.episode}")

        # Get all lines in the span
        ep_line_ids = [l.line_id for l in ep.lines]
        try:
            start_idx = ep_line_ids.index(seg.first_line_id)
            end_idx = ep_line_ids.index(seg.last_line_id)
        except ValueError:
            return ValidationResult(is_valid=False, reject_reason=f"Invalid line range {seg.first_line_id}-{seg.last_line_id}")

        if start_idx > end_idx:
            return ValidationResult(is_valid=False, reject_reason=f"Start line {seg.first_line_id} is after end line {seg.last_line_id}")

        span_lines = ep.lines[start_idx:end_idx + 1]

        # Calculate raw start and end
        raw_start_s = min(l.start_s for l in span_lines)
        raw_end_s = max(l.end_s for l in span_lines)

        # Snap clip end to complete dialogue line if applicable
        # If the last line is dialogue, ensure it ends with terminal punctuation (. ? ! " )
        last_line = span_lines[-1]
        snapped_end_s = raw_end_s
        if last_line.kind == "dialogue":
            # If line text ends in comma or ellipsis or no punctuation, check if next line in episode completes it
            txt = last_line.text.strip().rstrip('"').strip()
            if txt and txt[-1] in [",", ";", "-"] and (end_idx + 1 < len(ep.lines)):
                next_line = ep.lines[end_idx + 1]
                if next_line.kind == "dialogue" and next_line.speaker == last_line.speaker:
                    # Snap forward to cover the complete sentence
                    snapped_end_s = max(snapped_end_s, next_line.end_s)
                    span_lines.append(next_line)
                    end_idx += 1

        first_line_repr = span_lines[0].format_for_prompt()
        last_line_repr = span_lines[-1].format_for_prompt()

        validated_segs.append(ValidatedSegment(
            episode=seg.episode,
            start_s=raw_start_s,
            end_s=snapped_end_s,
            start_ts=format_seconds_to_ts(raw_start_s),
            end_ts=format_seconds_to_ts(snapped_end_s),
            first_line=first_line_repr,
            last_line=last_line_repr
        ))

        # Hook check on the very first segment
        if seg_idx == 0:
            hook_limit = raw_start_s + hook_window
            hook_lines = [l for l in ep.lines if l.start_s < hook_limit and l.end_s >= raw_start_s]
            has_dialogue = any(l.kind == "dialogue" for l in hook_lines)
            has_action = any(l.kind == "action" for l in hook_lines)
            has_sfx = any(l.kind == "sfx" for l in hook_lines)
            
            for hl in hook_lines:
                all_hook_events.append(f"[{hl.kind.upper()}] {hl.text[:60]}")

            # Check if only establishing shots
            only_camera = all(hl.kind == "camera" for hl in hook_lines)
            is_establishing = any(
                any(k in hl.text.lower() for k in ESTABLISHING_KEYWORDS)
                for hl in hook_lines
            )

            if not hook_lines:
                first_seg_hook_flag = "silent_start"
            elif only_camera and is_establishing:
                first_seg_hook_flag = "establishing_shot_only"
            elif has_dialogue:
                first_seg_hook_flag = "dialogue_hook"
            elif has_action:
                first_seg_hook_flag = "action_hook"
            elif has_sfx:
                first_seg_hook_flag = "sfx_hook"
            else:
                first_seg_hook_flag = "standard"

    # Validate ordering and non-overlapping segments
    for i in range(len(validated_segs) - 1):
        s_cur = validated_segs[i]
        s_next = validated_segs[i + 1]
        if s_next.episode < s_cur.episode:
            return ValidationResult(
                is_valid=False,
                reject_reason=f"Episodes out of order: Ep {s_cur.episode} then Ep {s_next.episode}"
            )
        elif s_next.episode == s_cur.episode:
            if s_next.start_s < s_cur.end_s:
                return ValidationResult(
                    is_valid=False,
                    reject_reason=f"Overlapping segments in Ep {s_cur.episode}: {s_cur.start_ts}-{s_cur.end_ts} vs {s_next.start_ts}-{s_next.end_ts}"
                )

    # Validate total duration
    total_dur = sum(s.end_s - s.start_s for s in validated_segs)
    total_dur = round(total_dur, 2)
    if total_dur < min_duration:
        return ValidationResult(
            is_valid=False,
            reject_reason=f"Total duration {total_dur:.1f}s is under minimum {min_duration:.1f}s",
            segments=validated_segs,
            total_duration_s=total_dur
        )
    if total_dur > max_duration:
        return ValidationResult(
            is_valid=False,
            reject_reason=f"Total duration {total_dur:.1f}s exceeds maximum {max_duration:.1f}s",
            segments=validated_segs,
            total_duration_s=total_dur
        )

    return ValidationResult(
        is_valid=True,
        segments=validated_segs,
        total_duration_s=total_dur,
        hook_events_0_to_3s=all_hook_events,
        hook_flag=first_seg_hook_flag
    )

