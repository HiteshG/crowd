from __future__ import annotations

import hashlib
import random
from typing import Any

from .cohorts import NEED_REGIONS
from .models import Beat, Episode, Persona, PersonaState
from .signals import KEYWORDS, episode_signals, term_score
from .utils import clamp, word_count


def build_episode_intelligence(episodes: list[Episode]) -> dict[int, dict[str, Any]]:
    intelligence: dict[int, dict[str, Any]] = {}
    promise_ledger: list[dict[str, Any]] = []
    for episode in episodes:
        item = analyze_episode(episode, promise_ledger)
        intelligence[episode.episode_no] = item
        promise_ledger = item["updated_promise_ledger"]
    return intelligence


def analyze_episode(episode: Episode, promise_ledger: list[dict[str, Any]]) -> dict[str, Any]:
    signals = episode_signals(episode)
    beat_rows = [analyze_beat(beat) for beat in episode.beats]
    updated_ledger = update_promise_ledger(episode, promise_ledger, beat_rows)
    driver_rows = driver_scores(signals, episode)
    ending = ending_analysis(episode, signals)
    cohort_rankings = cohort_fit_rankings(driver_rows, beat_rows, ending)
    beat_source = "llm" if any(beat.generator == "llm" for beat in episode.beats) else "parser"
    return {
        "episode_no": episode.episode_no,
        "title": episode.title,
        "beat_source": beat_source,
        "narrative_anatomy": narrative_anatomy(episode, signals, beat_rows),
        "driver_scores": driver_rows,
        "beat_table": beat_rows,
        "ending": ending,
        "cohort_fit_rankings": cohort_rankings,
        "updated_promise_ledger": updated_ledger,
        "drop_science": drop_science_note(),
        "confidence": "medium",
        "confidence_note": (
            "LLM beat segmentation with heuristic scoring and cohort-fit audit; use as structural prior, not calibrated truth."
            if beat_source == "llm"
            else "Heuristic Episode Intelligence pass; use as structural prior, not calibrated truth."
        ),
    }


def narrative_anatomy(
    episode: Episode,
    signals: dict[str, float],
    beat_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    new_entities = sorted(extract_candidate_entities(episode.text))[:12]
    agency_level = "drives" if signals["agency"] >= signals["passive"] else "reacts"
    status_delta = "clear escalation" if signals["cliffhanger"] >= 0.25 else "soft progression"
    if signals["resolved_no_hook"] >= 0.5:
        status_delta = "tension discharged"
    return {
        "core_conflict": infer_core_conflict(signals),
        "protagonist_agency": agency_level,
        "agency_cited_moment": first_matching_beat(beat_rows, {"agency", "passive"}),
        "status_quo_delta": status_delta,
        "cognitive_load": {
            "candidate_entities": new_entities,
            "new_entity_count": len(new_entities),
            "load_tier": "high" if len(new_entities) >= 9 else "medium" if len(new_entities) >= 5 else "low",
        },
    }


def analyze_beat(beat: Beat) -> dict[str, Any]:
    scores = {name: term_score(beat.text, terms, scale=2.0) for name, terms in KEYWORDS.items()}
    heuristic_purpose = beat_purpose(scores, beat.text)
    purpose = normalized_llm_purpose(beat.purpose) or heuristic_purpose
    heuristic_emotional_intensity = round(
        1
        + 9
        * clamp(
            (
                scores["family"]
                + scores["humiliation"]
                + scores["romance"]
                + scores["vindication"]
                + scores["agency"]
            )
            / 2.6,
            0.0,
            1.0,
        )
    )
    heuristic_suspense = round(
        1
        + 9
        * clamp(
            (
                scores["cliffhanger"]
                + scores["humiliation"]
                + scores["status"]
                + scores["exposition"] * 0.25
            )
            / 1.7,
            0.0,
            1.0,
        )
    )
    emotional_intensity = blended_beat_score(beat.emotional_intensity, heuristic_emotional_intensity)
    suspense = blended_beat_score(beat.suspense, heuristic_suspense)
    churn_risk, risk_score, dealbreakers = beat_churn_risk(scores, purpose, beat.text)
    churn_risk, risk_score, dealbreakers = apply_llm_risk_prior(
        beat,
        churn_risk,
        risk_score,
        dealbreakers,
    )
    return {
        "beat_id": beat.beat_id,
        "label": beat.label,
        "line_start": beat.line_start,
        "line_end": beat.line_end,
        "generator": beat.generator,
        "speaker_focus": list(beat.speaker_focus),
        "quote": compact(beat.text, 260),
        "purpose": purpose,
        "heuristic_purpose": heuristic_purpose,
        "emotional_intensity": int(emotional_intensity),
        "suspense": int(suspense),
        "info_revealed": info_revealed(scores, beat.text),
        "churn_risk": churn_risk,
        "risk_score": round(risk_score, 4),
        "dealbreaker_ids": dealbreakers,
        "removable": purpose == "none" and risk_score >= 0.45,
        "note": beat.risk_reason or beat_note(churn_risk, scores),
        "llm_audience_decision_risk": beat.audience_decision_risk,
        "llm_risk_reason": beat.risk_reason,
        "llm_evidence_quote": beat.evidence_quote,
        "craving_effect": beat.craving_effect,
    }


def normalized_llm_purpose(value: str) -> str:
    return value if value in {"reveal", "escalate", "reverse", "complicate", "payoff", "none"} else ""


def blended_beat_score(llm_value: int | None, heuristic_value: int) -> int:
    if llm_value is None:
        return int(heuristic_value)
    return int(round((2 * int(clamp(llm_value, 1, 10)) + heuristic_value) / 3))


def apply_llm_risk_prior(
    beat: Beat,
    churn_risk: str,
    risk_score: float,
    dealbreakers: list[str],
) -> tuple[str, float, list[str]]:
    risk = beat.audience_decision_risk
    if not risk or risk == "none":
        return churn_risk, risk_score, dealbreakers
    pressure_by_risk = {
        "boredom": 0.34,
        "confusion": 0.36,
        "payoff_delay": 0.42,
        "weak_gate": 0.38,
        "tonal_break": 0.32,
        "dealbreaker": 0.46,
    }
    churn_by_risk = {
        "boredom": "boredom",
        "confusion": "confusion",
        "payoff_delay": "dealbreaker:D_payoff_delay",
        "weak_gate": "dealbreaker:D_weak_gate",
        "tonal_break": "dealbreaker:D_tonal_break",
        "dealbreaker": "dealbreaker:D_llm_flag",
    }
    dealbreaker_by_risk = {
        "payoff_delay": "D_payoff_delay",
        "weak_gate": "D_weak_gate",
        "tonal_break": "D_tonal_break",
        "dealbreaker": "D_llm_flag",
    }
    llm_pressure = pressure_by_risk.get(risk, 0.0)
    if llm_pressure > risk_score:
        churn_risk = churn_by_risk.get(risk, churn_risk)
        risk_score = llm_pressure
    dealbreaker = dealbreaker_by_risk.get(risk)
    if dealbreaker and dealbreaker not in dealbreakers:
        dealbreakers.append(dealbreaker)
    return churn_risk, risk_score, dealbreakers


def beat_purpose(scores: dict[str, float], text: str) -> str:
    lower = text.lower()
    reveal_terms = [
        "found",
        "revealed",
        "truth",
        "evidence",
        "phone",
        "sim card",
        "gps",
        "bleach",
        "jacket",
        "courier",
        "brother",
        "warrant",
    ]
    threat_terms = [
        "blood",
        "dead",
        "body",
        "knife",
        "police",
        "inspector",
        "search warrant",
        "digging",
        "compost pit",
        "wail",
        "scream",
        "knock",
        "open the door",
    ]
    if scores["vindication"] >= 0.25 or any(term in lower for term in reveal_terms):
        return "reveal"
    if scores["cliffhanger"] >= 0.25 or scores["humiliation"] >= 0.25 or any(term in lower for term in threat_terms):
        return "escalate"
    if any(term in lower for term in ["but", "however", "instead", "suddenly", "until"]):
        return "reverse"
    if scores["exposition"] >= 0.22 or scores["status"] >= 0.22:
        return "complicate"
    if scores["agency"] >= 0.25 or scores["competence"] >= 0.25:
        return "payoff"
    return "none"


def beat_churn_risk(
    scores: dict[str, float],
    purpose: str,
    text: str,
) -> tuple[str, float, list[str]]:
    dealbreakers: list[str] = []
    length_boredom = 0.26 if word_count(text) > 85 and purpose == "none" else 0.0
    boredom = clamp(scores["filler"] * 0.46 + length_boredom, 0.0, 1.0)
    confusion = clamp(scores["exposition"] * 0.42 + (0.18 if entity_count(text) >= 6 else 0.0), 0.0, 1.0)
    agency_gap = clamp(scores["passive"] * 0.50 - scores["agency"] * 0.18, 0.0, 1.0)
    regressive = scores["regressive"] * 0.62
    movement_score = max(
        scores["cliffhanger"],
        scores["agency"],
        scores["competence"],
        scores["family"],
        scores["romance"],
        scores["status"],
        scores["humiliation"],
        scores["vindication"],
    )
    sfx_only = text.strip().startswith("[SFX:") and "**" not in text
    weak_promise = (
        0.18
        if not sfx_only and purpose == "none" and word_count(text) >= 14 and movement_score < 0.12
        else 0.0
    )
    risks = {
        "boredom": boredom,
        "confusion": confusion,
        "dealbreaker:D_agency_gap": agency_gap,
        "dealbreaker:D_regressive_frame": regressive,
        "dealbreaker:D_payoff_delay": weak_promise,
    }
    label, score = max(risks.items(), key=lambda item: item[1])
    if agency_gap >= 0.22:
        dealbreakers.append("D_agency_gap")
    if regressive >= 0.18:
        dealbreakers.append("D_regressive_frame")
    if weak_promise >= 0.18:
        dealbreakers.append("D_payoff_delay")
    if score < 0.18:
        return "none", 0.0, dealbreakers
    return label, score, dealbreakers


def driver_scores(signals: dict[str, float], episode: Episode) -> dict[str, dict[str, str]]:
    driver_signal = {
        "identity": max(signals["agency"], signals["urban_modern"], signals["status"]),
        "wish_fulfillment": max(signals["status"], signals["romance"], signals["competence"]),
        "escapism": max(signals["cliffhanger"], signals["event_density"]),
        "justice_seeking": max(signals["humiliation"], signals["public_vindication"]),
        "comfort": max(signals["family"], signals["romance"]) * (1.0 - signals["ending_cliffhanger"] * 0.35),
        "catharsis": max(signals["family"], signals["public_vindication"], signals["vindication"]),
        "belonging": max(signals["family"], signals["romance"]),
        "power_fantasy": max(signals["status"], signals["competence"], signals["public_vindication"]),
    }
    rows: dict[str, dict[str, str]] = {}
    for driver, score in driver_signal.items():
        if score >= 0.42:
            tier = "High"
        elif score >= 0.18:
            tier = "Med"
        else:
            tier = "Low"
        rows[driver] = {
            "tier": tier,
            "citation": citation_for_driver(driver, episode),
        }
    return rows


def ending_analysis(episode: Episode, signals: dict[str, float]) -> dict[str, Any]:
    ending_text = episode.beats[-1].text if episode.beats else episode.text
    ending_beat = episode.beats[-1] if episode.beats else None
    lower = ending_text.lower()
    taxonomy = "other"
    if llm_marks_resolved_or_weak_gate(ending_beat):
        taxonomy = "resolved_no_hook"
    elif any(term in lower for term in ["knife", "gun", "attack", "stab", "shoot", "kill"]) or (
        signals["ending_cliffhanger"] >= 0.35 and any(term in lower for term in ["before", "mid", "suddenly"])
    ):
        taxonomy = "interrupted_action"
    elif any(
        term in lower
        for term in [
            "knock",
            "knocks",
            "door opened",
            "door opens",
            "doorbell",
            "open the door",
            "police",
            "coming",
            "outside",
            "confront",
            "warrant",
        ]
    ):
        taxonomy = "imminent_confrontation"
    elif any(term in lower for term in ["she didn't know", "he didn't know", "unaware"]):
        taxonomy = "dramatic_irony"
    elif any(term in lower for term in ["phone", "buzzing", "message", "photo", "saw", "read", "opened"]) and (
        "what" in lower or "phone" in lower or "buzzing" in lower
    ):
        taxonomy = "withheld_sight"
    elif any(term in lower for term in ["secret", "truth", "exposed", "reveal"]):
        taxonomy = "exposure_threat"
    elif any(term in lower for term in ["betray", "ally", "enemy"]):
        taxonomy = "alliance_inversion"
    elif signals["ending_status_reveal"] >= 0.35:
        taxonomy = "status_reveal_tease"
    elif signals["resolved_no_hook"] >= 0.50 or weak_or_resolved_final_beat(signals):
        taxonomy = "resolved_no_hook"
    if signals["ending_cliffhanger"] >= 0.35 and signals["ending_status_reveal"] >= 0.35:
        taxonomy = "multi_hook"
    action_end_bonus = 0.75 if taxonomy in {"interrupted_action", "imminent_confrontation", "exposure_threat", "multi_hook"} else 0.0
    strength = round(1 + 9 * clamp(max(signals["ending_cliffhanger"], signals["ending_status_reveal"], signals["ending_romance_pressure"], signals["resolved_no_hook"] * 0.35, action_end_bonus), 0.0, 1.0))
    paywall_verdict = {
        "interrupted_action": "crisis_cliffhanger",
        "imminent_confrontation": "crisis_cliffhanger",
        "dramatic_irony": "crisis_cliffhanger",
        "withheld_sight": "crisis_cliffhanger",
        "exposure_threat": "status_reveal",
        "alliance_inversion": "status_reveal",
        "status_reveal_tease": "status_reveal",
        "resolved_no_hook": "resolved_no_gate",
        "multi_hook": "crisis_cliffhanger",
        "other": "resolved_no_gate" if signals["resolved_no_hook"] >= 0.5 else "crisis_cliffhanger",
    }[taxonomy]
    return {
        "taxonomy": taxonomy,
        "strength": int(strength),
        "novelty": "unknown_without_comparison",
        "paywall_verdict": paywall_verdict,
        "citation": compact(ending_text, 220),
    }


def llm_marks_resolved_or_weak_gate(ending_beat: Beat | None) -> bool:
    if not ending_beat or ending_beat.generator != "llm":
        return False
    return (
        ending_beat.audience_decision_risk in {"weak_gate", "tonal_break"}
        and ending_beat.craving_effect in {"holds", "lowers"}
        and ending_beat.purpose in {"payoff", "reverse", "none"}
    )


def weak_or_resolved_final_beat(signals: dict[str, float]) -> bool:
    return (
        signals.get("ending_cliffhanger", 0.0) < 0.10
        and signals.get("ending_status_reveal", 0.0) < 0.20
        and signals.get("ending_romance_pressure", 0.0) < 0.20
    )


def cohort_fit_rankings(
    driver_rows: dict[str, dict[str, str]],
    beat_rows: list[dict[str, Any]],
    ending: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for region_id, region in NEED_REGIONS.items():
        driver_fit = region_driver_fit(region.drivers, driver_rows)
        patience_penalty = cohort_patience_penalty(region_id, beat_rows)
        ending_bonus = cohort_ending_bonus(region_id, ending)
        risk_row = cohort_abandon_beat(region_id, beat_rows, ending)
        score = clamp(driver_fit + ending_bonus - patience_penalty - risk_row["abandon_pressure"] * 0.18, 0.0, 1.0)
        rows.append(
            {
                "region_id": region_id,
                "region": region.label,
                "relative_fit_score": round(score, 4),
                "risk_flag": risk_row["risk_flag"],
                "most_likely_abandon_beat": risk_row["beat_id"],
                "abandon_pressure": risk_row["abandon_pressure"],
                "reason": cohort_reason(region.label, driver_fit, ending, risk_row),
            }
        )
    ranked = sorted(rows, key=lambda item: item["relative_fit_score"], reverse=True)
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return ranked


def region_driver_fit(region_drivers: dict[str, str], driver_rows: dict[str, dict[str, str]]) -> float:
    tier_value = {"Low": 0.15, "Med": 0.55, "High": 0.90}
    need_value = {"low": 0.25, "medium": 0.55, "high": 0.78, "very_high": 0.96}
    if not region_drivers:
        return 0.35
    scores = []
    for driver, importance in region_drivers.items():
        observed = tier_value.get(driver_rows.get(driver, {}).get("tier", "Low"), 0.15)
        needed = need_value.get(importance, 0.55)
        scores.append(1.0 - abs(needed - observed))
    return sum(scores) / len(scores)


def cohort_patience_penalty(region_id: str, beat_rows: list[dict[str, Any]]) -> float:
    removable_count = sum(1 for row in beat_rows if row["removable"])
    avg_risk = sum(row["risk_score"] for row in beat_rows) / max(1, len(beat_rows))
    multiplier = 1.30 if region_id == "high_churn_thrill_chasers" else 0.70 if region_id == "slow_burn_comfort_seekers" else 1.0
    return clamp((0.05 * removable_count + 0.25 * avg_risk) * multiplier, 0.0, 0.40)


def cohort_ending_bonus(region_id: str, ending: dict[str, Any]) -> float:
    taxonomy = ending["taxonomy"]
    strength = ending["strength"] / 10.0
    if region_id == "high_churn_thrill_chasers":
        return 0.18 * strength if taxonomy in {"interrupted_action", "imminent_confrontation", "multi_hook"} else -0.08
    if region_id == "justice_payoff_bingers":
        return 0.14 * strength if taxonomy in {"exposure_threat", "multi_hook", "imminent_confrontation"} else 0.0
    if region_id == "status_progression_loyalists":
        return 0.16 * strength if taxonomy in {"status_reveal_tease", "exposure_threat", "multi_hook"} else -0.05
    if region_id in {"household_catharsis_devotees", "slow_burn_comfort_seekers"}:
        return 0.10 * strength if taxonomy in {"resolved_no_hook", "dramatic_irony"} else 0.02
    return 0.08 * strength


def cohort_abandon_beat(
    region_id: str,
    beat_rows: list[dict[str, Any]],
    ending: dict[str, Any],
) -> dict[str, Any]:
    if not beat_rows:
        return {"beat_id": None, "risk_flag": "none", "abandon_pressure": 0.0}
    scored = []
    for row in beat_rows:
        pressure = row["risk_score"]
        if region_id == "high_churn_thrill_chasers" and row["suspense"] <= 3 and row["purpose"] == "none":
            pressure += 0.22
        if region_id == "tier1_aspirational_escapists" and row["purpose"] == "none":
            pressure += 0.12
        if region_id in {"household_catharsis_devotees", "slow_burn_comfort_seekers"} and row["churn_risk"] == "confusion":
            pressure += 0.10
        if region_id == "justice_payoff_bingers" and "D_payoff_delay" in row["dealbreaker_ids"]:
            pressure += 0.16
        scored.append((row, clamp(pressure, 0.0, 1.0)))
    beat, pressure = max(scored, key=lambda item: item[1])
    if ending["taxonomy"] in {"resolved_no_hook", "other"} and region_id == "high_churn_thrill_chasers":
        pressure = clamp(pressure + 0.12, 0.0, 1.0)
    return {
        "beat_id": beat["beat_id"],
        "risk_flag": beat["churn_risk"],
        "abandon_pressure": round(pressure, 4),
    }


def persona_drop_guardrail(
    *,
    persona: Persona,
    state: PersonaState,
    episode: Episode,
    episode_intelligence: dict[str, Any] | None,
    llm_result: dict[str, Any],
    seed: int,
    run_id: str,
) -> dict[str, Any]:
    if not episode_intelligence:
        return {"should_drop": False, "pressure": 0.0, "threshold": 1.0, "beat_id": None, "reason": "no episode intelligence"}

    ranking = next(
        (
            row
            for row in episode_intelligence.get("cohort_fit_rankings", [])
            if row.get("region_id") == persona.region_id
        ),
        None,
    )
    beat_rows = {row["beat_id"]: row for row in episode_intelligence.get("beat_table", [])}
    beat_id = ranking.get("most_likely_abandon_beat") if ranking else None
    beat = beat_rows.get(beat_id) if beat_id else None
    rank = int(ranking.get("rank", len(NEED_REGIONS))) if ranking else len(NEED_REGIONS)
    abandon_pressure = float(ranking.get("abandon_pressure", 0.0)) if ranking else 0.0
    ending_strength = float(episode_intelligence.get("ending", {}).get("strength", 1)) / 10.0
    craving_delta = int(llm_result.get("craving_end", 5)) - int(llm_result.get("craving_mid", 5))
    craving_end = int(llm_result.get("craving_end", 5))

    components = {
        "baseline": 0.20,
        "beat_abandon_pressure": 0.42 * abandon_pressure,
        "cohort_mismatch_rank": 0.07 * max(0, rank - 3),
        "persona_churn_sensitivity": 0.12 * persona.churn_sensitivity,
        "low_narrative_patience": 0.08 * (1.0 - persona.narrative_patience),
        "payoff_trust_deficit": 0.07 * (1.0 - state.payoff_trust),
        "agency_trust_deficit": 0.05 * (1.0 - state.agency_trust),
    }
    if persona.interruption_load == "high" and episode_intelligence["narrative_anatomy"]["cognitive_load"]["load_tier"] == "high":
        components["interruption_x_cognitive_load"] = 0.08
    if persona.region_id == "high_churn_thrill_chasers" and ending_strength < 0.60:
        components["thrill_chaser_weak_ending"] = 0.13
    if persona.region_id == "tier1_aspirational_escapists" and rank >= 5:
        components["aspirational_cohort_mismatch"] = 0.10
    if craving_delta <= -1:
        components["negative_craving_delta"] = 0.08
    if craving_end <= 5:
        components["low_end_craving"] = 0.08
    if episode.episode_no == 1 and ending_strength >= 0.70:
        components["opener_crisis_elasticity"] = -0.12
    if episode.episode_no <= 2 and ending_strength >= 0.70 and craving_end >= 6:
        components["early_hook_protection"] = -0.10
    if ending_strength >= 0.75 and craving_end >= 7:
        components["strong_cliffhanger_craving_protection"] = -0.12
    if craving_end >= 8 and rank <= 3:
        components["high_craving_protection"] = -0.12

    rng = random.Random(hashlib.sha256(f"{seed}:{run_id}:{persona.persona_id}:{episode.episode_no}:guardrail".encode("utf-8")).hexdigest())
    jitter = rng.uniform(-0.055, 0.055)
    components["seeded_jitter"] = jitter
    pressure = sum(components.values())
    pressure = clamp(pressure, 0.0, 1.0)
    base_threshold = clamp(0.68 + 0.16 * persona.narrative_patience - 0.18 * persona.churn_sensitivity, 0.42, 0.82)
    override_margin = 0.0
    if craving_end >= 7:
        override_margin += 0.08
    if episode.episode_no == 1:
        override_margin += 0.06
    threshold = clamp(base_threshold + override_margin, 0.42, 0.95)
    should_drop = pressure >= threshold
    if not should_drop and rank == len(NEED_REGIONS) and abandon_pressure >= 0.58 and persona.churn_sensitivity >= 0.68:
        should_drop = True

    return {
        "should_drop": should_drop,
        "pressure": round(pressure, 4),
        "threshold": round(threshold, 4),
        "base_threshold": round(base_threshold, 4),
        "override_margin": round(override_margin, 4),
        "beat_id": beat_id,
        "reason": guardrail_reason(persona, ranking, beat),
        "rank": float(rank),
        "abandon_pressure": round(abandon_pressure, 4),
        "cohort_fit": round(float(ranking.get("relative_fit_score", 0.0)) if ranking else 0.0, 4),
        "components": {key: round(value, 4) for key, value in components.items()},
    }


def guardrail_reason(
    persona: Persona,
    ranking: dict[str, Any] | None,
    beat: dict[str, Any] | None,
) -> str:
    if not ranking or not beat:
        return "episode intelligence did not find a stable cohort fit"
    return (
        f"{persona.region_label} ranks {ranking['rank']} for this episode; "
        f"beat {beat['beat_id']} carries {beat['churn_risk']} risk: {beat['note']}"
    )


def update_promise_ledger(
    episode: Episode,
    promise_ledger: list[dict[str, Any]],
    beat_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ledger = [dict(item) for item in promise_ledger]
    lower = episode.text.lower()
    if any(term in lower for term in ["secret", "truth", "who", "why", "where", "police", "evidence"]):
        promise_id = f"p{episode.episode_no:03d}_{len(ledger) + 1:02d}"
        ledger.append(
            {
                "promise_id": promise_id,
                "text": "unresolved secret/threat/evidence question",
                "introduced_ep": episode.episode_no,
                "status": "open",
            }
        )
    if any(row["purpose"] == "reveal" for row in beat_rows):
        for item in ledger[-3:]:
            if item["status"] == "open":
                item["status"] = "advanced"
                break
    return ledger[-8:]


def drop_science_note() -> dict[str, Any]:
    return {
        "unit": "relative structural prior, not calibrated probability",
        "drop_pressure_inputs": [
            "beat-level abandon pressure from churn risk/dealbreaker/filler/confusion",
            "cohort-fit rank for the listener's need-region",
            "persona churn sensitivity and narrative patience",
            "payoff and agency trust carried from prior episodes",
            "listening interruption load x episode cognitive load",
            "LLM craving delta and end craving",
        ],
        "decision_rule": (
            "A listener can drop when structural pressure crosses their persona-specific "
            "threshold; the threshold rises with patience and falls with churn sensitivity."
        ),
        "audience_granularity": (
            "Need-regions remain the six ontology-level demand regions; nuance is added "
            "through occasion cohort, spend tier, city tier, interruption load, language "
            "register, genre affinity, MBTI voice, and persona state."
        ),
    }


def infer_core_conflict(signals: dict[str, float]) -> str:
    if signals["family"] >= 0.25 and signals["cliffhanger"] >= 0.20:
        return "family pressure under threat/mystery escalation"
    if signals["humiliation"] >= 0.20:
        return "humiliation requiring justice or public proof"
    if signals["romance"] >= 0.20:
        return "relationship pressure with unresolved consequence"
    return "serial mystery/threat progression"


def info_revealed(scores: dict[str, float], text: str) -> str:
    if scores["vindication"] >= 0.25 or any(term in text.lower() for term in ["evidence", "truth", "revealed", "found"]):
        return compact(text, 140)
    return ""


def beat_note(churn_risk: str, scores: dict[str, float]) -> str:
    if churn_risk == "boredom":
        return "low event movement or filler risk for impatient listeners"
    if churn_risk == "confusion":
        return "cognitive load rises without enough emotional anchoring"
    if churn_risk == "dealbreaker:D_agency_gap":
        return "listener proxy may feel reactive rather than decisive"
    if churn_risk == "dealbreaker:D_regressive_frame":
        return "family/gender framing may repel modern/agency-sensitive cohorts"
    if churn_risk == "dealbreaker:D_payoff_delay":
        return "promise is delayed without a fresh reward"
    return "no dominant churn risk"


def cohort_reason(
    region_label: str,
    driver_fit: float,
    ending: dict[str, Any],
    risk_row: dict[str, Any],
) -> str:
    return (
        f"{region_label} fit is driven by relative driver match {driver_fit:.2f}, "
        f"ending {ending['taxonomy']} strength {ending['strength']}, "
        f"and abandon risk {risk_row['risk_flag']} at {risk_row['beat_id']}."
    )


def citation_for_driver(driver: str, episode: Episode) -> str:
    driver_terms = {
        "identity": KEYWORDS["agency"] + KEYWORDS["urban_modern"] + KEYWORDS["status"],
        "wish_fulfillment": KEYWORDS["status"] + KEYWORDS["romance"] + KEYWORDS["competence"],
        "escapism": KEYWORDS["cliffhanger"],
        "justice_seeking": KEYWORDS["humiliation"] + KEYWORDS["vindication"],
        "comfort": KEYWORDS["family"] + KEYWORDS["romance"],
        "catharsis": KEYWORDS["family"] + KEYWORDS["vindication"],
        "belonging": KEYWORDS["family"] + KEYWORDS["romance"],
        "power_fantasy": KEYWORDS["status"] + KEYWORDS["competence"],
    }.get(driver, [])
    for beat in episode.beats:
        if term_score(beat.text, driver_terms, scale=2.0) >= 0.15:
            return compact(beat.text, 180)
    return ""


def first_matching_beat(beat_rows: list[dict[str, Any]], risks: set[str]) -> str:
    for row in beat_rows:
        if row["purpose"] in {"payoff", "reveal", "escalate", "reverse"} or any(item in row["churn_risk"] for item in risks):
            return row["quote"]
    return beat_rows[0]["quote"] if beat_rows else ""


def extract_candidate_entities(text: str) -> set[str]:
    stopwords = {
        "accidental",
        "are",
        "blood",
        "bring",
        "breathing",
        "car",
        "coldly",
        "crying",
        "don",
        "driving",
        "everything",
        "extremely",
        "footsteps",
        "gasping",
        "get",
        "good",
        "grunting",
        "hello",
        "hand",
        "heavy",
        "help",
        "house",
        "inside",
        "just",
        "keep",
        "laughing",
        "liquid",
        "look",
        "monday",
        "more",
        "mud",
        "muffled",
        "muttering",
        "mutually",
        "night",
        "now",
        "number",
        "one",
        "open",
        "pack",
        "panting",
        "phone",
        "police",
        "quickly",
        "rain",
        "she",
        "sfx",
        "sobbing",
        "someone",
        "swallow",
        "that",
        "the",
        "then",
        "they",
        "three",
        "two",
        "watch",
    }
    speaker_names = {
        " ".join(part.capitalize() for part in item.split())
        for item in __import__("re").findall(r"\*\*([A-Z][A-Z ]{2,})\*\*", text)
    }
    proper_nouns = {
        item
        for item in __import__("re").findall(r"\b[A-Z][a-z]{2,}\b", text)
        if item.lower() not in stopwords and item.lower() not in {"episode", "chapter", "and", "but"}
    }
    return speaker_names | proper_nouns


def entity_count(text: str) -> int:
    return len(extract_candidate_entities(text))


def compact(text: str, max_chars: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3] + "..."
