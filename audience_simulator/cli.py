from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .cohorts import INDIA_ENGLISH_COHORT_NAME, generate_india_english_population, init_state
from .ingest import parse_episodes
from .prompting import build_llm_reaction_payload
from .runner import run_audience_simulation
from .utils import pct


def cmd_run(args: argparse.Namespace) -> int:
    try:
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

    population = generate_india_english_population(args.personas, args.seed)
    persona = population[min(args.persona_index, len(population) - 1)]
    payload = build_llm_reaction_payload(persona, init_state(persona), episode)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_population(args: argparse.Namespace) -> int:
    population = generate_india_english_population(args.personas, args.seed)
    if args.summary:
        print_population_summary(population)
        return 0
    for persona in population:
        print(json.dumps(persona.__dict__, ensure_ascii=False, sort_keys=True))
    return 0


def print_summary(result: dict) -> None:
    verdict = result["verdict"]
    metrics = result["metrics"]
    print(f"Run: {result['run_id']}")
    print(f"Cohort: {result['cohort']}")
    print(f"Engine: {result['engine']}")
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
        "--model",
        default="gpt-5-mini",
        help="OpenAI model used only with --engine llm.",
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
    prompt_parser.set_defaults(func=cmd_prompt)

    pop_parser = subparsers.add_parser("population", help="Print generated India/English personas as JSONL.")
    pop_parser.add_argument("--personas", type=int, default=50, help="Synthetic listener count.")
    pop_parser.add_argument("--seed", type=int, default=7, help="Population seed.")
    pop_parser.add_argument("--summary", action="store_true", help="Print an auditable distribution summary.")
    pop_parser.set_defaults(func=cmd_population)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "personas", 1) < 1:
        print("error: --personas must be >= 1", file=sys.stderr)
        return 2
    return args.func(args)
