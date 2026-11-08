from __future__ import annotations
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class Line(BaseModel):
    episode: int
    line_id: str
    start_s: float
    end_s: float
    kind: Literal["camera", "action", "sfx", "dialogue"]
    speaker: Optional[str] = None
    emotion: Optional[str] = None
    text: str
    scene: str

    def format_for_prompt(self) -> str:
        s_m, s_s = divmod(self.start_s, 60)
        e_m, e_s = divmod(self.end_s, 60)
        ts_str = f"{int(s_m):02d}:{s_s:05.2f}-{int(e_m):02d}:{e_s:05.2f}"
        if self.kind == "dialogue":
            spk = self.speaker or "UNKNOWN"
            emo = f" ({self.emotion})" if self.emotion else ""
            return f"[{self.line_id} {ts_str}] {spk}{emo}: \"{self.text}\""
        elif self.kind == "camera":
            return f"[{self.line_id} {ts_str}] CAMERA: {self.text}"
        elif self.kind == "action":
            return f"[{self.line_id} {ts_str}] ACTION: {self.text}"
        elif self.kind == "sfx":
            return f"[{self.line_id} {ts_str}] SOUND FX: {self.text}"
        return f"[{self.line_id} {ts_str}] {self.text}"

class Episode(BaseModel):
    number: int
    logline: str
    continuity: str
    lines: List[Line]
    duration_s: float

class MajorReveal(BaseModel):
    episode: int
    reveal: str
    is_spoiler: bool
    explanation: str

class CharacterBio(BaseModel):
    name: str
    aliases: List[str] = Field(default_factory=list)
    role: str
    motivation: str

class ShowBible(BaseModel):
    title: str = "I Married a Broken Soldier. He was a Duke"
    premise: str
    characters: List[CharacterBio]
    relationships: List[str]
    main_arc: str
    major_reveals: List[MajorReveal]

class SegmentSpec(BaseModel):
    episode: int
    first_line_id: str
    last_line_id: str

class CandidateProposal(BaseModel):
    segments: List[SegmentSpec]
    hook_description: str
    hook_type: str = "confrontation"
    cliffhanger_description: str
    rationale: str

class CandidateGenerationOutput(BaseModel):
    candidates: List[CandidateProposal]

class ValidatedSegment(BaseModel):
    episode: int
    start_s: float
    end_s: float
    start_ts: str
    end_ts: str
    first_line: str
    last_line: str

class ValidationResult(BaseModel):
    is_valid: bool
    reject_reason: Optional[str] = None
    segments: List[ValidatedSegment] = Field(default_factory=list)
    total_duration_s: float = 0.0
    hook_events_0_to_3s: List[str] = Field(default_factory=list)
    hook_flag: Optional[str] = None

class ColdViewerOutput(BaseModel):
    characters: List[str]
    situation: str
    confusing_points: List[str]
    standalone_score: int
    notes: str

class CliffhangerSpoilerOutput(BaseModel):
    unresolved_cliffhanger_score: float
    cliffhanger_analysis: str
    is_unresolved: bool
    spoiler_risk: Literal["none", "minor", "severe"]
    spoiler_analysis: str

class RubricScores(BaseModel):
    hook: float
    hook_justification: str
    cliffhanger: float
    cliffhanger_justification: str
    standalone: float
    standalone_justification: str
    emotional_intensity: float
    emotional_intensity_justification: str
    show_representativeness: float
    show_representativeness_justification: str
    total_weighted_score: float

class PromoRecord(BaseModel):
    rank: int
    promo_id: str
    segments: List[ValidatedSegment]
    total_duration_s: float
    hook: str
    cliffhanger: str
    why_it_works: str
    scores: Dict[str, Any]
    flags: Dict[str, Any]

