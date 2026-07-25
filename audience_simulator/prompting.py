from __future__ import annotations

import dataclasses
import json
from typing import Any

from .cohorts import INDIA_ENGLISH_COHORT_CARD
from .ingest import format_beat_map
from .models import Episode, Persona, PersonaState, REACTION_SCHEMA


def build_llm_reaction_payload(
    persona: Persona,
    state: PersonaState,
    episode: Episode,
) -> dict[str, Any]:
    """Build the payload shape for replacing the heuristic engine with an LLM."""
    cohort_card = json.dumps(INDIA_ENGLISH_COHORT_CARD, ensure_ascii=False, indent=2)
    schema = json.dumps(REACTION_SCHEMA, indent=2)
    system = (
        "You are simulating one India-based English/Hinglish audio-fiction listener.\n"
        "The listener is not rating quality. They are making behavioral decisions: "
        "continue/drop, pay/do not pay, attention drop beat, craving, prediction.\n"
        "Use the persona's bio, MBTI, listening setting, need-region, payment tier, "
        "patience, churn sensitivity, language register, and interests as constraints.\n"
        "Be willing to drop or refuse payment when the episode does not satisfy that "
        "listener's actual use case.\n\n"
        f"Cohort card:\n{cohort_card}\n\n"
        f"Episode {episode.episode_no}: {episode.title}\n"
        f"Beat map:\n{format_beat_map(episode)}\n\n"
        f"Return only JSON matching this schema:\n{schema}"
    )
    user = {
        "persona": dataclasses.asdict(persona),
        "listener_state": dataclasses.asdict(state),
        "episode_script": episode.text,
    }
    return {
        "system": system,
        "messages": [{"role": "user", "content": json.dumps(user, ensure_ascii=False)}],
        "response_format": REACTION_SCHEMA,
    }
