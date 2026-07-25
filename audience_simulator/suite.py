from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .runner import run_audience_simulation
from .utils import json_dumps, pct


def run_audience_simulation_suite(
    *,
    story_path: Path,
    out_dir: Path,
    personas: int,
    seed: int,
    repeats: int,
    run_id: str | None,
    expect_episodes: int | None,
    episode_mode: str,
    notes: str,
    engine_kind: str,
    model: str,
    reasoning_effort: str,
    persona_mode: str,
    report_mode: str,
    max_workers: int,
    progress: bool,
    checkpoint: bool,
    episode_intel_mode: str,
    guardrail_mode: str,
    judgement_mode: str,
) -> dict[str, Any]:
    if repeats < 2:
        raise ValueError("--repeats must be >= 2 for a suite run")

    started_at = time.time()
    suite_id = run_id or f"suite-{story_path.stem}-{int(started_at)}"
    suite_dir = out_dir / suite_id
    suite_dir.mkdir(parents=True, exist_ok=True)

    run_results: list[dict[str, Any]] = []
    for index in range(repeats):
        repeat_no = index + 1
        repeat_seed = seed + index
        repeat_run_id = f"{suite_id}-r{repeat_no:02d}-s{repeat_seed}"
        result = run_audience_simulation(
            story_path=story_path,
            out_dir=suite_dir,
            personas=personas,
            seed=repeat_seed,
            run_id=repeat_run_id,
            expect_episodes=expect_episodes,
            episode_mode=episode_mode,
            notes=f"{notes} | suite={suite_id} repeat={repeat_no}/{repeats}".strip(" |"),
            engine_kind=engine_kind,
            model=model,
            reasoning_effort=reasoning_effort,
            persona_mode=persona_mode,
            report_mode=report_mode,
            max_workers=max_workers,
            progress=progress,
            checkpoint=checkpoint,
            episode_intel_mode=episode_intel_mode,
            guardrail_mode=guardrail_mode,
            judgement_mode=judgement_mode,
        )
        result["repeat_no"] = repeat_no
        result["seed"] = repeat_seed
        run_results.append(result)

    summary = build_suite_summary(suite_id, run_results)
    manifest = {
        "suite_id": suite_id,
        "created_at": int(started_at),
        "story_path": str(story_path),
        "personas_per_run": personas,
        "repeats": repeats,
        "seed_start": seed,
        "engine_kind": engine_kind,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "persona_mode": persona_mode,
        "report_mode": report_mode,
        "episode_intel_mode": episode_intel_mode,
        "guardrail_mode": guardrail_mode,
        "judgement_mode": judgement_mode,
        "run_ids": [item["run_id"] for item in run_results],
        "artifacts": {
            "suite_summary": "suite_summary.json",
            "suite_report": "suite_report.md",
        },
    }
    (suite_dir / "suite_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (suite_dir / "suite_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (suite_dir / "suite_report.md").write_text(
        render_suite_report(manifest, summary),
        encoding="utf-8",
    )
    return {
        "suite_id": suite_id,
        "suite_dir": str(suite_dir),
        "runs": run_results,
        "summary": summary,
    }


def build_suite_summary(suite_id: str, run_results: list[dict[str, Any]]) -> dict[str, Any]:
    per_episode: dict[int, list[dict[str, Any]]] = defaultdict(list)
    recommendation_counts: Counter[str] = Counter()
    all_drop_beats: Counter[str] = Counter()
    judgement_changes = 0
    total_reactions = 0
    emotion_to_judgement: Counter[str] = Counter()

    for result in run_results:
        verdict = result["verdict"]
        recommendation_counts[verdict["recommendation"]] += 1
        for row in result["metrics"]:
            per_episode[row["episode_no"]].append(row)
            for beat_id, count in row.get("top_drop_beats", []):
                all_drop_beats[str(beat_id)] += int(count)
        run_dir = Path(result["run_dir"])
        reactions_path = run_dir / "reactions.jsonl"
        if reactions_path.exists():
            for raw_line in reactions_path.read_text(encoding="utf-8").splitlines():
                reaction = json.loads(raw_line)
                total_reactions += 1
                if reaction.get("judgement_changed"):
                    judgement_changes += 1
                bridge = str(reaction.get("judgement_bridge", "")).strip()
                if bridge:
                    emotion_to_judgement[bridge] += 1

    episode_rows = []
    for episode_no, rows in sorted(per_episode.items()):
        continue_rates = [float(row["continue_rate"]) for row in rows]
        retained = [float(row["retention_from_start"]) for row in rows]
        pay_rates = [float(row["pay_rate"]) for row in rows]
        craving = [float(row["avg_craving_delta"]) for row in rows]
        drop_counts = [int(row["drop_count"]) for row in rows]
        beat_counts: Counter[str] = Counter()
        for row in rows:
            for beat_id, count in row.get("top_drop_beats", []):
                beat_counts[str(beat_id)] += int(count)
        episode_rows.append(
            {
                "episode_no": episode_no,
                "title": rows[0]["episode_title"],
                "mean_continue_rate": mean(continue_rates),
                "min_continue_rate": min(continue_rates),
                "max_continue_rate": max(continue_rates),
                "mean_retained_index": mean(retained) * 100,
                "mean_pay_rate": mean(pay_rates),
                "mean_craving_delta": mean(craving),
                "mean_drop_count": mean(drop_counts),
                "top_drop_beats": beat_counts.most_common(4),
            }
        )

    final_retentions = [
        float(result["metrics"][-1]["retention_from_start"])
        for result in run_results
        if result.get("metrics")
    ]
    return {
        "suite_id": suite_id,
        "runs": [
            {
                "run_id": item["run_id"],
                "seed": item["seed"],
                "run_dir": item["run_dir"],
                "recommendation": item["verdict"]["recommendation"],
                "final_retention_from_start": item["verdict"]["final_retention_from_start"],
                "weakest_episode": item["verdict"].get("weakest_episode"),
                "paywall_candidate": item["verdict"].get("paywall_candidate"),
            }
            for item in run_results
        ],
        "final_retention": {
            "mean": mean(final_retentions),
            "min": min(final_retentions) if final_retentions else 0.0,
            "max": max(final_retentions) if final_retentions else 0.0,
        },
        "recommendation_counts": dict(recommendation_counts),
        "episode_rows": episode_rows,
        "top_drop_beats_across_runs": all_drop_beats.most_common(8),
        "judgement": {
            "total_reactions": total_reactions,
            "changed_count": judgement_changes,
            "changed_rate": judgement_changes / total_reactions if total_reactions else 0.0,
            "top_emotion_to_judgement": [
                {"text": text, "count": count}
                for text, count in emotion_to_judgement.most_common(8)
            ],
        },
    }


def render_suite_report(manifest: dict[str, Any], summary: dict[str, Any]) -> str:
    lines = [
        f"# {Path(manifest['story_path']).stem.replace('_', ' ').title()} - Audience Simulation Suite Report",
        "",
        (
            f"Suite `{manifest['suite_id']}` | {manifest['repeats']} main-loop runs | "
            f"{manifest['personas_per_run']} personas/run | model `{manifest['model']}` | "
            f"reasoning `{manifest['reasoning_effort']}` | judgement `{manifest['judgement_mode']}`"
        ),
        "> Uncalibrated simulator output. Use agreement across runs as directional signal, not calibrated audience truth.",
        "",
        "## Verdict Across Runs",
        "",
        f"- Recommendation counts: {summary['recommendation_counts']}",
        (
            "- Final retained index: "
            f"mean {summary['final_retention']['mean'] * 100:.1f}, "
            f"range {summary['final_retention']['min'] * 100:.1f}-{summary['final_retention']['max'] * 100:.1f}."
        ),
        (
            f"- Judge changed {summary['judgement']['changed_count']} of "
            f"{summary['judgement']['total_reactions']} persona-episode reactions "
            f"({pct(summary['judgement']['changed_rate']).strip()})."
        ),
        "",
        "## Episode Stability",
        "",
        "| Ep | Title | Mean continue | Range | Mean retained idx | Mean pay | Craving delta | Mean drops | Top drop beats |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["episode_rows"]:
        beats = ", ".join(f"{beat} ({count})" for beat, count in row["top_drop_beats"]) or "-"
        lines.append(
            f"| {row['episode_no']} | {row['title']} | "
            f"{pct(row['mean_continue_rate']).strip()} | "
            f"{pct(row['min_continue_rate']).strip()}-{pct(row['max_continue_rate']).strip()} | "
            f"{row['mean_retained_index']:.1f} | "
            f"{pct(row['mean_pay_rate']).strip()} | "
            f"{row['mean_craving_delta']:.2f} | "
            f"{row['mean_drop_count']:.1f} | {beats} |"
        )

    lines.extend(["", "## Run Details", "", "| Run | Seed | Recommendation | Final idx | Weakest ep | Paywall candidate |", "|---|---:|---|---:|---|---|"])
    for row in summary["runs"]:
        weakest = row.get("weakest_episode") or {}
        paywall = row.get("paywall_candidate") or {}
        lines.append(
            f"| `{row['run_id']}` | {row['seed']} | {row['recommendation']} | "
            f"{row['final_retention_from_start'] * 100:.1f} | "
            f"{weakest.get('episode_no', '-')} {weakest.get('title', '')} | "
            f"{paywall.get('episode_no', '-')} {paywall.get('title', '')} |"
        )

    lines.extend(["", "## Emotion To Judgement Signals", ""])
    for item in summary["judgement"]["top_emotion_to_judgement"]:
        lines.append(f"- {item['count']} agent-episodes: {item['text']}")

    lines.extend(
        [
            "",
            "## Methods",
            "",
            "- Main loop per repeat: LLM story beats -> seeded persona panel -> LLM persona reaction -> LLM judge final decision -> state update -> next episode.",
            f"- Episode intelligence mode: `{manifest['episode_intel_mode']}`.",
            f"- Guardrail mode: `{manifest['guardrail_mode']}`; judge decisions are LLM decisions, not parser decisions.",
            "- Individual run reports live in each repeat run directory under this suite directory.",
        ]
    )
    return "\n".join(lines) + "\n"


def mean(values: list[float] | list[int]) -> float:
    return sum(values) / len(values) if values else 0.0
