from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .models import Episode, Persona, Reaction
from .utils import pct


def build_insights(
    episodes: list[Episode],
    reactions: list[Reaction],
    metrics: list[dict[str, Any]],
    personas: list[Persona] | None = None,
) -> dict[str, Any]:
    by_episode: dict[int, list[Reaction]] = defaultdict(list)
    for reaction in reactions:
        by_episode[reaction.episode_no].append(reaction)
    persona_lookup = {persona.persona_id: persona for persona in personas or []}

    beat_lookup = {
        beat.beat_id: compact(beat.text, 260)
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
        "segment_sensitivity": segment_sensitivity(metrics, by_episode, persona_lookup),
        "survivor_skew": survivor_skew(episodes, by_episode, persona_lookup),
        "paywall_diagnostics": paywall_diagnostics(metrics, by_episode, persona_lookup),
        "episode_insights": episode_insights,
        "agent_opinion_themes": {
            "drop_reasons": counter_rows(record.continue_reason for record in drop_records),
            "continue_reasons": counter_rows(record.continue_reason for record in continue_records),
            "emotional_states": counter_rows(record.emotional_state for record in all_records),
            "pay_objections": counter_rows(record.pay_reason for record in all_records if not record.would_pay),
            "next_predictions": counter_rows(record.next_prediction for record in all_records),
        },
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
    beat_lookup: dict[str, str],
) -> dict[str, Any]:
    active_before = metric["active_before"]
    drop_records = [record for record in records if not record.will_continue]
    continue_records = [record for record in records if record.will_continue]
    pay_no_records = [record for record in records if not record.would_pay]
    top_drop_beat = metric["top_drop_beat"]
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
        "top_drop_beat_excerpt": beat_lookup.get(top_drop_beat, "") if top_drop_beat else "",
        "drop_reasons": counter_rows(record.continue_reason for record in drop_records),
        "continue_reasons": counter_rows(record.continue_reason for record in continue_records),
        "emotional_states": counter_rows(record.emotional_state for record in records),
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
        notes.append("low external payoff: few competence, career, revenge, or status wins for the mixed panel")
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
        "For this mixed panel, add a visible payoff before asking listeners to carry more danger or procedural detail: revenge progress, emotional catharsis, competence, relationship movement, or status change."
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
