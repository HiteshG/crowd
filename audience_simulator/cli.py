from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .cohorts import INDIA_ENGLISH_COHORT_NAME, generate_india_english_population, init_state
from .env import default_max_workers, default_openai_model, default_reasoning_effort, load_dotenv
from .episode_intelligence import build_episode_intelligence
from .ingest import parse_episodes
from .prompting import build_llm_reaction_payload
from .runner import run_audience_simulation
from .utils import pct


def cmd_run(args: argparse.Namespace) -> int:
    try:
        if args.repeats > 1:
            from .suite import run_audience_simulation_suite

            suite_result = run_audience_simulation_suite(
                story_path=Path(args.story),
                out_dir=Path(args.out),
                personas=args.personas,
                seed=args.seed,
                repeats=args.repeats,
                run_id=args.run_id,
                expect_episodes=args.expect_episodes,
                episode_mode=args.episode_mode,
                notes=args.notes,
                engine_kind=args.engine,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                persona_mode=args.persona_mode,
                report_mode=args.report_mode,
                max_workers=args.max_workers,
                progress=not args.no_progress,
                checkpoint=not args.no_checkpoint,
                episode_intel_mode=args.episode_intel,
                guardrail_mode="off" if args.no_behavioral_guardrails else args.guardrail_mode,
                judgement_mode=args.judgement_mode,
            )
            print_suite_summary(suite_result)
            print(f"\nSuite artifacts written to {suite_result['suite_dir']}")
            return 0
        result = run_audience_simulation(
            story_path=Path(args.story),
            out_dir=Path(args.out),
            personas=args.personas,
            seed=args.seed,
            run_id=args.run_id,
            expect_episodes=args.expect_episodes,
            episode_mode=args.episode_mode,
            notes=args.notes,
            engine_kind=args.engine,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            persona_mode=args.persona_mode,
            report_mode=args.report_mode,
            max_workers=args.max_workers,
            progress=not args.no_progress,
            checkpoint=not args.no_checkpoint,
            episode_intel_mode=args.episode_intel,
            guardrail_mode="off" if args.no_behavioral_guardrails else args.guardrail_mode,
            judgement_mode=args.judgement_mode,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print_summary(result)
    print(f"\nArtifacts written to {result['run_dir']}")
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    story_text = Path(args.story).read_text(encoding="utf-8")
    episodes = parse_episodes(story_text, mode=args.episode_mode)
    if not episodes:
        print(f"error: no episodes found in {args.story}", file=sys.stderr)
        return 2
    episode = next((item for item in episodes if item.episode_no == args.episode), None)
    if episode is None:
        print(f"error: episode {args.episode} not found", file=sys.stderr)
        return 2
    if args.episode_intel == "llm":
        try:
            from .llm_beats import generate_llm_episode_beats

            episode = generate_llm_episode_beats(
                [episode],
                model=args.model,
                seed=args.seed,
                reasoning_effort=args.reasoning_effort,
            )[0]
            episodes = [episode]
        except (RuntimeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    try:
        population = generate_india_english_population(args.personas, args.seed)
        if args.persona_mode == "llm":
            from .llm_personas import enrich_personas_with_llm

            population = enrich_personas_with_llm(
                population,
                model=args.model,
                seed=args.seed,
                reasoning_effort=args.reasoning_effort,
            )
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    persona = population[min(args.persona_index, len(population) - 1)]
    episode_intelligence = (
        build_episode_intelligence(episodes).get(episode.episode_no)
        if args.episode_intel != "off"
        else None
    )
    payload = build_llm_reaction_payload(persona, init_state(persona), episode, episode_intelligence)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_population(args: argparse.Namespace) -> int:
    try:
        population = generate_india_english_population(args.personas, args.seed)
        if args.persona_mode == "llm":
            from .llm_personas import enrich_personas_with_llm

            population = enrich_personas_with_llm(
                population,
                model=args.model,
                seed=args.seed,
                reasoning_effort=args.reasoning_effort,
            )
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.summary:
        print_population_summary(population)
        return 0
    for persona in population:
        print(json.dumps(persona.__dict__, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_beats(args: argparse.Namespace) -> int:
    story_text = Path(args.story).read_text(encoding="utf-8")
    episodes = parse_episodes(story_text, mode=args.episode_mode)
    if args.episode is not None:
        episodes = [episode for episode in episodes if episode.episode_no == args.episode]
    if not episodes:
        print(f"error: no matching episodes found in {args.story}", file=sys.stderr)
        return 2
    if args.episode_intel == "llm":
        try:
            from .llm_beats import generate_llm_episode_beats

            episodes = generate_llm_episode_beats(
                episodes,
                model=args.model,
                seed=args.seed,
                reasoning_effort=args.reasoning_effort,
            )
        except (RuntimeError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    intelligence = build_episode_intelligence(episodes)
    print(json.dumps(beat_map_output(episodes, intelligence), ensure_ascii=False, indent=2))
    return 0


def beat_map_output(
    episodes: list,
    intelligence: dict[int, dict],
) -> list[dict]:
    output = []
    for episode in episodes:
        intel_by_beat = {
            row["beat_id"]: row
            for row in intelligence.get(episode.episode_no, {}).get("beat_table", [])
        }
        output.append(
            {
                "episode_no": episode.episode_no,
                "title": episode.title,
                "beat_source": intelligence.get(episode.episode_no, {}).get("beat_source", "parser"),
                "ending": intelligence.get(episode.episode_no, {}).get("ending"),
                "beats": [
                    {
                        "beat_id": beat.beat_id,
                        "label": beat.label,
                        "purpose": intel_by_beat.get(beat.beat_id, {}).get("purpose") or beat.purpose,
                        "line_start": beat.line_start,
                        "line_end": beat.line_end,
                        "speaker_focus": list(beat.speaker_focus),
                        "risk": intel_by_beat.get(beat.beat_id, {}).get("churn_risk")
                        or beat.audience_decision_risk,
                        "risk_score": intel_by_beat.get(beat.beat_id, {}).get("risk_score"),
                        "risk_reason": intel_by_beat.get(beat.beat_id, {}).get("note")
                        or beat.risk_reason,
                        "emotional_intensity": intel_by_beat.get(beat.beat_id, {}).get("emotional_intensity")
                        or beat.emotional_intensity,
                        "suspense": intel_by_beat.get(beat.beat_id, {}).get("suspense")
                        or beat.suspense,
                        "craving_effect": beat.craving_effect,
                        "quote": " ".join(beat.text.split())[:320],
                    }
                    for beat in episode.beats
                ],
            }
        )
    return output


def print_summary(result: dict) -> None:
    verdict = result["verdict"]
    metrics = result["metrics"]
    print(f"Run: {result['run_id']}")
    print(f"Cohort: {result['cohort']}")
    print(f"Engine: {result['engine']}")
    print(f"Persona mode: {result['persona_mode']}")
    print(f"Report mode: {result['report_mode']}")
    print(f"Population: {result['population_size']} synthetic listeners")
    print(f"Episodes: {len(result['episodes'])}")
    print("\nUncalibrated simulated metrics. Use ranking and diagnosis until backtested.\n")
    print("Ep  Active  Continue  Retained  Pay Rate  Craving D  Entropy  Top Drop Beat  Title")
    print("-" * 98)
    for row in metrics:
        print(
            f"{row['episode_no']:>2}  "
            f"{row['active_before']:>6,}  "
            f"{pct(row['continue_rate']):>8}  "
            f"{pct(row['retention_from_start']):>8}  "
            f"{pct(row['pay_rate']):>8}  "
            f"{row['avg_craving_delta']:>9.2f}  "
            f"{row['prediction_entropy']:>7.2f}  "
            f"{(row['top_drop_beat'] or '-'):>13}  "
            f"{row['episode_title'][:28]}"
        )

    print("\nVerdict:")
    print(f"- Recommendation: {verdict['recommendation']}")
    print(f"- Final retained from start: {pct(verdict['final_retention_from_start']).strip()}")
    if verdict["weakest_episode"]:
        weakest = verdict["weakest_episode"]
        print(
            f"- Weakest episode: {weakest['episode_no']} ({weakest['title']}), "
            f"{pct(weakest['continue_rate']).strip()} continue"
        )
    if verdict["paywall_candidate"]:
        paywall = verdict["paywall_candidate"]
        print(
            f"- Paywall candidate: episode {paywall['episode_no']} ({paywall['title']}), "
            f"{pct(paywall['pay_rate']).strip()} pay"
        )


def print_suite_summary(result: dict) -> None:
    summary = result["summary"]
    print(f"Suite: {result['suite_id']}")
    print(f"Runs: {len(result['runs'])}")
    print(f"Final retained index mean: {summary['final_retention']['mean'] * 100:.1f}")
    print(
        "Final retained index range: "
        f"{summary['final_retention']['min'] * 100:.1f}-"
        f"{summary['final_retention']['max'] * 100:.1f}"
    )
    print(f"Recommendation counts: {summary['recommendation_counts']}")
    print(
        "Judge decision changes: "
        f"{summary['judgement']['decision_changed_count']}/"
        f"{summary['judgement']['total_reactions']} "
        f"({pct(summary['judgement']['decision_changed_rate']).strip()})"
    )
    print(
        "Judge reasoning rewrites: "
        f"{summary['judgement']['reasoning_changed_count']}/"
        f"{summary['judgement']['total_reactions']} "
        f"({pct(summary['judgement']['reasoning_changed_rate']).strip()})"
    )
    print("\nEpisode mean continue:")
    for row in summary["episode_rows"]:
        print(
            f"- Ep {row['episode_no']} {row['title']}: "
            f"{pct(row['mean_continue_rate']).strip()} "
            f"(range {pct(row['min_continue_rate']).strip()}-"
            f"{pct(row['max_continue_rate']).strip()})"
        )


def print_population_summary(population: list) -> None:
    print(f"Cohort: {INDIA_ENGLISH_COHORT_NAME}")
    print(f"Population: {len(population)} synthetic listeners")
    print("")
    print_counter("Listening Settings", Counter(persona.cohort_label for persona in population))
    print_counter("Story Need Regions", Counter(persona.region_label for persona in population))
    print_counter("MBTI", Counter(persona.mbti for persona in population), limit=16)
    print_counter("City Tier", Counter(f"Tier {persona.city_tier}" for persona in population))
    print_counter("Coin Spend Tier", Counter(persona.coin_spend_tier for persona in population))
    print_counter("Discovery Channel", Counter(persona.discovery_channel for persona in population))


def print_counter(label: str, counter: Counter, limit: int = 10) -> None:
    print(label)
    for name, count in counter.most_common(limit):
        print(f"- {name}: {count}")
    print("")


def build_parser() -> argparse.ArgumentParser:
    model_default = default_openai_model()
    reasoning_default = default_reasoning_effort()
    max_workers_default = default_max_workers()
    parser = argparse.ArgumentParser(
        prog="audience-sim",
        description="Audience simulation harness for India/English serialized audio-fiction listeners.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the full simulation and write artifacts.")
    run_parser.add_argument("story", help="Markdown/plain-text story with Episode headings.")
    run_parser.add_argument("--personas", type=int, default=50, help="Synthetic listener count.")
    run_parser.add_argument("--expect-episodes", type=int, default=8, help="Validate exact episode count.")
    run_parser.add_argument(
        "--episode-mode",
        choices=["headings", "separator"],
        default="headings",
        help="Use Episode headings or split every markdown --- section as a simulation unit.",
    )
    run_parser.add_argument("--seed", type=int, default=7, help="Deterministic population/simulation seed.")
    run_parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Run the complete main loop N times with seeds seed..seed+N-1 and write a suite report.",
    )
    run_parser.add_argument("--out", default="runs", help="Output directory for immutable run artifacts.")
    run_parser.add_argument("--run-id", help="Optional explicit run id.")
    run_parser.add_argument("--notes", default="", help="Free-text notes stored in manifest.")
    run_parser.add_argument(
        "--engine",
        choices=["heuristic", "llm"],
        default="heuristic",
        help="Use deterministic local simulation or an OpenAI LLM reaction engine.",
    )
    run_parser.add_argument(
        "--persona-mode",
        choices=["seed", "llm"],
        default="seed",
        help="Use auditable seed personas or LLM-enriched persona prose generated on the fly.",
    )
    run_parser.add_argument(
        "--report-mode",
        choices=["deterministic", "llm"],
        default="deterministic",
        help="Use deterministic report writing or one OpenAI call for the final report.",
    )
    run_parser.add_argument(
        "--model",
        default=model_default,
        help="OpenAI model used with --engine llm, --persona-mode llm, and/or --report-mode llm.",
    )
    run_parser.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        default=reasoning_default,
        help="Reasoning effort for OpenAI reaction and report calls.",
    )
    run_parser.add_argument(
        "--max-workers",
        type=int,
        default=max_workers_default,
        help="Concurrent persona reaction calls per episode when using --engine llm.",
    )
    run_parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable stderr progress logs and progress.jsonl.",
    )
    run_parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Disable checkpoint.json and reactions.partial.jsonl writes during the run.",
    )
    run_parser.add_argument(
        "--episode-intel",
        choices=["auto", "llm", "heuristic", "off"],
        default="auto",
        help=(
            "Build Episode Intelligence before simulation. auto uses LLM beat generation "
            "for --engine llm and heuristic parser beats otherwise."
        ),
    )
    run_parser.add_argument(
        "--guardrail-mode",
        choices=["advisory", "override", "off"],
        default="advisory",
        help=(
            "How Episode Intelligence affects LLM reactions: advisory records pressure only, "
            "override can flip optimistic continue decisions, off disables the layer."
        ),
    )
    run_parser.add_argument(
        "--no-behavioral-guardrails",
        action="store_true",
        help="Alias for --guardrail-mode off.",
    )
    run_parser.add_argument(
        "--judgement-mode",
        choices=["auto", "llm", "off"],
        default="auto",
        help="Run an LLM judge after each persona reaction. auto enables it for --engine llm.",
    )
    run_parser.set_defaults(func=cmd_run)

    prompt_parser = subparsers.add_parser("prompt", help="Emit one LLM reaction payload for inspection.")
    prompt_parser.add_argument("story", help="Markdown/plain-text story file.")
    prompt_parser.add_argument("--episode", type=int, default=1, help="Episode number.")
    prompt_parser.add_argument(
        "--episode-mode",
        choices=["headings", "separator"],
        default="headings",
        help="Use Episode headings or split every markdown --- section as a simulation unit.",
    )
    prompt_parser.add_argument("--personas", type=int, default=50, help="Generated persona pool size.")
    prompt_parser.add_argument("--persona-index", type=int, default=0, help="Persona index from generated pool.")
    prompt_parser.add_argument("--seed", type=int, default=7, help="Population seed.")
    prompt_parser.add_argument(
        "--persona-mode",
        choices=["seed", "llm"],
        default="seed",
        help="Use auditable seed personas or LLM-enriched persona prose generated on the fly.",
    )
    prompt_parser.add_argument(
        "--model",
        default=model_default,
        help="OpenAI model used with --persona-mode llm.",
    )
    prompt_parser.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        default=reasoning_default,
        help="Reasoning effort for LLM persona enrichment.",
    )
    prompt_parser.add_argument(
        "--episode-intel",
        choices=["llm", "heuristic", "off"],
        default="heuristic",
        help="Choose parser/heuristic or LLM-generated beat map in the inspection payload.",
    )
    prompt_parser.set_defaults(func=cmd_prompt)

    pop_parser = subparsers.add_parser("population", help="Print generated India/English personas as JSONL.")
    pop_parser.add_argument("--personas", type=int, default=50, help="Synthetic listener count.")
    pop_parser.add_argument("--seed", type=int, default=7, help="Population seed.")
    pop_parser.add_argument(
        "--persona-mode",
        choices=["seed", "llm"],
        default="seed",
        help="Use auditable seed personas or LLM-enriched persona prose generated on the fly.",
    )
    pop_parser.add_argument(
        "--model",
        default=model_default,
        help="OpenAI model used with --persona-mode llm.",
    )
    pop_parser.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        default=reasoning_default,
        help="Reasoning effort for LLM persona enrichment.",
    )
    pop_parser.add_argument("--summary", action="store_true", help="Print an auditable distribution summary.")
    pop_parser.set_defaults(func=cmd_population)

    beats_parser = subparsers.add_parser("beats", help="Print the episode beat map for inspection.")
    beats_parser.add_argument("story", help="Markdown/plain-text story file.")
    beats_parser.add_argument("--episode", type=int, help="Optional single episode number.")
    beats_parser.add_argument(
        "--episode-mode",
        choices=["headings", "separator"],
        default="headings",
        help="Use Episode headings or split every markdown --- section as a simulation unit.",
    )
    beats_parser.add_argument("--seed", type=int, default=7, help="Beat-generation seed context.")
    beats_parser.add_argument(
        "--episode-intel",
        choices=["llm", "heuristic"],
        default="heuristic",
        help="Use parser beats with heuristic scoring or LLM-generated beats with heuristic scoring.",
    )
    beats_parser.add_argument(
        "--model",
        default=model_default,
        help="OpenAI model used with --episode-intel llm.",
    )
    beats_parser.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        default=reasoning_default,
        help="Reasoning effort for LLM beat generation.",
    )
    beats_parser.set_defaults(func=cmd_beats)
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "personas", 1) < 1:
        print("error: --personas must be >= 1", file=sys.stderr)
        return 2
    if getattr(args, "repeats", 1) < 1:
        print("error: --repeats must be >= 1", file=sys.stderr)
        return 2
    if getattr(args, "max_workers", 1) < 1:
        print("error: --max-workers must be >= 1", file=sys.stderr)
        return 2
    return args.func(args)
