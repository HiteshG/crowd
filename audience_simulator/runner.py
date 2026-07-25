from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .artifacts import write_run_artifacts
from .cohorts import generate_india_english_population, init_state
from .engine import IndiaEnglishHeuristicEngine
from .ingest import parse_episodes, story_version
from .insights import build_insights
from .metrics import aggregate_metrics, build_verdict
from .models import Reaction
from .storage import write_sqlite


def run_audience_simulation(
    story_path: Path,
    out_dir: Path,
    personas: int,
    seed: int,
    run_id: str | None = None,
    expect_episodes: int | None = None,
    episode_mode: str = "headings",
    notes: str = "",
    engine_kind: str = "heuristic",
    model: str = "gpt-5-mini",
) -> dict[str, Any]:
    story_text = story_path.read_text(encoding="utf-8")
    episodes = parse_episodes(story_text, mode=episode_mode)
    if not episodes:
        raise ValueError(f"No episodes found in {story_path}")
    if expect_episodes is not None and len(episodes) != expect_episodes:
        raise ValueError(
            f"Expected {expect_episodes} episodes, found {len(episodes)} in {story_path}"
        )

    version = story_version(episodes)
    resolved_run_id = run_id or f"in-en-{version}-{int(time.time())}"
    run_dir = out_dir / resolved_run_id
    population = generate_india_english_population(personas, seed)
    engine: Any
    if engine_kind == "llm":
        from .llm_engine import OpenAIResponsesEngine

        engine = OpenAIResponsesEngine(seed=seed, model=model)
    elif engine_kind == "heuristic":
        engine = IndiaEnglishHeuristicEngine(seed=seed)
    else:
        raise ValueError(f"Unknown engine '{engine_kind}'")

    reactions: list[Reaction] = []
    for persona in population:
        state = init_state(persona)
        for episode in episodes:
            if not state.active:
                break
            reaction, state = engine.react(resolved_run_id, persona, state, episode)
            reactions.append(reaction)

    metrics = aggregate_metrics(resolved_run_id, len(population), episodes, reactions)
    insights = build_insights(episodes, reactions, metrics, population)
    verdict = build_verdict(
        run_id=resolved_run_id,
        cohort_name=engine.cohort_name,
        population_size=len(population),
        episode_count=len(episodes),
        metrics=metrics,
    )
    verdict["insights"] = insights
    run_record = {
        "run_id": resolved_run_id,
        "created_at": int(time.time()),
        "story_path": str(story_path),
        "story_version": version,
        "cohort_name": engine.cohort_name,
        "population_size": len(population),
        "episode_count": len(episodes),
        "episode_mode": episode_mode,
        "seed": seed,
        "engine": engine.engine_name,
        "engine_kind": engine_kind,
        "model": model if engine_kind == "llm" else None,
        "notes": notes,
        "artifacts": {
            "manifest": "manifest.json",
            "cohort_card": "cohort_card.json",
            "personas": "personas.jsonl",
            "reactions": "reactions.jsonl",
            "metrics": "metrics.json",
            "verdict": "verdict.json",
            "report": "report.md",
            "sqlite": "run.sqlite",
        },
    }

    write_run_artifacts(run_dir, run_record, population, reactions, metrics, verdict)
    write_sqlite(run_dir / "run.sqlite", run_record, population, reactions, metrics)
    return {
        "run_id": resolved_run_id,
        "run_dir": str(run_dir),
        "episodes": episodes,
        "cohort": engine.cohort_name,
        "engine": engine.engine_name,
        "population_size": len(population),
        "metrics": metrics,
        "verdict": verdict,
    }
