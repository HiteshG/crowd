from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .models import Episode, Reaction
from .utils import entropy


def prediction_bucket(prediction: str) -> str:
    text = prediction.lower()
    if any(term in text for term in ["proof", "truth", "surface", "exposed", "public"]):
        return "truth_or_proof"
    if any(term in text for term in ["cover-up", "cover up", "protect the family", "secret stays buried"]):
        return "coverup_pressure"
    if any(term in text for term in ["relationship", "confession"]):
        return "romance_interruption"
    if any(term in text for term in ["status", "ownership", "identity"]):
        return "status_or_identity_reveal"
    if any(term in text for term in ["police", "body", "threat", "clue", "lying"]):
        return "investigation_pressure"
    if any(term in text for term in ["guilt", "family secret", "emotional trap"]):
        return "family_secret"
    return "tactical_move"


def aggregate_metrics(
    run_id: str,
    population_size: int,
    episodes: list[Episode],
    reactions: list[Reaction],
) -> list[dict[str, Any]]:
    by_episode: dict[int, list[Reaction]] = defaultdict(list)
    for reaction in reactions:
        by_episode[reaction.episode_no].append(reaction)

    rows: list[dict[str, Any]] = []
    for episode in episodes:
        records = by_episode.get(episode.episode_no, [])
        active_before = len(records)
        continue_count = sum(1 for record in records if record.will_continue)
        drop_count = active_before - continue_count
        pay_count = sum(1 for record in records if record.would_pay)
        drop_counts = Counter(
            record.drop_beat
            for record in records
            if record.drop_beat and not record.will_continue
        )
        top_drop_beat = drop_counts.most_common(1)[0][0] if drop_counts else None
        craving_delta = (
            sum(record.craving_end - record.craving_mid for record in records) / active_before
            if active_before
            else 0.0
        )
        buckets = [prediction_bucket(record.next_prediction) for record in records]
        rows.append(
            {
                "run_id": run_id,
                "episode_no": episode.episode_no,
                "episode_title": episode.title,
                "active_before": active_before,
                "continue_count": continue_count,
                "drop_count": drop_count,
                "pay_count": pay_count,
                "retention_from_start": continue_count / population_size if population_size else 0.0,
                "continue_rate": continue_count / active_before if active_before else 0.0,
                "pay_rate": pay_count / active_before if active_before else 0.0,
                "avg_craving_delta": craving_delta,
                "prediction_entropy": entropy(buckets),
                "top_drop_beat": top_drop_beat,
                "top_prediction_buckets": Counter(buckets).most_common(4),
                "top_drop_beats": drop_counts.most_common(4),
            }
        )
    return rows


def build_verdict(
    run_id: str,
    cohort_name: str,
    population_size: int,
    episode_count: int,
    metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    weakest = min(metrics, key=lambda row: row["continue_rate"]) if metrics else None
    paywall = max(metrics, key=lambda row: row["pay_rate"]) if metrics else None
    final_retention = metrics[-1]["retention_from_start"] if metrics else 0.0
    mean_continue = sum(row["continue_rate"] for row in metrics) / len(metrics) if metrics else 0.0
    mean_craving_delta = sum(row["avg_craving_delta"] for row in metrics) / len(metrics) if metrics else 0.0
    mean_entropy = sum(row["prediction_entropy"] for row in metrics) / len(metrics) if metrics else 0.0

    if final_retention >= 0.70 and mean_craving_delta >= 1.0:
        recommendation = "greenlight_for_pilot"
        confidence = "medium"
    elif final_retention >= 0.45:
        recommendation = "revise_before_pilot"
        confidence = "medium"
    else:
        recommendation = "major_rewrite"
        confidence = "medium-low"

    return {
        "run_id": run_id,
        "cohort": cohort_name,
        "population_size": population_size,
        "episode_count": episode_count,
        "calibration_warning": "Uncalibrated simulator output. Use rankings, drop points, and directional diagnosis until backtested.",
        "recommendation": recommendation,
        "confidence": confidence,
        "final_retention_from_start": round(final_retention, 4),
        "mean_continue_rate": round(mean_continue, 4),
        "mean_craving_delta": round(mean_craving_delta, 4),
        "mean_prediction_entropy": round(mean_entropy, 4),
        "weakest_episode": {
            "episode_no": weakest["episode_no"],
            "title": weakest["episode_title"],
            "continue_rate": round(weakest["continue_rate"], 4),
            "top_drop_beat": weakest["top_drop_beat"],
        }
        if weakest
        else None,
        "paywall_candidate": {
            "episode_no": paywall["episode_no"],
            "title": paywall["episode_title"],
            "pay_rate": round(paywall["pay_rate"], 4),
        }
        if paywall
        else None,
        "episode_metrics": metrics,
    }
