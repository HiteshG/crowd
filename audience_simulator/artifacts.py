from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from .cohorts import INDIA_ENGLISH_COHORT_CARD
from .models import Persona, Reaction
from .report_agent import build_report_agent
from .utils import json_dumps


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


def write_report(path: Path, run_record: dict[str, Any], verdict: dict[str, Any]) -> None:
    agent = build_report_agent(
        str(run_record.get("report_mode", "deterministic")),
        model=run_record.get("report_model"),
        seed=int(run_record.get("seed", 7)),
        reasoning_effort=str(run_record.get("reasoning_effort", "medium")),
    )
    path.write_text(agent.render(run_record, verdict), encoding="utf-8")


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
    write_json(run_dir / "episode_intelligence.json", verdict.get("insights", {}).get("episode_intelligence", {}))
    write_json(run_dir / "llm_heuristic_bridge.json", verdict.get("insights", {}).get("llm_heuristic_bridge", {}))
    write_report(run_dir / "report.md", run_record, verdict)
