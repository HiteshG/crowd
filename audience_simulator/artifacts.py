from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from .cohorts import INDIA_ENGLISH_COHORT_CARD
from .models import Persona, Reaction
from .utils import json_dumps, pct


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if dataclasses.is_dataclass(row):
                payload = dataclasses.asdict(row)
            else:
                payload = row
            handle.write(json_dumps(payload) + "\n")


def write_report(path: Path, verdict: dict[str, Any]) -> None:
    metrics = verdict["episode_metrics"]
    lines = [
        "# Audience Simulator Report",
        "",
        f"Run ID: `{verdict['run_id']}`",
        f"Cohort: **{verdict['cohort']}**",
        f"Population: **{verdict['population_size']} synthetic listeners**",
        f"Episodes: **{verdict['episode_count']}**",
        "",
        "> Uncalibrated simulator output. Use rankings, drop points, and directional diagnosis until backtested against real retention.",
        "",
        "## Verdict",
        "",
        f"- Recommendation: `{verdict['recommendation']}`",
        f"- Confidence: `{verdict['confidence']}`",
        f"- Final retained from start: **{pct(verdict['final_retention_from_start']).strip()}**",
        f"- Mean continue rate: **{pct(verdict['mean_continue_rate']).strip()}**",
        f"- Mean craving delta: **{verdict['mean_craving_delta']:.2f}**",
        f"- Mean prediction entropy: **{verdict['mean_prediction_entropy']:.2f}**",
        "",
        "## India/English Cohort Model",
        "",
        f"- Model: {INDIA_ENGLISH_COHORT_CARD['model']}",
        f"- Market: {INDIA_ENGLISH_COHORT_CARD['market']}",
        f"- Drivers: {', '.join(INDIA_ENGLISH_COHORT_CARD['drivers'])}",
        f"- Retention hooks: {', '.join(INDIA_ENGLISH_COHORT_CARD['retention_hooks'])}",
        f"- Drop triggers: {', '.join(INDIA_ENGLISH_COHORT_CARD['drop_triggers'])}",
        f"- Pay triggers: {', '.join(INDIA_ENGLISH_COHORT_CARD['pay_triggers'])}",
        f"- MBTI scope: {INDIA_ENGLISH_COHORT_CARD['mbti']['scope']}",
        "",
        "Source basis:",
        "",
    ]
    for source in INDIA_ENGLISH_COHORT_CARD["source_basis"]:
        lines.append(f"- {source}")
    lines.extend(
        [
            "",
            "Listener settings:",
            "",
        ]
    )
    for seed in INDIA_ENGLISH_COHORT_CARD["listener_seed_mix"]:
        lines.append(
            f"- {seed['label']} ({seed['weight']:.0%}, {seed['context']}, {seed['session_pattern']})"
        )
    lines.extend(
        [
            "",
            "## Episode Metrics",
            "",
            "| Ep | Title | Active | Continue | Retained | Pay | Craving Delta | Entropy | Top Drop Beat |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in metrics:
        lines.append(
            "| "
            f"{row['episode_no']} | "
            f"{row['episode_title']} | "
            f"{row['active_before']} | "
            f"{pct(row['continue_rate']).strip()} | "
            f"{pct(row['retention_from_start']).strip()} | "
            f"{pct(row['pay_rate']).strip()} | "
            f"{row['avg_craving_delta']:.2f} | "
            f"{row['prediction_entropy']:.2f} | "
            f"{row['top_drop_beat'] or '-'} |"
        )
    lines.extend(["", "## Triage", ""])
    if verdict["weakest_episode"]:
        weakest = verdict["weakest_episode"]
        lines.append(
            f"- Weakest continue point: episode {weakest['episode_no']} "
            f"({weakest['title']}), {pct(weakest['continue_rate']).strip()} continue."
        )
        if weakest["top_drop_beat"]:
            lines.append(f"- First beat to inspect: `{weakest['top_drop_beat']}`.")
    if verdict["paywall_candidate"]:
        paywall = verdict["paywall_candidate"]
        lines.append(
            f"- Best paywall candidate in this run: episode {paywall['episode_no']} "
            f"({paywall['title']}), {pct(paywall['pay_rate']).strip()} simulated pay."
        )
    if verdict.get("insights"):
        append_insights(lines, verdict["insights"])
    lines.extend(["", "## Prediction Buckets", ""])
    for row in metrics:
        buckets = ", ".join(f"{name}: {count}" for name, count in row["top_prediction_buckets"])
        lines.append(f"- Episode {row['episode_no']}: {buckets or 'none'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_insights(lines: list[str], insights: dict[str, Any]) -> None:
    lines.extend(
        [
            "",
            "## Drop-Off Insights",
            "",
            f"- {insights['headline']}",
            f"- Caveat: {insights['audience_model_caveat']}",
            "",
            "### Retention Shape",
            "",
        ]
    )
    if insights.get("retention_shape"):
        for item in insights["retention_shape"]:
            lines.append(
                f"- Episode {item['episode_no']} ({item['title']}): lost {item['lost']} listeners "
                f"({pct(item['loss_from_start']).strip()} of start) in {item['stage']}; "
                f"{pct(item['continue_rate']).strip()} continued."
            )
    else:
        lines.append("- No listener loss detected.")

    if insights.get("survivor_skew"):
        skew = insights["survivor_skew"]
        lines.append("")
        lines.append(
            f"- Final survivors: {skew.get('final_survivors', 0)}. "
            "The final panel is no longer the same audience mix as episode 1."
        )
        over = skew.get("over_represented_regions", [])
        under = skew.get("under_represented_regions", [])
        if over:
            formatted = ", ".join(
                f"{item['region']} ({pct(item['retention_rate']).strip()} retained)"
                for item in over
            )
            lines.append(f"- Over-represented by finale: {formatted}.")
        if under:
            formatted = ", ".join(
                f"{item['region']} ({pct(item['retention_rate']).strip()} retained)"
                for item in under
            )
            lines.append(f"- Under-represented by finale: {formatted}.")

    lines.extend(
        [
            "",
            "### Episode Diagnosis",
            "",
        ]
    )
    for item in insights["episode_insights"]:
        if item["active_before"] == 0:
            continue
        lines.append(
            f"- Episode {item['episode_no']} ({item['title']}): "
            f"{pct(item['continue_rate']).strip()} continue, "
            f"{pct(item['retention_from_start']).strip()} retained from start. "
            f"{item['read']}"
        )
        if item["top_drop_beat"]:
            lines.append(f"  Top drop beat `{item['top_drop_beat']}`: {item['top_drop_beat_excerpt']}")
        for note in item["signal_diagnosis"][:3]:
            lines.append(f"  Signal: {note}.")

    if insights.get("segment_sensitivity"):
        lines.extend(["", "### Segment Sensitivity", ""])
        for item in insights["segment_sensitivity"]:
            lines.append(
                f"- Episode {item['episode_no']} ({item['title']}), {item['axis']} "
                f"`{item['segment']}`: {item['drops']}/{item['active']} dropped "
                f"({pct(item['drop_rate']).strip()})."
            )

    if insights.get("paywall_diagnostics"):
        lines.extend(["", "### Paywall Diagnostics", ""])
        for item in insights["paywall_diagnostics"]:
            tier_text = ", ".join(
                f"{row['text']}: {row['count']}" for row in item.get("closest_tiers", [])
            )
            suffix = f" Close-call tiers: {tier_text}." if tier_text else ""
            lines.append(
                f"- Episode {item['episode_no']} ({item['title']}): "
                f"{pct(item['pay_rate']).strip()} paid, average pressure-threshold gap "
                f"{item['avg_pay_gap']:.2f}, {item['close_calls']} close calls.{suffix}"
            )

    themes = insights["agent_opinion_themes"]
    lines.extend(["", "### Agent Opinion Themes", ""])
    append_theme(lines, "Why Droppers Left", themes["drop_reasons"])
    append_theme(lines, "Why Continuers Stayed", themes["continue_reasons"])
    append_theme(lines, "Emotional States", themes["emotional_states"])
    append_theme(lines, "Paywall Objections", themes["pay_objections"])
    append_theme(lines, "Expected Next Beats", themes["next_predictions"])

    lines.extend(["", "### Editorial Actions", ""])
    for action in insights["editorial_actions"]:
        lines.append(f"- {action}")

    if insights.get("model_gaps"):
        lines.extend(["", "### Missing Nuance / Model Gaps", ""])
        for gap in insights["model_gaps"]:
            lines.append(f"- {gap}")


def append_theme(lines: list[str], label: str, rows: list[dict[str, Any]]) -> None:
    lines.append(f"**{label}**")
    if not rows:
        lines.append("- No data.")
        return
    for row in rows:
        lines.append(f"- {row['count']} agents: {row['text']}")
    lines.append("")


def write_run_artifacts(
    run_dir: Path,
    run_record: dict[str, Any],
    personas: list[Persona],
    reactions: list[Reaction],
    metrics: list[dict[str, Any]],
    verdict: dict[str, Any],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "manifest.json", run_record)
    write_json(run_dir / "cohort_card.json", INDIA_ENGLISH_COHORT_CARD)
    write_jsonl(run_dir / "personas.jsonl", personas)
    write_jsonl(run_dir / "reactions.jsonl", reactions)
    write_json(run_dir / "metrics.json", metrics)
    write_json(run_dir / "verdict.json", verdict)
    write_report(run_dir / "report.md", verdict)
