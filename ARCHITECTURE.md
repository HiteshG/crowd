# ARCHITECTURE — Audience Simulator

The **agent harness**, laid out for easy explanation.

Read **README.md** for what it does. Read **DESIGN.md** for why the layers are shaped the way they are. This document shows *how the pieces connect*, module by module and step by step.

---

## 0. The one-slide summary

```
             ┌──────────┐
             │  script  │  (markdown / plain text with Episode headings)
             └────┬─────┘
                  ▼
           ┌────────────┐        ┌────────────────────────┐
           │  ingest    │ ─────► │  Episode Intelligence  │  ◄── LLM beats (optional)
           │ (parse →   │        │ (drivers, cohort fit,  │
           │  beats)    │        │  beat risk, endings)   │
           └─────┬──────┘        └──────────┬─────────────┘
                 │                          │
                 ▼                          │
       ┌──────────────────┐                 │
       │  cohorts sampler │ ──► personas.jsonl (audience)
       │ (seed → panel)   │        + optional LLM biography
       └────────┬─────────┘                 │
                │                           │
                └───────────┬───────────────┘
                            ▼
              ┌──────────────────────────────┐
              │      REACTION ENGINE          │
              │  heuristic  ┃  llm (Responses)│
              │             ┃  + judge (2nd)  │
              │             ┃  + guardrail    │
              └───────────┬──────────────────┘
                          │  Reaction per persona × episode
                          ▼
                 ┌───────────────────┐
                 │  metrics + verdict│
                 └────────┬──────────┘
                          ▼
              ┌──────────────────────────┐
              │  report agent            │
              │  deterministic ┃ llm     │
              └────────┬─────────────────┘
                       ▼
             runs/<run_id>/  ← manifest, personas.jsonl, reactions.jsonl,
                              metrics.json, verdict.json, report.md,
                              run.sqlite, progress.jsonl, checkpoint.json
```

Every arrow either passes plain dataclasses (`Persona`, `Episode`, `Beat`, `PersonaState`, `Reaction`) or writes an artifact. There is no shared mutable state.

---

## 1. Component-by-component breakdown

The harness is nine components. Each has one job.

### 1.1 CLI (`cli.py`)

Thin `argparse` layer. Four subcommands: `run`, `beats`, `population`, `prompt`. Loads `.env`, validates arguments, dispatches to `runner.run_audience_simulation` (or `suite.run_audience_simulation_suite` if `--repeats > 1`).

**Owns:** flag parsing, validation, summary printing.
**Does not own:** any simulation logic. Everything is delegated.

### 1.2 Runner (`runner.py`)

The main-loop orchestrator. One function, `run_audience_simulation`, that in order:

1. Reads the story and parses episodes.
2. Resolves the `episode_intel_mode` and `judgement_mode` (both accept `auto`, which picks LLM under `--engine llm` and heuristic otherwise).
3. If LLM beats requested → calls `llm_beats.generate_llm_episode_beats`.
4. Builds Episode Intelligence.
5. Generates the persona population; optionally enriches biographies via LLM.
6. Instantiates the engine (`IndiaEnglishHeuristicEngine` or `OpenAIResponsesEngine`).
7. Per episode: filters to active personas, fans out reactions via `ThreadPoolExecutor`, updates state, checkpoints.
8. Aggregates metrics, builds insights, builds verdict, writes artifacts, writes SQLite.

**Owns:** episode-by-episode control flow, checkpoint writes, progress emission.
**Does not own:** how a reaction is produced (delegated to engine).

### 1.3 Ingest (`ingest.py`)

Two modes: `headings` (regex on `## Episode N: title`) and `separator` (split on `\n---\n`). Emits `Episode` dataclasses with parser-produced beats (paragraph-block split, line-numbered, speaker-focus extracted). The parser output is the *fallback* beat map; `--episode-intel llm` replaces the beats but keeps the same `Beat` shape.

### 1.4 Cohorts (`cohorts.py`)

The audience-model definitions. `LISTENER_SEEDS` for the *when/how* axis; `NEED_REGIONS` for the *what for* axis. `generate_india_english_population(count, seed)` samples a `Persona` per slot under the seeded RNG.

The single point of truth for what a persona *is*. Every downstream module reads `Persona` and treats every field as immutable.

### 1.5 Episode Intelligence (`episode_intelligence.py`)

Structural read of the script, produced once, consumed by everyone. Per episode: driver scores, beat table with risk annotations, ending analysis, cohort-fit rankings, promise ledger update.

Also owns `persona_drop_guardrail` — the independent drop-pressure estimate that the LLM engine consults when `--guardrail-mode` is `advisory` or `override`.

### 1.6 Signals (`signals.py`)

Fixed keyword feature bank. Extracts numeric episode signals (`ambition`, `competence`, `justice_seeking`, `family`, `cliffhanger`, `ending_cliffhanger`, `ending_status_reveal`, …) from raw episode text. Shared by the heuristic engine, the guardrail, and Episode Intelligence, so heuristic-vs-LLM comparisons stay on the same feature basis.

### 1.7 Reaction engines

Two implementations of the same contract:

```python
def react(run_id, persona, state, episode) -> tuple[Reaction, PersonaState]
```

- **Heuristic** (`engine.IndiaEnglishHeuristicEngine`): deterministic, seed-driven, feature-×-driver dot product.
- **LLM** (`llm_engine.OpenAIResponsesEngine`): OpenAI Responses call with strict JSON schema, optional judge, optional guardrail override.

Same signature → runner does not care which one it holds.

### 1.8 Judge (`llm_judge.py`)

Second-pass LLM invoked from `OpenAIResponsesEngine._apply_judgement_layer` when `--judgement-mode llm`. Takes the raw reaction plus persona / state / episode / Episode Intelligence, returns a possibly-rewritten reaction plus `changed_decision` / `changed_reasoning` flags.

### 1.9 Metrics, insights, verdict, artifacts, storage

- `metrics.aggregate_metrics` — per-episode aggregates from `reactions.jsonl`.
- `insights.build_insights` — cohort curves, drop-beat inspector, paywall map, expectation scorecard, LLM-heuristic bridge.
- `metrics.build_verdict` — recommendation (`greenlight_for_pilot` / `revise_before_pilot` / `major_rewrite`), weakest episode, paywall candidate.
- `report_agent.build_report_agent` — deterministic templated markdown or single LLM call.
- `artifacts.write_run_artifacts` — writes every JSON/JSONL/md file.
- `storage.write_sqlite` — mirrors the same data into `run.sqlite` for querying.

---

## 2. Data flow for one reaction

Zoomed into the tightest inner loop — one persona, one episode. This is the atom of the harness.

```
    Persona ─────┐
    PersonaState┤
    Episode ────┤
    EpisodeIntelligence[ep_no] ─┐
                                ▼
                    ┌──────────────────────────┐
                    │  prompting.              │
                    │  build_llm_reaction_     │
                    │  payload(...)            │
                    └───────────┬──────────────┘
                                ▼
              ┌───────────────────────────────────┐
              │ OpenAI Responses API              │
              │   model: gpt-5.6-luna (or fallback)│
              │   text.format.json_schema (strict)│
              │   reasoning.effort: medium        │
              └───────────┬───────────────────────┘
                          ▼
              raw_reaction (validated against REACTION_SCHEMA)
                          │
                ┌─────────┴──────────┐
                ▼ (--judgement=llm)  ▼ (--judgement=off)
           ┌──────────┐          raw_reaction passes through
           │  Judge   │
           │  (2nd    │
           │  LLM)    │
           └────┬─────┘
                ▼
        judged_reaction + judgement_meta
                │
                ▼
     ┌──────────────────────────┐
     │ guardrail_adjustment     │  ← Episode Intelligence + persona region
     │ (--guardrail advisory/   │
     │  override/off)           │
     └───────────┬──────────────┘
                 ▼
   Reaction (frozen dataclass) + next PersonaState
                 │
                 ▼
   append to reactions[] (in-memory) and
              reactions.partial.jsonl (crash-safe)
```

The heuristic path replaces the "OpenAI Responses API" box with a pure function; everything upstream and downstream is identical. That symmetry is the point.

---

## 3. Every artifact and who writes it

Every path is relative to `runs/<run_id>/`. Every write is done by exactly one module — no shared writes.

| Artifact | Writer | When | Purpose |
|---|---|---|---|
| `manifest.json` | `artifacts` | After run | Reproducibility record — every mode flag, model, seed |
| `cohort_card.json` | `artifacts` | After run | The need-region taxonomy this run used |
| `personas.jsonl` | `artifacts` | After run | One line per persona (frozen `Persona` dataclass) |
| `reactions.jsonl` | `artifacts` | After run | One line per persona × episode |
| `metrics.json` | `artifacts` | After run | Per-episode aggregates |
| `verdict.json` | `artifacts` | After run | Recommendation + insights payload |
| `report.md` | `report_agent` (via `artifacts.write_report`) | After run | Human-readable writeup |
| `episode_intelligence.json` | `artifacts` | After run | Structural read of every episode |
| `llm_heuristic_bridge.json` | `artifacts` | After run | Where LLM and heuristic disagree per episode |
| `run.sqlite` | `storage` | After run | Queryable copy of runs / personas / reactions / metrics |
| `progress.jsonl` | `runner.ProgressLogger` | Streaming | Event log; `[progress]` also echoed to stderr |
| `checkpoint.json` | `runner._write_checkpoint` | After each episode | Resumable state (completed episodes, active personas, state per persona) |
| `reactions.partial.jsonl` | `runner._append_partial_reactions` | After each episode | Crash-safe copy of reactions written so far |

For suite runs, one extra layer:

| Artifact | Writer | Purpose |
|---|---|---|
| `<suite_dir>/suite_manifest.json` | `suite` | What ran, seed range, run IDs |
| `<suite_dir>/suite_summary.json` | `suite` | Recommendation counts, per-episode stability, judgement change rate |
| `<suite_dir>/suite_report.md` | `suite` | Rendered summary |
| `<suite_dir>/<run_id>/...` | delegated to `runner` | Full per-run artifacts, one folder each |

---

## 4. The mode matrix — every switch that changes behavior

The harness is a product of five independent switches. Any combination is legal.

| Switch | Values | Deterministic default | Consumes API |
|---|---|---|---|
| `--engine` | `heuristic`, `llm` | `heuristic` | reactions |
| `--persona-mode` | `seed`, `llm` | `seed` | persona biographies |
| `--episode-intel` | `auto`, `llm`, `heuristic`, `off` | `auto` (→ heuristic unless engine=llm) | beat segmentation |
| `--judgement-mode` | `auto`, `llm`, `off` | `auto` (→ llm iff engine=llm) | second-pass audit |
| `--report-mode` | `deterministic`, `llm` | `deterministic` | final report writing |
| `--guardrail-mode` | `advisory`, `override`, `off` | `advisory` | none — pure code |
| `--repeats` | integer ≥ 1 | `1` | multiplies everything |

The full LLM path is `--engine llm --persona-mode llm --episode-intel llm --judgement-mode llm --report-mode llm`. Any subset can be flipped back to deterministic for debugging or cost reasons.

---

## 5. The agent harness — what "agent" actually means here

There are **five agent-shaped roles** in this system. Each has an explicit contract, a named implementation, and an accountable artifact.

| # | Role | Deterministic agent | LLM agent | Contract | Artifact where its output lives |
|---|---|---|---|---|---|
| 1 | **Beat segmenter** | Paragraph-block parser (`ingest.make_beats`) | `llm_beats.generate_llm_episode_beats` (`beat_map_v1`) | `Episode.text → list[Beat]` | `episode_intelligence.json` (via `beats` on `Episode`) |
| 2 | **Persona biographer** | Distributional sampler (`cohorts.generate_india_english_population`) | `llm_personas.enrich_personas_with_llm` (`persona_enrichment_v1`) | `Persona (numeric skeleton) → Persona (with bio, persona, interested_topics)` | `personas.jsonl` |
| 3 | **Reaction agent** | `IndiaEnglishHeuristicEngine` (`india_english_heuristic_v1`) | `OpenAIResponsesEngine` (`openai_responses_llm_v1`) | `(persona, state, episode) → (Reaction, next_state)` | `reactions.jsonl` |
| 4 | **Judge** | Off | `OpenAIJudgementLayer` (`openai_reaction_judge_v1`) | `(raw_reaction, persona, state, episode, EI) → judged_reaction + meta` | `reactions.jsonl` (`judgement_*` fields) |
| 5 | **Report writer** | `DeterministicReportWritingAgent` (`deterministic_report_writer_v1`) | `OpenAIReportWritingAgent` (`openai_report_writer_v1`) | `(run_record, verdict) → markdown` | `report.md` |

Plus one non-agent structural pass:

| Structural pass | Where | Contract |
|---|---|---|
| **Episode Intelligence** | `episode_intelligence.build_episode_intelligence` | `list[Episode] → dict[episode_no, IntelligenceRecord]` |
| **Guardrail** | `episode_intelligence.persona_drop_guardrail` | `(persona, state, episode, EI, llm_result) → GuardrailAdjustment` |

**Why call these the "agent harness":** each row above is an independent decision-maker with a swappable implementation, a fixed input/output shape, and a named artifact. The harness is what wires them together, controls concurrency, records provenance, and enforces schema.

### 5.1 What the harness itself owns

- **Prompt construction** — `prompting.py` builds every LLM prompt. Reaction and judge agents share a compact-persona-card and behavioral-calibration payload so their views of the persona stay identical.
- **Schema enforcement** — `REACTION_SCHEMA`, `JUDGEMENT_SCHEMA`, `PERSONA_ENRICHMENT_SCHEMA`, `BEAT_MAP_SCHEMA`, `REPORT_SCHEMA`. Every LLM call is `strict: true`. Failures are counted and retried against fallback models before aborting.
- **Model fallback** — `env.openai_model_candidates` returns `[primary, ...fallbacks]`. Each candidate is tried on availability errors only; non-availability errors bubble immediately.
- **Concurrency** — `runner._run_episode_reactions` uses a `ThreadPoolExecutor` sized to `min(max_workers, len(active_personas))`. Between episodes: strictly sequential (state carries forward). Within an episode: parallel.
- **Checkpointing** — `runner._write_checkpoint` after every episode. `runner._append_partial_reactions` after every episode. A crash leaves everything up to that point on disk.
- **Progress** — `ProgressLogger` writes JSONL and stderr in tandem; every event carries a timestamp.
- **Determinism** — a per-call decision seed derived from `sha256(seed:run_id:persona_id:episode_no)` so the same inputs re-produce the same OpenAI request (subject to model behavior).

### 5.2 What the harness deliberately does not own

- Any decision about a persona's continue / drop / pay — that's the reaction agent.
- Any structural read of the script — that's Episode Intelligence.
- Any narrative interpretation of numbers — that's the report writer.
- Any calibration to real-world retention — that's the backtest that does not yet exist.

The harness is plumbing. Every judgement lives in a named component whose output is on disk.

---

## 6. Determinism and seeds

Two independent RNG sources:

1. **Population seed** — from `--seed`. Drives every sampled attribute in `cohorts.generate_india_english_population`. Reproduces the same audience.
2. **Per-reaction seed** — `sha256(seed:run_id:persona_id:episode_no)`. Drives the heuristic engine's per-reaction RNG *and* the LLM engine's `decision_seed` embedded in the prompt.

**Consequence:** the heuristic path is byte-for-byte reproducible under `(seed, run_id)`. The LLM path is reproducible up to model non-determinism (temperature, sampling, model version) — which is why suite mode measures across seeds instead of trusting a single run.

---

## 7. Failure modes and how each is contained

| Failure | Containment |
|---|---|
| Story has no episodes | `runner` raises `ValueError` before any state is written |
| Expected episode count mismatch | `--expect-episodes` validates and raises before any state is written |
| Model unavailable | Fallback list in `env.openai_model_candidates`; retry against next candidate |
| LLM returns non-JSON | Recorded as `RuntimeError` with truncated payload; run aborts (no silent bias) |
| LLM returns invalid schema | `_validate_reaction_payload` raises; run aborts |
| LLM hallucinates a beat_id | `_validated_drop_beat` substitutes `strongest_drop_beat(episode, persona)[0]` |
| Network transient | `urllib.error.URLError` → run aborts; `checkpoint.json` and `reactions.partial.jsonl` preserve everything up to that episode |
| Crash mid-run | Same as above — checkpoint + partial reactions are the resume point |
| Suite verdicts flip between seeds | `suite_summary.json` records `recommendation_counts` — flip visible in the summary |
| Persona region ↔ episode structural mismatch | Guardrail produces high pressure; either recorded (advisory) or applied (override); every override is logged with reason |

---

## 8. Reading the artifacts

The fastest ways to inspect a run:

```bash
# Human report
open runs/<run_id>/report.md

# Aggregate view
jq '.recommendation, .final_retention_from_start, .weakest_episode' runs/<run_id>/verdict.json

# Where did people drop within an episode?
jq '.[] | {ep: .episode_no, drops: .top_drop_beats}' runs/<run_id>/metrics.json

# One persona's full journey
jq 'select(.persona_id == "p_00007") | {ep: .episode_no, cont: .will_continue, beat: .drop_beat, reason: .continue_reason}' runs/<run_id>/reactions.jsonl

# Queryable
sqlite3 runs/<run_id>/run.sqlite '.tables'
sqlite3 runs/<run_id>/run.sqlite 'SELECT episode_no, AVG(will_continue) FROM reactions GROUP BY episode_no;'

# Suite stability
jq '.summary.episode_rows[] | {ep: .episode_no, mean: .mean_continue_rate, spread: [.min_continue_rate, .max_continue_rate]}' runs/<suite_id>/suite_summary.json
```

---

## 9. Extending the harness

The interfaces to preserve when adding an agent:

- **New reaction engine** — implement `react(run_id, persona, state, episode) -> tuple[Reaction, PersonaState]` and expose `cohort_name`, `engine_name`. Wire it in `runner` alongside the two existing engines.
- **New market** — new listener seeds and region weightings in `cohorts.py`. No downstream module changes. Add a `--market` flag once there are two.
- **New metric** — extend `metrics.aggregate_metrics` and add rendering in `report_agent`. Never write a new field into `verdict.json` whose name would assert a calibrated real-world prediction (`predicted_*`, `expected_retention`) — those field names are a smell that the tool has started claiming what it cannot back up.
- **New report agent** — implement `render(run_record, verdict) -> str` and register in `report_agent.build_report_agent`.
- **New judge** — implement the `judge(persona, state, episode, episode_intelligence, raw_reaction) -> (dict, meta)` contract in `llm_judge`.

Every one of those extensions is a new file plus a wiring change in the module that dispatches. No cross-cutting refactor is required — that's the payoff for keeping every agent behind a single-function contract.
