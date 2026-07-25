from __future__ import annotations

import dataclasses
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .artifacts import write_run_artifacts
from .cohorts import generate_india_english_population, init_state
from .engine import IndiaEnglishHeuristicEngine
from .episode_intelligence import build_episode_intelligence
from .ingest import parse_episodes, story_version
from .insights import build_insights
from .metrics import aggregate_metrics, build_verdict
from .models import Episode, Persona, PersonaState, Reaction
from .report_agent import report_agent_name
from .storage import write_sqlite
from .utils import json_dumps


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
    model: str = "gpt-5.6-luna",
    reasoning_effort: str = "medium",
    persona_mode: str = "seed",
    report_mode: str = "deterministic",
    max_workers: int = 8,
    progress: bool = True,
    checkpoint: bool = True,
    episode_intel_mode: str = "auto",
    guardrail_mode: str = "advisory",
    judgement_mode: str = "auto",
    behavioral_guardrails: bool | None = None,
) -> dict[str, Any]:
    if behavioral_guardrails is False:
        guardrail_mode = "off"
    if guardrail_mode not in {"advisory", "override", "off"}:
        raise ValueError(f"Unknown guardrail mode '{guardrail_mode}'")
    if reasoning_effort not in {"minimal", "low", "medium", "high"}:
        raise ValueError(f"Unknown reasoning effort '{reasoning_effort}'")
    requested_episode_intel_mode = episode_intel_mode
    episode_intel_mode = resolve_episode_intel_mode(
        requested_episode_intel_mode,
        engine_kind=engine_kind,
    )
    requested_judgement_mode = judgement_mode
    judgement_mode = resolve_judgement_mode(
        requested_judgement_mode,
        engine_kind=engine_kind,
    )
    started_at = time.time()
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
    run_dir.mkdir(parents=True, exist_ok=True)
    progress_log = ProgressLogger(run_dir, enabled=progress)
    progress_log.emit(
        "run_started",
        run_id=resolved_run_id,
        story_path=str(story_path),
        personas=personas,
        episodes=len(episodes),
        engine_kind=engine_kind,
        persona_mode=persona_mode,
        report_mode=report_mode,
        model=model,
        reasoning_effort=reasoning_effort,
        max_workers=max_workers,
        episode_intel_mode=episode_intel_mode,
        requested_episode_intel_mode=requested_episode_intel_mode,
        judgement_mode=judgement_mode,
        requested_judgement_mode=requested_judgement_mode,
        guardrail_mode=guardrail_mode,
    )
    if episode_intel_mode == "llm":
        from .llm_beats import generate_llm_episode_beats

        progress_log.emit(
            "episode_beat_generation_started",
            mode=episode_intel_mode,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        episodes = generate_llm_episode_beats(
            episodes,
            model=model,
            seed=seed,
            reasoning_effort=reasoning_effort,
            progress=lambda event, fields: progress_log.emit(event, **fields),
        )
        progress_log.emit(
            "episode_beat_generation_finished",
            episodes=len(episodes),
            total_beats=sum(len(episode.beats) for episode in episodes),
        )
        progress_log.emit("episode_intelligence_started", mode="heuristic_on_llm_beats")
        episode_intelligence = build_episode_intelligence(episodes)
        progress_log.emit("episode_intelligence_finished", episodes=len(episode_intelligence))
    elif episode_intel_mode == "heuristic":
        progress_log.emit("episode_intelligence_started", mode=episode_intel_mode)
        episode_intelligence = build_episode_intelligence(episodes)
        progress_log.emit("episode_intelligence_finished", episodes=len(episode_intelligence))
    elif episode_intel_mode == "off":
        episode_intelligence = {}
    else:
        raise ValueError(f"Unknown episode intelligence mode '{episode_intel_mode}'")
    progress_log.emit("population_started")
    population = generate_india_english_population(personas, seed)
    progress_log.emit("population_seeded", count=len(population))

    if persona_mode == "llm":
        from .llm_personas import enrich_personas_with_llm

        progress_log.emit("persona_enrichment_started", count=len(population), model=model)
        population = enrich_personas_with_llm(
            population,
            model=model,
            seed=seed,
            reasoning_effort=reasoning_effort,
        )
        progress_log.emit("persona_enrichment_finished", count=len(population), model=model)
    elif persona_mode != "seed":
        raise ValueError(f"Unknown persona mode '{persona_mode}'")
    if report_mode not in {"deterministic", "llm"}:
        raise ValueError(f"Unknown report mode '{report_mode}'")

    engine: Any
    if engine_kind == "llm":
        from .llm_engine import OpenAIResponsesEngine

        engine = OpenAIResponsesEngine(
            seed=seed,
            model=model,
            reasoning_effort=reasoning_effort,
            guardrail_mode=guardrail_mode,
            judgement_mode=judgement_mode,
        )
        engine.set_episode_intelligence(episode_intelligence)
    elif engine_kind == "heuristic":
        engine = IndiaEnglishHeuristicEngine(seed=seed)
    else:
        raise ValueError(f"Unknown engine '{engine_kind}'")

    uses_openai = (
        engine_kind == "llm"
        or persona_mode == "llm"
        or report_mode == "llm"
        or episode_intel_mode == "llm"
        or judgement_mode == "llm"
    )
    run_record = {
        "run_id": resolved_run_id,
        "created_at": int(started_at),
        "story_path": str(story_path),
        "story_version": version,
        "cohort_name": engine.cohort_name,
        "population_size": len(population),
        "episode_count": len(episodes),
        "episode_mode": episode_mode,
        "seed": seed,
        "engine": engine.engine_name,
        "engine_kind": engine_kind,
        "model": model if uses_openai else None,
        "reasoning_effort": reasoning_effort if uses_openai else None,
        "reaction_model": model if engine_kind == "llm" else None,
        "reaction_reasoning_effort": reasoning_effort if engine_kind == "llm" else None,
        "persona_mode": persona_mode,
        "persona_model": model if persona_mode == "llm" else None,
        "persona_reasoning_effort": reasoning_effort if persona_mode == "llm" else None,
        "report_mode": report_mode,
        "report_agent": report_agent_name(report_mode),
        "report_model": model if report_mode == "llm" else None,
        "report_reasoning_effort": reasoning_effort if report_mode == "llm" else None,
        "beat_generator": "llm" if episode_intel_mode == "llm" else "parser",
        "beat_model": model if episode_intel_mode == "llm" else None,
        "beat_reasoning_effort": reasoning_effort if episode_intel_mode == "llm" else None,
        "judgement_mode": judgement_mode,
        "requested_judgement_mode": requested_judgement_mode,
        "judgement_model": model if judgement_mode == "llm" else None,
        "judgement_reasoning_effort": reasoning_effort if judgement_mode == "llm" else None,
        "max_workers": max_workers,
        "progress": progress,
        "checkpoint": checkpoint,
        "requested_episode_intel_mode": requested_episode_intel_mode,
        "episode_intel_mode": episode_intel_mode,
        "guardrail_mode": guardrail_mode,
        "behavioral_guardrails": guardrail_mode != "off",
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
            "progress": "progress.jsonl",
            "checkpoint": "checkpoint.json",
            "partial_reactions": "reactions.partial.jsonl",
            "episode_intelligence": "episode_intelligence.json",
            "llm_heuristic_bridge": "llm_heuristic_bridge.json",
        },
    }

    reactions: list[Reaction] = []
    states = {persona.persona_id: init_state(persona) for persona in population}
    partial_reactions_path = run_dir / "reactions.partial.jsonl"
    if checkpoint:
        partial_reactions_path.write_text("", encoding="utf-8")
        _write_checkpoint(
            run_dir,
            run_record,
            completed_episodes=[],
            states=states,
            reactions=reactions,
            status="running",
        )

    completed_episodes: list[int] = []
    effective_workers = max(1, max_workers)
    for episode in episodes:
        active_personas = [persona for persona in population if states[persona.persona_id].active]
        progress_log.emit(
            "episode_started",
            episode_no=episode.episode_no,
            title=episode.title,
            active=len(active_personas),
        )
        episode_started_at = time.time()
        episode_results = _run_episode_reactions(
            engine=engine,
            run_id=resolved_run_id,
            active_personas=active_personas,
            states=states,
            episode=episode,
            max_workers=effective_workers if engine_kind == "llm" else 1,
        )
        for reaction, next_state in episode_results:
            states[reaction.persona_id] = next_state
            reactions.append(reaction)
        if checkpoint:
            _append_partial_reactions(partial_reactions_path, [reaction for reaction, _ in episode_results])
        completed_episodes.append(episode.episode_no)
        continue_count = sum(1 for reaction, _ in episode_results if reaction.will_continue)
        drop_count = len(episode_results) - continue_count
        progress_log.emit(
            "episode_finished",
            episode_no=episode.episode_no,
            active_before=len(episode_results),
            continued=continue_count,
            dropped=drop_count,
            elapsed_seconds=round(time.time() - episode_started_at, 2),
            total_reactions=len(reactions),
        )
        if checkpoint:
            _write_checkpoint(
                run_dir,
                run_record,
                completed_episodes=completed_episodes,
                states=states,
                reactions=reactions,
                status="running",
            )

    progress_log.emit("aggregation_started", total_reactions=len(reactions))
    metrics = aggregate_metrics(resolved_run_id, len(population), episodes, reactions)
    insights = build_insights(episodes, reactions, metrics, population, episode_intelligence)
    verdict = build_verdict(
        run_id=resolved_run_id,
        cohort_name=engine.cohort_name,
        population_size=len(population),
        episode_count=len(episodes),
        metrics=metrics,
    )
    verdict["insights"] = insights
    progress_log.emit("artifacts_started")
    write_run_artifacts(run_dir, run_record, population, reactions, metrics, verdict)
    write_sqlite(run_dir / "run.sqlite", run_record, population, reactions, metrics)
    if checkpoint:
        _write_checkpoint(
            run_dir,
            run_record,
            completed_episodes=completed_episodes,
            states=states,
            reactions=reactions,
            status="complete",
        )
    progress_log.emit(
        "run_finished",
        elapsed_seconds=round(time.time() - started_at, 2),
        total_reactions=len(reactions),
        run_dir=str(run_dir),
    )
    return {
        "run_id": resolved_run_id,
        "run_dir": str(run_dir),
        "episodes": episodes,
        "cohort": engine.cohort_name,
        "engine": engine.engine_name,
        "persona_mode": persona_mode,
        "report_mode": report_mode,
        "population_size": len(population),
        "metrics": metrics,
        "verdict": verdict,
    }


class ProgressLogger:
    def __init__(self, run_dir: Path, *, enabled: bool) -> None:
        self.enabled = enabled
        self.path = run_dir / "progress.jsonl"
        if self.enabled:
            self.path.write_text("", encoding="utf-8")

    def emit(self, event: str, **fields: Any) -> None:
        if not self.enabled:
            return
        payload = {"created_at": int(time.time()), "event": event, **fields}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json_dumps(payload) + "\n")
        message_bits = [f"{key}={value}" for key, value in fields.items() if key not in {"story_path"}]
        suffix = " " + " ".join(message_bits) if message_bits else ""
        print(f"[progress] {event}{suffix}", file=sys.stderr, flush=True)


def resolve_episode_intel_mode(requested: str, *, engine_kind: str) -> str:
    if requested == "auto":
        return "llm" if engine_kind == "llm" else "heuristic"
    if requested in {"llm", "heuristic", "off"}:
        return requested
    raise ValueError(f"Unknown episode intelligence mode '{requested}'")


def resolve_judgement_mode(requested: str, *, engine_kind: str) -> str:
    if requested == "auto":
        return "llm" if engine_kind == "llm" else "off"
    if requested in {"llm", "off"}:
        return requested
    raise ValueError(f"Unknown judgement mode '{requested}'")


def _run_episode_reactions(
    *,
    engine: Any,
    run_id: str,
    active_personas: list[Persona],
    states: dict[str, PersonaState],
    episode: Episode,
    max_workers: int,
) -> list[tuple[Reaction, PersonaState]]:
    if max_workers <= 1 or len(active_personas) <= 1:
        return [
            engine.react(run_id, persona, states[persona.persona_id], episode)
            for persona in active_personas
        ]

    results: list[tuple[Reaction, PersonaState] | None] = [None] * len(active_personas)
    workers = min(max_workers, len(active_personas))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(engine.react, run_id, persona, states[persona.persona_id], episode): index
            for index, persona in enumerate(active_personas)
        }
        for future in as_completed(futures):
            index = futures[future]
            results[index] = future.result()
    return [item for item in results if item is not None]


def _append_partial_reactions(path: Path, episode_reactions: list[Reaction]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for reaction in episode_reactions:
            handle.write(json_dumps(dataclasses.asdict(reaction)) + "\n")


def _write_checkpoint(
    run_dir: Path,
    run_record: dict[str, Any],
    *,
    completed_episodes: list[int],
    states: dict[str, PersonaState],
    reactions: list[Reaction],
    status: str,
) -> None:
    active_ids = [persona_id for persona_id, state in states.items() if state.active]
    payload = {
        "status": status,
        "run_id": run_record["run_id"],
        "updated_at": int(time.time()),
        "completed_episodes": completed_episodes,
        "active_persona_ids": active_ids,
        "reaction_count": len(reactions),
        "state_by_persona_id": {
            persona_id: dataclasses.asdict(state) for persona_id, state in states.items()
        },
    }
    (run_dir / "checkpoint.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
