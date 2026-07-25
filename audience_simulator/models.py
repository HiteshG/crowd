from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Beat:
    beat_id: str
    text: str
    label: str = ""
    purpose: str = ""
    line_start: int | None = None
    line_end: int | None = None
    speaker_focus: tuple[str, ...] = ()
    audience_decision_risk: str = "none"
    risk_reason: str = ""
    evidence_quote: str = ""
    emotional_intensity: int | None = None
    suspense: int | None = None
    craving_effect: str = ""
    generator: str = "parser"


@dataclass(frozen=True)
class Episode:
    episode_no: int
    title: str
    text: str
    beats: list[Beat]


@dataclass(frozen=True)
class Persona:
    persona_id: str
    realname: str
    age: int
    gender: str
    country: str
    city: str
    city_tier: int
    profession: str
    cohort_id: str
    cohort_label: str
    region_id: str
    region_label: str
    bio: str
    persona: str
    mbti: str
    language_preference: list[str]
    listening_context: str
    primary_drivers: list[str]
    drivers: dict[str, str]
    driver_intensity: dict[str, float]
    genre_affinity: dict[str, float]
    interested_topics: list[str]
    avg_daily_minutes: int
    session_minutes: int
    session_pattern: str
    gap_hours: int
    coin_spend_tier: str
    historical_completion: float
    tenure_months: int
    playback_speed: float
    listening_privacy: str
    interruption_load: str
    discovery_channel: str
    exploration_propensity: float
    narrative_patience: float
    churn_sensitivity: float
    pay_threshold: float
    commitment_tolerance: int
    binge_speed: int
    language_register: str
    anti_stereotype: str


@dataclass(frozen=True)
class PersonaState:
    persona_id: str
    episodes_heard: int
    active: bool
    dropped_at: str | None
    story_summary: str
    unresolved_questions: list[str]
    payoff_trust: float
    agency_trust: float
    coins_spent: int


@dataclass(frozen=True)
class Reaction:
    run_id: str
    persona_id: str
    cohort: str
    episode_no: int
    will_continue: bool
    continue_reason: str
    would_pay: bool
    pay_reason: str
    drop_beat: str | None
    craving_mid: int
    craving_end: int
    next_prediction: str
    emotional_state: str
    felt_emotion: str
    emotion_shift: str
    judgement_bridge: str
    decision_factors: list[str]
    engagement_score: float
    pay_pressure: float
    signal_json: dict[str, float]
    state_json: dict[str, Any]
    judgement_agent: str = ""
    judgement_changed: bool = False
    judgement_notes: str = ""
    raw_reaction_json: dict[str, Any] | None = None


REACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "will_continue": {"type": "boolean"},
        "continue_reason": {"type": "string"},
        "would_pay": {"type": "boolean"},
        "pay_reason": {"type": "string"},
        "drop_beat": {"type": ["string", "null"]},
        "craving_mid": {"type": "integer", "minimum": 1, "maximum": 10},
        "craving_end": {"type": "integer", "minimum": 1, "maximum": 10},
        "next_prediction": {"type": "string"},
        "emotional_state": {"type": "string"},
        "felt_emotion": {"type": "string"},
        "emotion_shift": {"type": "string"},
        "judgement_bridge": {"type": "string"},
        "decision_factors": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "maxItems": 5,
        },
    },
    "required": [
        "will_continue",
        "continue_reason",
        "would_pay",
        "pay_reason",
        "drop_beat",
        "craving_mid",
        "craving_end",
        "next_prediction",
        "emotional_state",
        "felt_emotion",
        "emotion_shift",
        "judgement_bridge",
        "decision_factors",
    ],
    "additionalProperties": False,
}
