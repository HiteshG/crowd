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
    episode_intelligence: dict[str, Any] | None = None,
    decision_seed: int | None = None,
) -> dict[str, Any]:
    """Build the payload shape for replacing the heuristic engine with an LLM."""
    cohort_card = json.dumps(INDIA_ENGLISH_COHORT_CARD, ensure_ascii=False, indent=2)
    schema = json.dumps(REACTION_SCHEMA, indent=2)
    intelligence_note = ""
    if episode_intelligence:
        intelligence_note = (
            "\nEpisode Intelligence structural prior is included in the user payload. "
            "Use it as audit evidence: beat churn risks, cohort-fit rank, cognitive load, "
            "promise movement, and ending taxonomy. You may disagree with it only if the "
            "persona and script evidence support the disagreement.\n"
        )
    system = (
        "You are simulating one India-based English/Hinglish audio-fiction listener.\n"
        "The listener is not rating quality. They are making behavioral decisions: "
        "continue/drop, pay/do not pay, attention drop beat, craving, prediction.\n"
        "Continue means the listener actively starts the next episode in their normal "
        "listening window. It does not mean they are vaguely curious, appreciate the "
        "writing, or might return someday.\n"
        "Use the persona's bio, MBTI, listening setting, need-region, payment tier, "
        "patience, churn sensitivity, language register, and interests as constraints.\n"
        "Be willing to drop or refuse payment when the episode does not satisfy that "
        "listener's actual use case.\n"
        "Unresolved questions are not automatic retention. The current episode must create "
        "enough fresh pull, payoff trust, or emotional/genre fit to beat the listener's "
        "opportunity cost.\n"
        "Avoid panel-wide politeness bias: do not keep a persona active just because the "
        "story is coherent or because one plot question remains. High-churn, low-patience, "
        "poor-fit, distracted, paywall-skeptical, or low-trust personas should drop when "
        "their actual next-play motivation is weak.\n"
        "If craving_end is lower than craving_mid and will_continue is true, the reason must "
        "name a specific next-episode hook strong enough to overcome the drop pressure. If "
        "there is no such hook in the episode or listener state, will_continue should be false.\n"
        "Reasoning fields must be sharp and behavior-facing:\n"
        "- felt_emotion: the dominant end-of-episode feeling in the persona's voice.\n"
        "- emotion_shift: how the emotion changed from mid-episode to end.\n"
        "- judgement_bridge: the one causal bridge from emotion to continue/drop/pay decision.\n"
        "- decision_factors: 2-5 short concrete factors, each grounded in persona traits, "
        "state, episode beat labels, or Episode Intelligence. Avoid generic praise.\n"
        "Use decision_seed only as a reproducible tie-breaker when the persona could "
        "plausibly go either way; never mention it in user-facing reasons.\n"
        "A drop decision must be grounded in at least one behavioral cause: cohort mismatch, "
        "a beat-level churn risk, a tripped dealbreaker, cognitive load for the listening "
        "setting, delayed payoff, weak ending gate, trust erosion, or low craving.\n"
        "If will_continue is true, drop_beat must be null. If will_continue is false, "
        "drop_beat must be one beat_id from the beat map, not a sentence or future condition.\n\n"
        "Do not invent absent story layers. Mention career, office, romance, status ladder, "
        "professional rivals, supernatural lore, or family inheritance only if they appear in "
        "the episode script or listener state.\n"
        f"{intelligence_note}\n"
        f"Cohort card:\n{cohort_card}\n\n"
        f"Episode {episode.episode_no}: {episode.title}\n"
        f"Beat map:\n{format_beat_map(episode)}\n\n"
        f"Return only JSON matching this schema:\n{schema}"
    )
    user = {
        "persona": dataclasses.asdict(persona),
        "listener_state": dataclasses.asdict(state),
        "decision_seed": decision_seed,
        "behavioral_calibration": behavioral_calibration(persona, state, episode, episode_intelligence),
        "episode_script": episode.text,
        "episode_intelligence": compact_episode_intelligence(episode_intelligence),
    }
    return {
        "system": system,
        "messages": [{"role": "user", "content": json.dumps(user, ensure_ascii=False)}],
        "response_format": REACTION_SCHEMA,
    }


def behavioral_calibration(
    persona: Persona,
    state: PersonaState,
    episode: Episode,
    episode_intelligence: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compact churn-context for the LLM. It informs judgement; it does not decide."""
    ranking = persona_region_ranking(persona, episode_intelligence)
    ending = (episode_intelligence or {}).get("ending", {})
    weak_gate = ending.get("paywall_verdict") == "resolved_no_gate" or ending.get("taxonomy") in {
        "resolved_no_hook",
        "other",
    }
    risk_reasons: list[str] = []
    risk_score = 0.0
    if ranking:
        rank = int(ranking.get("rank", 6))
        if rank >= 5:
            risk_score += 0.26
            risk_reasons.append(f"low region fit rank {rank}")
        elif rank == 4:
            risk_score += 0.14
            risk_reasons.append("borderline region fit")
        abandon_pressure = float(ranking.get("abandon_pressure", 0.0))
        if abandon_pressure >= 0.40:
            risk_score += 0.18
            risk_reasons.append(f"episode intelligence abandon pressure {abandon_pressure:.2f}")
    if weak_gate:
        risk_score += 0.18
        risk_reasons.append("ending has weak or resolved gate")
    if state.payoff_trust < 0.30 and episode.episode_no >= 3:
        risk_score += 0.18
        risk_reasons.append(f"low carried payoff trust {state.payoff_trust:.2f}")
    if state.agency_trust < 0.35 and episode.episode_no >= 3:
        risk_score += 0.08
        risk_reasons.append(f"low carried agency trust {state.agency_trust:.2f}")
    churn_gap = persona.churn_sensitivity - persona.narrative_patience
    if churn_gap >= 0.20:
        risk_score += 0.16
        risk_reasons.append("churn sensitivity materially exceeds patience")
    elif churn_gap >= 0.05:
        risk_score += 0.08
        risk_reasons.append("churn sensitivity slightly exceeds patience")
    if persona.interruption_load == "high" and (episode_intelligence or {}).get("narrative_anatomy", {}).get("cognitive_load", {}).get("load_tier") == "high":
        risk_score += 0.10
        risk_reasons.append("high interruption load with high cognitive load")
    if episode.episode_no >= 6 and state.payoff_trust < 0.35:
        risk_score += 0.12
        risk_reasons.append("late-run promise fatigue risk")

    continue_bar = "high" if risk_score >= 0.55 else "medium" if risk_score >= 0.30 else "normal"
    return {
        "meaning": (
            "Decision prior for next-play behavior. The LLM should use story evidence and "
            "persona judgement, but this prevents treating generic curiosity as retention."
        ),
        "episode_stage": episode_stage_label(episode.episode_no),
        "persona_region_rank": ranking.get("rank") if ranking else None,
        "persona_region_fit_score": ranking.get("relative_fit_score") if ranking else None,
        "most_likely_abandon_beat": ranking.get("most_likely_abandon_beat") if ranking else None,
        "risk_flag": ranking.get("risk_flag") if ranking else None,
        "ending_taxonomy": ending.get("taxonomy"),
        "ending_gate": ending.get("paywall_verdict"),
        "continue_bar": continue_bar,
        "drop_pressure_reasons": risk_reasons[:6],
        "persona_churn_sensitivity": persona.churn_sensitivity,
        "persona_narrative_patience": persona.narrative_patience,
        "payoff_trust": state.payoff_trust,
        "agency_trust": state.agency_trust,
        "episodes_heard": state.episodes_heard,
    }


def persona_region_ranking(
    persona: Persona,
    episode_intelligence: dict[str, Any] | None,
) -> dict[str, Any]:
    if not episode_intelligence:
        return {}
    for row in episode_intelligence.get("cohort_fit_rankings", []):
        if row.get("region_id") == persona.region_id:
            return row
    return {}


def episode_stage_label(episode_no: int) -> str:
    if episode_no == 1:
        return "opening_hook"
    if episode_no <= 3:
        return "premise_validation"
    if episode_no <= 6:
        return "mid_run_endurance"
    return "endgame"


def compact_episode_intelligence(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    return {
        "episode_no": value.get("episode_no"),
        "title": value.get("title"),
        "narrative_anatomy": value.get("narrative_anatomy"),
        "driver_scores": value.get("driver_scores"),
        "ending": value.get("ending"),
        "drop_science": value.get("drop_science"),
        "cohort_fit_rankings": value.get("cohort_fit_rankings"),
        "beat_table": [
            {
                "beat_id": row.get("beat_id"),
                "label": row.get("label"),
                "line_start": row.get("line_start"),
                "line_end": row.get("line_end"),
                "generator": row.get("generator"),
                "speaker_focus": row.get("speaker_focus"),
                "purpose": row.get("purpose"),
                "heuristic_purpose": row.get("heuristic_purpose"),
                "emotional_intensity": row.get("emotional_intensity"),
                "suspense": row.get("suspense"),
                "churn_risk": row.get("churn_risk"),
                "risk_score": row.get("risk_score"),
                "dealbreaker_ids": row.get("dealbreaker_ids"),
                "removable": row.get("removable"),
                "note": row.get("note"),
                "quote": row.get("quote"),
                "llm_audience_decision_risk": row.get("llm_audience_decision_risk"),
                "llm_risk_reason": row.get("llm_risk_reason"),
                "llm_evidence_quote": row.get("llm_evidence_quote"),
                "craving_effect": row.get("craving_effect"),
            }
            for row in value.get("beat_table", [])
        ],
    }
