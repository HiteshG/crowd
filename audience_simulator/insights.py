from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from .cohorts import LISTENER_SEEDS
from .models import Episode, Persona, Reaction
from .utils import pct


def build_insights(
    episodes: list[Episode],
    reactions: list[Reaction],
    metrics: list[dict[str, Any]],
    personas: list[Persona] | None = None,
    episode_intelligence: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    by_episode: dict[int, list[Reaction]] = defaultdict(list)
    for reaction in reactions:
        by_episode[reaction.episode_no].append(reaction)
    persona_lookup = {persona.persona_id: persona for persona in personas or []}

    beat_lookup = {
        beat.beat_id: {
            "quote": compact(beat.text, 260),
            "label": beat.label,
            "line_start": beat.line_start,
            "line_end": beat.line_end,
            "purpose": beat.purpose,
            "generator": beat.generator,
            "risk": beat.audience_decision_risk,
            "risk_reason": beat.risk_reason,
        }
        for episode in episodes
        for beat in episode.beats
    }
    episode_insights = [
        episode_insight(row, by_episode.get(row["episode_no"], []), beat_lookup)
        for row in metrics
    ]
    reached = [item for item in episode_insights if item["active_before"] > 0]
    all_records = [reaction for records in by_episode.values() for reaction in records]
    drop_records = [reaction for reaction in all_records if not reaction.will_continue]
    continue_records = [reaction for reaction in all_records if reaction.will_continue]
    weighted_voice = weighted_agent_voice(all_records, persona_lookup)
    paywall_rows = paywall_map(metrics, by_episode, persona_lookup)

    strongest_drop = max(
        reached,
        key=lambda item: (item["drop_count"], 1.0 - item["continue_rate"]),
        default=None,
    )
    most_engaged = max(
        reached,
        key=lambda item: (item["continue_rate"], item["avg_craving_delta"]),
        default=None,
    )

    return {
        "headline": make_headline(strongest_drop, most_engaged),
        "audience_model_caveat": (
            "Current run uses a mixed India/English Pocket-FM-style listener panel. It covers "
            "multiple listening settings and story need-regions, but absolute retention levels "
            "are still uncalibrated until compared with real episode-level drop data."
        ),
        "strongest_drop": strongest_drop,
        "most_engaged": most_engaged,
        "retention_shape": retention_shape(metrics),
        "episode_intelligence": episode_intelligence or {},
        "region_retention_curves": region_retention_curves(episodes, by_episode, persona_lookup),
        "microsegment_retention": microsegment_retention(episodes, by_episode, persona_lookup),
        "episode_table": episode_table(metrics, by_episode, persona_lookup, paywall_rows),
        "drop_beat_inspector": drop_beat_inspector(metrics, by_episode, beat_lookup, persona_lookup),
        "llm_heuristic_bridge": llm_heuristic_bridge(metrics, by_episode, persona_lookup),
        "segment_sensitivity": segment_sensitivity(metrics, by_episode, persona_lookup),
        "survivor_skew": survivor_skew(episodes, by_episode, persona_lookup),
        "paywall_diagnostics": paywall_diagnostics(metrics, by_episode, persona_lookup),
        "paywall_map": paywall_rows,
        "expectation_scorecard": expectation_scorecard(metrics, paywall_rows),
        "episode_insights": episode_insights,
        "agent_opinion_themes": {
            "drop_reasons": counter_rows(record.continue_reason for record in drop_records),
            "continue_reasons": counter_rows(record.continue_reason for record in continue_records),
            "emotional_states": counter_rows(record.emotional_state for record in all_records),
            "felt_emotions": counter_rows(record.felt_emotion for record in all_records),
            "emotion_shifts": counter_rows(record.emotion_shift for record in all_records),
            "judgement_bridges": counter_rows(record.judgement_bridge for record in all_records),
            "pay_objections": counter_rows(record.pay_reason for record in all_records if not record.would_pay),
            "next_predictions": counter_rows(record.next_prediction for record in all_records),
        },
        "weighted_agent_voice": weighted_voice,
        "editorial_actions": editorial_actions(episode_insights),
        "model_gaps": model_gaps(),
    }


def retention_shape(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not metrics:
        return []
    population_size = metrics[0]["active_before"] or 1
    rows = []
    for row in metrics:
        lost = row["active_before"] - row["continue_count"]
        if lost <= 0:
            continue
        rows.append(
            {
                "episode_no": row["episode_no"],
                "title": row["episode_title"],
                "stage": episode_stage(row["episode_no"]),
                "lost": lost,
                "loss_from_start": round(lost / population_size, 4),
                "continue_rate": row["continue_rate"],
                "retention_from_start": row["retention_from_start"],
            }
        )
    return sorted(rows, key=lambda item: (item["lost"], 1.0 - item["continue_rate"]), reverse=True)[:4]


def episode_stage(episode_no: int) -> str:
    if episode_no == 1:
        return "opening hook"
    if episode_no <= 3:
        return "premise validation"
    if episode_no <= 6:
        return "mid-season endurance"
    return "endgame"


def region_retention_curves(
    episodes: list[Episode],
    by_episode: dict[int, list[Reaction]],
    persona_lookup: dict[str, Persona],
) -> list[dict[str, Any]]:
    if not episodes or not persona_lookup:
        return []
    region_ids = sorted({persona.region_label for persona in persona_lookup.values()})
    rows: list[dict[str, Any]] = []
    for region in region_ids:
        start_count = sum(1 for persona in persona_lookup.values() if persona.region_label == region)
        if start_count == 0:
            continue
        points = []
        for episode in episodes:
            records = [
                record
                for record in by_episode.get(episode.episode_no, [])
                if persona_lookup.get(record.persona_id)
                and persona_lookup[record.persona_id].region_label == region
            ]
            active_before = len(records)
            retained_after = sum(1 for record in records if record.will_continue)
            points.append(
                {
                    "episode_no": episode.episode_no,
                    "active_index": round(active_before / start_count * 100, 1),
                    "retained_index": round(retained_after / start_count * 100, 1),
                    "active_before": active_before,
                    "retained_after": retained_after,
                }
            )
        rows.append(
            {
                "region": region,
                "start_count": start_count,
                "points": points,
                "departure_signature": departure_signature(region, points),
            }
        )
    return rows


def departure_signature(region: str, points: list[dict[str, Any]]) -> str:
    if not points:
        return "no exposure"
    final_idx = points[-1]["retained_index"]
    losses = []
    previous = 100.0
    for point in points:
        loss = max(0.0, previous - point["retained_index"])
        if loss:
            losses.append((point["episode_no"], loss))
        previous = point["retained_index"]
    if final_idx >= 85:
        return "held throughout"
    if not losses:
        return "no clear departure point"
    episode_no, loss = max(losses, key=lambda item: item[1])
    if episode_no == 1:
        return "opening hook did not convert enough of this region"
    return f"largest relative loss after episode {episode_no}"


def episode_table(
    metrics: list[dict[str, Any]],
    by_episode: dict[int, list[Reaction]],
    persona_lookup: dict[str, Persona],
    paywall_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    paywall_by_ep = {row["episode_no"]: row for row in paywall_rows}
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        records = by_episode.get(metric["episode_no"], [])
        rows.append(
            {
                "episode_no": metric["episode_no"],
                "title": metric["episode_title"],
                "continue_tier": continue_tier(metric["continue_rate"]),
                "retained_index": round(metric["retention_from_start"] * 100, 1),
                "active": metric["active_before"],
                "lost": metric["drop_count"],
                "top_drop_beat": metric["top_drop_beat"],
                "regions_leaving": top_leaving_regions(records, persona_lookup),
                "pay_pressure": paywall_by_ep.get(metric["episode_no"], {}).get("pay_pressure", "none"),
            }
        )
    return rows


def continue_tier(rate: float) -> str:
    if rate >= 0.95:
        return "strong"
    if rate >= 0.85:
        return "stable"
    if rate >= 0.70:
        return "soft"
    return "polarizing"


def top_leaving_regions(
    records: list[Reaction],
    persona_lookup: dict[str, Persona],
    limit: int = 2,
) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for record in records:
        if record.will_continue:
            continue
        persona = persona_lookup.get(record.persona_id)
        if persona:
            counter[persona.region_label] += 1
    return [{"region": region, "count": count} for region, count in counter.most_common(limit)]


def drop_beat_inspector(
    metrics: list[dict[str, Any]],
    by_episode: dict[int, list[Reaction]],
    beat_lookup: dict[str, dict[str, Any]],
    persona_lookup: dict[str, Persona],
) -> list[dict[str, Any]]:
    metric_by_ep = {row["episode_no"]: row for row in metrics}
    grouped: dict[tuple[int, str], list[Reaction]] = defaultdict(list)
    for episode_no, records in by_episode.items():
        for record in records:
            if record.drop_beat and not record.will_continue:
                grouped[(episode_no, record.drop_beat)].append(record)

    rows: list[dict[str, Any]] = []
    for (episode_no, beat_id), records in grouped.items():
        metric = metric_by_ep.get(episode_no, {})
        signals = records[0].signal_json if records else {}
        beat_info = beat_lookup.get(beat_id, {})
        rows.append(
            {
                "episode_no": episode_no,
                "title": metric.get("episode_title", ""),
                "continue_tier": continue_tier(float(metric.get("continue_rate", 0.0))),
                "beat_id": beat_id,
                "label": beat_info.get("label", ""),
                "line_start": beat_info.get("line_start"),
                "line_end": beat_info.get("line_end"),
                "purpose": beat_info.get("purpose", ""),
                "beat_generator": beat_info.get("generator", ""),
                "beat_risk": beat_info.get("risk", ""),
                "beat_risk_reason": beat_info.get("risk_reason", ""),
                "quote": beat_info.get("quote", ""),
                "drop_count": len(records),
                "who_left": top_leaving_regions(records, persona_lookup, limit=4),
            "why": counter_rows((record.continue_reason for record in records), limit=4),
            "judgement_bridges": counter_rows((record.judgement_bridge for record in records), limit=4),
            "felt_emotions": counter_rows((record.felt_emotion for record in records), limit=4),
            "story_side_context": top_signal_flags(signals),
        }
        )
    return sorted(rows, key=lambda item: item["drop_count"], reverse=True)[:8]


def llm_heuristic_bridge(
    metrics: list[dict[str, Any]],
    by_episode: dict[int, list[Reaction]],
    persona_lookup: dict[str, Persona],
) -> dict[str, Any]:
    """Compare LLM decisions with Episode Intelligence advisory drop pressure.

    This is the bridge between the fast structural layer and LLM judgment. In
    advisory mode, these fields do not affect behavior; they explain where the
    heuristic prior is aligned, noisy, or blind.
    """
    rows: list[dict[str, Any]] = []
    disagreement_records: list[dict[str, Any]] = []
    total_actual_drops = 0
    total_advisory_drops = 0
    total_agreed_drops = 0
    total_advisory_only = 0
    total_llm_only = 0

    for metric in metrics:
        records = by_episode.get(metric["episode_no"], [])
        actual_drops = [record for record in records if not record.will_continue]
        advisory_drops = [
            record
            for record in records
            if float(record.signal_json.get("guardrail_recommended_drop", 0.0)) >= 0.5
        ]
        agreed = [
            record
            for record in records
            if not record.will_continue
            and float(record.signal_json.get("guardrail_recommended_drop", 0.0)) >= 0.5
        ]
        advisory_only = [
            record
            for record in records
            if record.will_continue
            and float(record.signal_json.get("guardrail_recommended_drop", 0.0)) >= 0.5
        ]
        llm_only = [
            record
            for record in records
            if not record.will_continue
            and float(record.signal_json.get("guardrail_recommended_drop", 0.0)) < 0.5
        ]
        total_actual_drops += len(actual_drops)
        total_advisory_drops += len(advisory_drops)
        total_agreed_drops += len(agreed)
        total_advisory_only += len(advisory_only)
        total_llm_only += len(llm_only)

        row = {
            "episode_no": metric["episode_no"],
            "title": metric["episode_title"],
            "active": len(records),
            "llm_drops": len(actual_drops),
            "advisory_drop_flags": len(advisory_drops),
            "agreed_drops": len(agreed),
            "advisory_only": len(advisory_only),
            "llm_only": len(llm_only),
            "precision": round(len(agreed) / len(advisory_drops), 4) if advisory_drops else None,
            "recall": round(len(agreed) / len(actual_drops), 4) if actual_drops else None,
            "read": bridge_read(len(records), len(actual_drops), len(advisory_drops), len(agreed), len(advisory_only), len(llm_only)),
            "advisory_only_regions": top_regions(advisory_only, persona_lookup, limit=4),
            "llm_drop_regions": top_regions(actual_drops, persona_lookup, limit=4),
        }
        rows.append(row)
        for record in advisory_only[:3]:
            disagreement_records.append(disagreement_row(metric, record, persona_lookup, "advisory_warned_llm_continued"))
        for record in llm_only[:3]:
            disagreement_records.append(disagreement_row(metric, record, persona_lookup, "llm_dropped_without_advisory"))

    return {
        "summary": {
            "llm_actual_drops": total_actual_drops,
            "advisory_drop_flags": total_advisory_drops,
            "agreed_drops": total_agreed_drops,
            "advisory_only": total_advisory_only,
            "llm_only": total_llm_only,
            "applied_overrides": sum(
                1
                for records in by_episode.values()
                for record in records
                if float(record.signal_json.get("guardrail_applied_override", 0.0)) >= 0.5
            ),
            "interpretation": bridge_summary(total_actual_drops, total_advisory_drops, total_agreed_drops, total_advisory_only, total_llm_only),
        },
        "by_episode": rows,
        "sample_disagreements": disagreement_records[:12],
    }


def bridge_read(
    active: int,
    actual: int,
    advisory: int,
    agreed: int,
    advisory_only: int,
    llm_only: int,
) -> str:
    if active == 0:
        return "No active listeners reached this episode."
    if actual == 0 and advisory == 0:
        return "LLM and structural prior both treat this episode as stable."
    if actual == 0 and advisory > 0:
        return "Structural prior over-warned; LLM accepted the live serial hook."
    if actual > 0 and agreed == actual and advisory_only == 0:
        return "LLM and structural prior agree on the drop risk."
    if actual > 0 and agreed > 0 and advisory_only > 0:
        return "Structural prior found the risk area but over-warned relative to LLM judgment."
    if actual > 0 and agreed > 0:
        return "Structural prior partially matched the LLM drop pattern."
    if llm_only > 0:
        return "LLM found qualitative drop reasons that the structural prior did not flag."
    return "Mixed alignment."


def bridge_summary(
    actual: int,
    advisory: int,
    agreed: int,
    advisory_only: int,
    llm_only: int,
) -> str:
    if actual == 0 and advisory == 0:
        return "No LLM drops and no advisory risk flags."
    if advisory_only > agreed and actual:
        return "The structural prior is useful as an early-warning layer, but too broad as a drop decision rule."
    if advisory_only and not actual:
        return "The structural prior is over-sensitive to risk where LLM judgment still sees continuation pull."
    if llm_only > agreed:
        return "The structural prior is missing qualitative reasons the LLM sees."
    return "The structural prior and LLM judgment are broadly aligned."


def disagreement_row(
    metric: dict[str, Any],
    record: Reaction,
    persona_lookup: dict[str, Persona],
    kind: str,
) -> dict[str, Any]:
    persona = persona_lookup.get(record.persona_id)
    return {
        "kind": kind,
        "episode_no": metric["episode_no"],
        "title": metric["episode_title"],
        "persona_id": record.persona_id,
        "region": persona.region_label if persona else "",
        "listening_setting": persona.cohort_label if persona else "",
        "drop_beat": record.drop_beat,
        "guardrail_pressure": record.signal_json.get("guardrail_pressure"),
        "guardrail_threshold": record.signal_json.get("guardrail_threshold"),
        "guardrail_rank": record.signal_json.get("guardrail_rank"),
        "reason": compact(record.continue_reason, 260),
    }


def top_regions(
    records: list[Reaction],
    persona_lookup: dict[str, Persona],
    limit: int = 4,
) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for record in records:
        persona = persona_lookup.get(record.persona_id)
        if persona:
            counter[persona.region_label] += 1
    return [{"region": region, "count": count} for region, count in counter.most_common(limit)]


def top_signal_flags(signals: dict[str, float], limit: int = 4) -> list[dict[str, Any]]:
    useful = {
        key: value
        for key, value in signals.items()
        if value >= 0.20
        and key
        in {
            "agency_gap",
            "family_only",
            "ambition",
            "competence",
            "cliffhanger",
            "ending_cliffhanger",
            "ending_status_reveal",
            "ending_romance_pressure",
            "public_vindication",
            "resolved_no_hook",
            "guardrail_pressure",
            "guardrail_threshold",
            "guardrail_base_threshold",
            "guardrail_override_margin",
            "guardrail_recommended_drop",
            "guardrail_applied_override",
            "guardrail_override",
            "guardrail_rank",
            "guardrail_abandon_pressure",
            "guardrail_cohort_fit",
        }
    }
    return [
        {"signal": key, "value": round(value, 3)}
        for key, value in sorted(useful.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def paywall_map(
    metrics: list[dict[str, Any]],
    by_episode: dict[int, list[Reaction]],
    persona_lookup: dict[str, Persona],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        records = by_episode.get(metric["episode_no"], [])
        signals = records[0].signal_json if records else {}
        ending_type = ending_taxonomy(signals)
        gate_class = gate_class_for_ending(ending_type)
        matched_regions = pay_matched_regions(records, persona_lookup, ending_type)
        pay_rate = metric.get("pay_rate", 0.0)
        rows.append(
            {
                "episode_no": metric["episode_no"],
                "title": metric["episode_title"],
                "ending_type": ending_type,
                "gate_class": gate_class,
                "matched_regions": matched_regions,
                "pay_pressure": pay_pressure_tier(pay_rate, ending_type, matched_regions),
                "verdict": paywall_verdict(metric["episode_no"], pay_rate, gate_class, matched_regions),
            }
        )
    return rows


def ending_taxonomy(signals: dict[str, float]) -> str:
    if signals.get("ending_cliffhanger", 0.0) >= 0.35:
        return "crisis_cliffhanger"
    if signals.get("ending_status_reveal", 0.0) >= 0.35:
        return "status_reveal"
    if signals.get("ending_romance_pressure", 0.0) >= 0.35:
        return "emotional_confession"
    if signals.get("resolved_no_hook", 0.0) >= 0.35:
        return "resolved_no_gate"
    return "weak_or_unclear_gate"


def gate_class_for_ending(ending_type: str) -> str:
    return {
        "crisis_cliffhanger": "threat gate",
        "status_reveal": "identity/status gate",
        "emotional_confession": "relationship/emotion gate",
        "resolved_no_gate": "comfort epilogue gate",
        "weak_or_unclear_gate": "no clean gate",
    }[ending_type]


def pay_matched_regions(
    records: list[Reaction],
    persona_lookup: dict[str, Persona],
    ending_type: str,
) -> list[dict[str, Any]]:
    region_counts: Counter[str] = Counter()
    paid_counts: Counter[str] = Counter()
    for record in records:
        persona = persona_lookup.get(record.persona_id)
        if not persona:
            continue
        region_counts[persona.region_label] += 1
        if record.would_pay:
            paid_counts[persona.region_label] += 1
    rows = []
    for region, active in region_counts.items():
        paid = paid_counts.get(region, 0)
        rate = paid / active if active else 0.0
        if paid or _region_matches_gate(region, ending_type):
            rows.append(
                {
                    "region": region,
                    "paid": paid,
                    "active": active,
                    "pay_rate": round(rate, 4),
                }
            )
    return sorted(rows, key=lambda item: (item["pay_rate"], item["paid"]), reverse=True)[:4]


def _region_matches_gate(region: str, ending_type: str) -> bool:
    lowered = region.lower()
    if ending_type == "crisis_cliffhanger":
        return "thrill" in lowered or "justice" in lowered or "household" in lowered
    if ending_type == "status_reveal":
        return "status" in lowered or "aspirational" in lowered or "justice" in lowered
    if ending_type == "emotional_confession":
        return "comfort" in lowered or "household" in lowered or "aspirational" in lowered
    if ending_type == "resolved_no_gate":
        return "comfort" in lowered or "household" in lowered
    return False


def pay_pressure_tier(
    pay_rate: float,
    ending_type: str,
    matched_regions: list[dict[str, Any]],
) -> str:
    if pay_rate >= 0.35:
        return "strong"
    if pay_rate >= 0.18:
        return "moderate"
    if pay_rate > 0.0 or (ending_type != "resolved_no_gate" and matched_regions):
        return "weak"
    return "none"


def paywall_verdict(
    episode_no: int,
    pay_rate: float,
    gate_class: str,
    matched_regions: list[dict[str, Any]],
) -> str:
    if pay_rate >= 0.35:
        return f"best gate candidate if episode {episode_no} is near a monetization point"
    if pay_rate >= 0.18:
        return "possible soft gate; strengthen the ending before charging"
    if gate_class == "comfort epilogue gate" and matched_regions:
        return "comfort-only epilogue gate; risky for thrill/status regions"
    if gate_class == "no clean gate":
        return "do not gate; ending lacks a clean paid promise"
    return "weak gate; pay psychology match is not yet converting"


def expectation_scorecard(
    metrics: list[dict[str, Any]],
    paywall_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    final_retention = metrics[-1]["retention_from_start"] if metrics else 0.0
    weakest = min(metrics, key=lambda row: row["continue_rate"]) if metrics else None
    best_pay = max(paywall_rows, key=lambda row: _pay_pressure_rank(row["pay_pressure"]), default=None)
    return [
        {
            "check": "Opening hook keeps enough of the panel to test later episodes",
            "result": "fired" if metrics and metrics[0]["continue_rate"] >= 0.70 else "missed",
            "note": (
                f"Episode 1 continue is {pct(metrics[0]['continue_rate']).strip()}."
                if metrics
                else "No episode metrics."
            ),
        },
        {
            "check": "Mid-season does not become the main attrition point",
            "result": "missed"
            if weakest and 4 <= weakest["episode_no"] <= 6 and weakest["continue_rate"] < 0.70
            else "fired",
            "note": (
                f"Weakest episode is {weakest['episode_no']} at {pct(weakest['continue_rate']).strip()} continue."
                if weakest
                else "No weakest episode."
            ),
        },
        {
            "check": "At least one ending has a clean paid-gate shape",
            "result": "fired"
            if best_pay and best_pay["pay_pressure"] in {"moderate", "strong"}
            else "partial"
            if best_pay and best_pay["pay_pressure"] == "weak"
            else "missed",
            "note": (
                f"Best gate: episode {best_pay['episode_no']} ({best_pay['gate_class']}), {best_pay['pay_pressure']} pressure."
                if best_pay
                else "No gate candidates found."
            ),
        },
        {
            "check": "Final retention index clears a directional publish threshold",
            "result": "fired" if final_retention >= 0.45 else "missed",
            "note": f"Final retained index is {final_retention * 100:.1f} with ep1 start = 100.",
        },
    ]


def _pay_pressure_rank(value: str) -> int:
    return {"none": 0, "weak": 1, "moderate": 2, "strong": 3}.get(value, 0)


def weighted_agent_voice(
    records: list[Reaction],
    persona_lookup: dict[str, Persona],
) -> dict[str, Any]:
    cohort_counts = Counter(persona.cohort_id for persona in persona_lookup.values())
    cohort_weights = {seed.seed_id: seed.weight for seed in LISTENER_SEEDS}

    def weight_for(persona_id: str) -> float:
        persona = persona_lookup.get(persona_id)
        if not persona:
            return 0.0
        count = cohort_counts.get(persona.cohort_id, 1)
        return cohort_weights.get(persona.cohort_id, 0.0) / count

    return {
        "drop_reasons": weighted_rows(
            (record.continue_reason, weight_for(record.persona_id))
            for record in records
            if not record.will_continue
        ),
        "continue_reasons": weighted_rows(
            (record.continue_reason, weight_for(record.persona_id))
            for record in records
            if record.will_continue
        ),
        "next_predictions": weighted_rows(
            (record.next_prediction, weight_for(record.persona_id))
            for record in records
        ),
        "pay_objections": weighted_rows(
            (record.pay_reason, weight_for(record.persona_id))
            for record in records
            if not record.would_pay
        ),
        "judgement_bridges": weighted_rows(
            (record.judgement_bridge, weight_for(record.persona_id))
            for record in records
        ),
        "felt_emotions": weighted_rows(
            (record.felt_emotion, weight_for(record.persona_id))
            for record in records
        ),
    }


def weighted_rows(values: Any, limit: int = 4) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    weights: Counter[str] = Counter()
    total_weight = 0.0
    for text, weight in values:
        normalized = normalize_reason(str(text))
        if not normalized:
            continue
        counts[normalized] += 1
        weights[normalized] += weight
        total_weight += weight
    rows = []
    for text, count in counts.items():
        rows.append(
            {
                "text": text,
                "agent_episodes": count,
                "market_mass_share": round(weights[text] / total_weight, 4) if total_weight else 0.0,
            }
        )
    return sorted(rows, key=lambda item: (item["market_mass_share"], item["agent_episodes"]), reverse=True)[:limit]


def normalize_reason(text: str) -> str:
    clean = " ".join(text.lower().split())
    clean = re.sub(r"\b(ep|episode)\s+\d+\b", "episode", clean)
    clean = re.sub(r"\b\d+\b", "#", clean)
    return clean.strip(" .")


def segment_sensitivity(
    metrics: list[dict[str, Any]],
    by_episode: dict[int, list[Reaction]],
    persona_lookup: dict[str, Persona],
) -> list[dict[str, Any]]:
    if not persona_lookup:
        return []
    rows: list[dict[str, Any]] = []
    axes = [
        ("need_region", "region_label"),
        ("listening_setting", "cohort_label"),
        ("spend_tier", "coin_spend_tier"),
        ("discovery", "discovery_channel"),
        ("interruption", "interruption_load"),
    ]
    for metric in metrics:
        records = by_episode.get(metric["episode_no"], [])
        if not records:
            continue
        for axis_label, attr in axes:
            active_counts: Counter[str] = Counter()
            drop_counts: Counter[str] = Counter()
            for record in records:
                persona = persona_lookup.get(record.persona_id)
                if not persona:
                    continue
                segment = str(getattr(persona, attr))
                active_counts[segment] += 1
                if not record.will_continue:
                    drop_counts[segment] += 1
            min_active = 3 if len(records) < 80 else 5
            candidates = []
            for segment, active in active_counts.items():
                drops = drop_counts[segment]
                if active >= min_active and drops:
                    candidates.append(
                        {
                            "segment": segment,
                            "active": active,
                            "drops": drops,
                            "drop_rate": drops / active,
                        }
                    )
            if candidates:
                strongest = sorted(
                    candidates,
                    key=lambda item: (item["drop_rate"], item["drops"], item["active"]),
                    reverse=True,
                )[0]
                rows.append(
                    {
                        "episode_no": metric["episode_no"],
                        "title": metric["episode_title"],
                        "axis": axis_label,
                        **strongest,
                    }
                )
    return sorted(rows, key=lambda item: (item["drops"], item["drop_rate"]), reverse=True)[:8]


def survivor_skew(
    episodes: list[Episode],
    by_episode: dict[int, list[Reaction]],
    persona_lookup: dict[str, Persona],
) -> dict[str, Any]:
    if not episodes or not persona_lookup:
        return {}
    last_episode_no = episodes[-1].episode_no
    final_records = by_episode.get(last_episode_no, [])
    final_ids = {record.persona_id for record in final_records if record.will_continue}
    if not final_ids:
        return {"final_survivors": 0, "over_represented_regions": [], "under_represented_regions": []}
    start_counts = Counter(persona.region_label for persona in persona_lookup.values())
    final_counts = Counter(persona_lookup[pid].region_label for pid in final_ids if pid in persona_lookup)
    start_total = sum(start_counts.values()) or 1
    final_total = sum(final_counts.values()) or 1
    rows = []
    for region, start_count in start_counts.items():
        final_count = final_counts.get(region, 0)
        rows.append(
            {
                "region": region,
                "start_count": start_count,
                "final_count": final_count,
                "retention_rate": final_count / start_count if start_count else 0.0,
                "share_delta": final_count / final_total - start_count / start_total,
            }
        )
    return {
        "final_survivors": final_total,
        "over_represented_regions": sorted(rows, key=lambda item: item["share_delta"], reverse=True)[:3],
        "under_represented_regions": sorted(rows, key=lambda item: item["share_delta"])[:3],
    }


def microsegment_retention(
    episodes: list[Episode],
    by_episode: dict[int, list[Reaction]],
    persona_lookup: dict[str, Persona],
) -> list[dict[str, Any]]:
    if not episodes or not persona_lookup:
        return []
    final_episode_no = episodes[-1].episode_no
    final_records = by_episode.get(final_episode_no, [])
    final_ids = {record.persona_id for record in final_records if record.will_continue}
    start_counts: Counter[str] = Counter()
    final_counts: Counter[str] = Counter()
    labels: dict[str, dict[str, str]] = {}
    for persona in persona_lookup.values():
        key = microsegment_key(persona)
        start_counts[key] += 1
        labels[key] = {
            "need_region": persona.region_label,
            "listening_setting": persona.cohort_label,
            "spend_tier": persona.coin_spend_tier,
            "interruption": persona.interruption_load,
            "city_tier": f"Tier {persona.city_tier}",
        }
        if persona.persona_id in final_ids:
            final_counts[key] += 1
    rows = []
    for key, start_count in start_counts.items():
        final_count = final_counts.get(key, 0)
        rows.append(
            {
                "microsegment": key,
                **labels[key],
                "start_count": start_count,
                "final_count": final_count,
                "retention_index": round(final_count / start_count * 100, 1) if start_count else 0.0,
            }
        )
    return sorted(rows, key=lambda item: (item["start_count"], item["retention_index"]), reverse=True)[:12]


def microsegment_key(persona: Persona) -> str:
    return (
        f"{persona.region_label} / {persona.cohort_label} / "
        f"{persona.coin_spend_tier} / {persona.interruption_load} interruption"
    )


def paywall_diagnostics(
    metrics: list[dict[str, Any]],
    by_episode: dict[int, list[Reaction]],
    persona_lookup: dict[str, Persona],
) -> list[dict[str, Any]]:
    if not persona_lookup:
        return []
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        records = by_episode.get(metric["episode_no"], [])
        gaps = []
        close_calls = 0
        tier_counts: Counter[str] = Counter()
        for record in records:
            persona = persona_lookup.get(record.persona_id)
            if not persona:
                continue
            gap = persona.pay_threshold - record.pay_pressure
            gaps.append(gap)
            if record.will_continue and not record.would_pay and 0.0 <= gap <= 0.12:
                close_calls += 1
                tier_counts[persona.coin_spend_tier] += 1
        if not gaps:
            continue
        rows.append(
            {
                "episode_no": metric["episode_no"],
                "title": metric["episode_title"],
                "pay_rate": metric["pay_rate"],
                "avg_pay_gap": sum(gaps) / len(gaps),
                "close_calls": close_calls,
                "closest_tiers": counter_rows(tier_counts.elements(), limit=3),
            }
        )
    return sorted(rows, key=lambda item: (item["pay_rate"], -item["avg_pay_gap"], item["close_calls"]), reverse=True)[:4]


def model_gaps() -> list[str]:
    return [
        "The deterministic engine is fast, but its story understanding is keyword/signal based; it can under-read motifs like guilt, moral inversion, voice performance, and cultural texture unless they map to known signals.",
        "Current reports summarize agent reasons as repeated buckets; an LLM run can produce richer per-persona explanations, but costs more time and API calls.",
        "The run is not calibrated against real Pocket-FM episode retention, ad source, coin conversion, or completion logs, so absolute percentages should be treated as directional.",
        "The simulator does not yet test alternate edits, paywall placement variants, episode thumbnails/hooks, or narration quality, all of which can change actual release performance.",
    ]


def episode_insight(
    metric: dict[str, Any],
    records: list[Reaction],
    beat_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    active_before = metric["active_before"]
    drop_records = [record for record in records if not record.will_continue]
    continue_records = [record for record in records if record.will_continue]
    pay_no_records = [record for record in records if not record.would_pay]
    top_drop_beat = metric["top_drop_beat"]
    top_drop_info = beat_lookup.get(top_drop_beat or "", {})
    signals = records[0].signal_json if records else {}

    return {
        "episode_no": metric["episode_no"],
        "title": metric["episode_title"],
        "active_before": active_before,
        "continue_rate": metric["continue_rate"],
        "retention_from_start": metric["retention_from_start"],
        "drop_count": metric["drop_count"],
        "pay_rate": metric["pay_rate"],
        "avg_craving_delta": metric["avg_craving_delta"],
        "top_drop_beat": top_drop_beat,
        "top_drop_beat_excerpt": top_drop_info.get("quote", "") if top_drop_beat else "",
        "top_drop_beat_label": top_drop_info.get("label", "") if top_drop_beat else "",
        "top_drop_beat_lines": (
            [top_drop_info.get("line_start"), top_drop_info.get("line_end")]
            if top_drop_beat and top_drop_info.get("line_start") is not None
            else []
        ),
        "drop_reasons": counter_rows(record.continue_reason for record in drop_records),
        "continue_reasons": counter_rows(record.continue_reason for record in continue_records),
        "emotional_states": counter_rows(record.emotional_state for record in records),
        "felt_emotions": counter_rows(record.felt_emotion for record in records),
        "emotion_shifts": counter_rows(record.emotion_shift for record in records),
        "judgement_bridges": counter_rows(record.judgement_bridge for record in records),
        "pay_objections": counter_rows(record.pay_reason for record in pay_no_records),
        "signal_diagnosis": signal_diagnosis(signals),
        "read": episode_read(metric, drop_records, continue_records, signals),
    }


def signal_diagnosis(signals: dict[str, float]) -> list[str]:
    if not signals:
        return ["No active listeners reached this episode."]
    notes: list[str] = []
    if signals.get("agency_gap", 0.0) >= 0.20:
        notes.append("agency risk: protagonist/listener proxy feels reactive or cornered")
    if signals.get("family_only", 0.0) >= 0.15:
        notes.append("family-pressure risk: domestic stakes need clearer catharsis, justice, or status payoff")
    if signals.get("ambition", 0.0) < 0.10 and signals.get("competence", 0.0) < 0.10:
        notes.append("low external payoff: few competence, justice, revenge, or status wins for the mixed panel")
    if signals.get("ending_cliffhanger", 0.0) < 0.10 and signals.get("ending_status_reveal", 0.0) < 0.10:
        notes.append("weak paywall pressure: ending is not a status/reveal gate for this cohort")
    if signals.get("public_vindication", 0.0) >= 0.25:
        notes.append("positive: public proof/vindication is present")
    if signals.get("cliffhanger", 0.0) >= 0.25:
        notes.append("positive: threat/cliffhanger language is present")
    if not notes:
        notes.append("no dominant risk signal detected by the current heuristic layer")
    return notes


def episode_read(
    metric: dict[str, Any],
    drop_records: list[Reaction],
    continue_records: list[Reaction],
    signals: dict[str, float],
) -> str:
    if metric["active_before"] == 0:
        return "No active simulated listeners remained to evaluate this episode."
    if metric["continue_rate"] >= 0.75:
        return "The remaining listeners treated this as a stable continuation point."
    if metric["continue_rate"] >= 0.40:
        return "The episode is polarizing: some listeners follow the threat, but a large share does not see enough cohort-specific reward."
    if signals.get("ambition", 0.0) < 0.10 and signals.get("competence", 0.0) < 0.10:
        return "The main drop is fit related: the story has danger, but not enough clear payoff type for this mixed India/English panel."
    if drop_records and not continue_records:
        return "The episode fails the active panel almost completely; the surviving listeners do not find a strong enough next-episode reason."
    return "Drop-off is driven by a mismatch between the episode's promise and this cohort's continuation triggers."


def editorial_actions(episode_insights: list[dict[str, Any]]) -> list[str]:
    reached = [item for item in episode_insights if item["active_before"] > 0]
    if not reached:
        return ["Run a story opening first; no active listeners reached any episode."]

    weakest = min(reached, key=lambda item: item["continue_rate"])
    actions = [
        (
            f"Rewrite episode {weakest['episode_no']} ({weakest['title']}) first. "
            f"It has {pct(weakest['continue_rate']).strip()} continue among active listeners."
        )
    ]
    if weakest["top_drop_beat"]:
        actions.append(
            f"Inspect `{weakest['top_drop_beat']}`: {weakest['top_drop_beat_excerpt']}"
        )
    actions.append(
        "For this mixed panel, add a visible payoff before asking listeners to carry more danger or procedural detail: justice progress, emotional catharsis, competence, relationship movement, or status change."
    )
    actions.append(
        "Do not place a paywall until the ending blocks a reveal, public proof, or irreversible status move; current simulated pay pressure is weak."
    )
    actions.append(
        "For high-stakes decisions, rerun with `--engine llm` on a smaller panel and compare the qualitative reasons against this deterministic pass."
    )
    return actions


def make_headline(
    strongest_drop: dict[str, Any] | None,
    most_engaged: dict[str, Any] | None,
) -> str:
    if not strongest_drop:
        return "No active-listener drop pattern available."
    if strongest_drop["continue_rate"] == 0:
        return (
            f"Drop-off concentrates at episode {strongest_drop['episode_no']}: "
            f"all remaining active listeners abandon there in this cohort run."
        )
    return (
        f"Largest drop pressure is episode {strongest_drop['episode_no']} "
        f"({pct(strongest_drop['continue_rate']).strip()} continue)."
    )


def counter_rows(values: Any, limit: int = 5) -> list[dict[str, Any]]:
    counter = Counter(value for value in values if value)
    return [
        {"text": text, "count": count}
        for text, count in counter.most_common(limit)
    ]


def compact(text: str, max_chars: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3] + "..."
