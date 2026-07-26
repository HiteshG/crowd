# Crowd — Audience Simulator

**A synthetic audience harness for serialized audio fiction.**

Crowd plays a script to a few hundred synthetic listeners, episode by episode, and turns their decisions into a ranked list of which episodes to fix, where to put the paywall, and which cohort the story is actually for.

The CLI entry point is `audience-sim`. The package is `audience_simulator`.

---

## Why this exists

Every writers' room has the same argument: *"episode 7 is fine, the drop is at 9."*
Nobody can prove it. Real analytics tell you where retention fell — never *why*, never *which of the six things you might change would move it*, and never before the episode ships.

Crowd is a focus group you can run on a laptop in an afternoon. It doesn't predict retention percentages. It answers the questions the room actually has:

- **Where should I spend limited rewrite hours?** — a Fix List ranks episodes by drop risk × active share × episodes remaining.
- **Did the rewrite actually work?** — same audience, v1 vs v2, paired delta. Persona bias cancels in the difference.
- **Who is this story for?** — six need-regions ranked, with the specific dealbreaker the script trips for each.
- **Is that cliffhanger actually a cliffhanger?** — prediction disagreement tells you whether listeners genuinely don't know what happens next, or already do and won't hurry back.
- **Which episode looks satisfying but is quietly killing the series?** — craving delta catches the episode that resolves too cleanly, invisible to a satisfaction score.

Reports say *"episode 7 is the weakest in this script; the rewrite recovers X points in paired simulation"* — never *"predicted retention: 34%."* Relative claims survive persona miscalibration. Absolute claims, with no data behind them, would be indefensible.

---

## What you get

| Capability | What it produces |
|---|---|
| **Episode ranking within a script** | Which episodes are weakest, relative to the rest |
| **Paired rewrite deltas (suite mode)** | Same audience across seeds, mean/range per episode |
| **Drop-beat localisation** | Which *beat* inside an episode most listeners abandoned on |
| **Cohort divergence** | Which of the six need-regions engages most (directional) |
| **Craving delta** | Post-episode craving minus mid-episode — catches over-resolved endings |
| **Prediction entropy** | Disagreement in what listeners think comes next — cliffhanger quality proxy |
| **Paywall placement** | Which episode has the highest willingness-to-pay signal |
| **Report + SQLite export** | Deterministic or LLM-authored markdown, plus a queryable `run.sqlite` |

---

## The mental model — it's a focus group

Each command is one step of running one.

| Command | Plain English |
|---|---|
| `beats` | Break the script into beats and show the beat map |
| `population` | Hire the test audience (seeded personas, optionally LLM-enriched prose) |
| `prompt` | Print one persona × one episode reaction prompt for inspection |
| `run` | Hold the screening — episode by episode, continue/drop, pay/not, then write the report |
| `run --repeats N` | Run the whole loop N times with rolling seeds; write a suite summary |

---

## Quickstart

The heuristic engine runs offline with no API key.

```bash
# 1. Install
python3 -m venv .venv
.venv/bin/pip install -e .

# 2. Optional: add OPENAI_API_KEY to .env for LLM modes
cp .env.example .env

# 3. See the beat map for a story (no API needed)
audience-sim beats sample_stories/house_on_kaveri_lane.md

# 4. Inspect the generated audience (no API needed)
audience-sim population --personas 25 --summary

# 5. Run a full deterministic simulation (no API needed)
audience-sim run sample_stories/house_on_kaveri_lane.md \
  --personas 50 --engine heuristic --run-id smoke-1
```

Artifacts land under `runs/smoke-1/` — manifest, personas, per-episode reactions, metrics, verdict, report, SQLite.

To use the LLM harness end-to-end (persona reactions, judge layer, LLM-authored report):

```bash
audience-sim run sample_stories/house_on_kaveri_lane.md \
  --personas 30 \
  --engine llm \
  --persona-mode llm \
  --report-mode llm \
  --episode-intel llm \
  --judgement-mode llm \
  --guardrail-mode advisory \
  --run-id kaveri-llm-1
```

To test stability across seeds (the suite loop that catches noise-driven verdicts):

```bash
audience-sim run sample_stories/house_on_kaveri_lane.md \
  --personas 50 --repeats 5 --seed 7 --run-id kaveri-suite
```

---

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e .
cp .env.example .env      # add OPENAI_API_KEY for LLM modes
```

Then either activate the venv or run entry points directly:

```bash
# Option A — activate
source .venv/bin/activate
audience-sim --help

# Option B — no activation
.venv/bin/audience-sim --help
```

Python 3.11+. Zero runtime dependencies for the core CLI — the LLM engine hits the OpenAI Responses API through `urllib`. The optional web UI adds three deps (see below).

### Troubleshooting install

- `zsh: no such file or directory: .venv/bin/pip` — you skipped `python3 -m venv .venv`. Run it first, then re-run the install line.
- `python3 -m venv .venv` errors on macOS — install `virtualenv` and use it instead:
  ```bash
  python3 -m pip install --user virtualenv
  python3 -m virtualenv .venv
  ```
- No venv at all — install to your user site:
  ```bash
  python3 -m pip install --user -e '.[web]'
  python3 -m webapp.server
  ```

---

## Web app — drop a script, watch it run, see the dashboard

A small FastAPI wrapper around the CLI. The user drops a script, watches the audience react episode by episode in real time, then the dashboard appears below.

### Install and run

```bash
# in the repo root, with a venv already created (see Install above)
.venv/bin/pip install -e '.[web]'
.venv/bin/crowd-web
```

If quoting gives zsh trouble, use double quotes: `pip install -e ".[web]"`.

Open http://127.0.0.1:8000. The port can be overridden with `CROWD_WEB_PORT=8001 crowd-web`.

### What it does

- **Drop a `.md` / `.txt` script** (or paste text). Configure personas, seed, engine (`heuristic` free / `llm` paid), and the per-layer modes.
- **Live episode-by-episode progress** — a pulsing "current episode" cell, a "N of M listeners still hooked" counter that ticks down per episode, a persona-dot grid where a dot turns red for every drop, and a streaming event log tailing `progress.jsonl`.
- **Dashboard reveals in place** when the run finishes — verdict, KPI strip, retention funnel, per-episode continue rate, craving delta (diverging), drop-beat inspector for the weakest three episodes, and a `report.md` download.

### How the plumbing works

- `POST /api/runs` spawns `python -m audience_simulator run …` as a subprocess and returns a `run_id`. **No LLM calls happen in the server itself** — the runner subprocess makes every network call.
- `GET /api/runs/{run_id}/events` opens an SSE stream. The server tails `runs/{run_id}/progress.jsonl` every ~350ms and forwards each new line to the browser.
- Inside the runner, each stage emits events the dashboard listens for:

  | Stage | Event | Triggers an LLM call when… |
  |---|---|---|
  | Parse script | `run_started` | — |
  | Beat generation | `episode_beat_generation_started` / `_finished` | `--episode-intel llm` (1 call per episode) |
  | Episode Intelligence | `episode_intelligence_started` / `_finished` | never (pure Python) |
  | Persona sampling | `population_seeded` | — |
  | Persona enrichment | `persona_enrichment_started` / `_finished` | `--persona-mode llm` (batched, ~10/batch) |
  | Per-episode reactions | `episode_started` → `episode_finished` | `--engine llm` (N parallel calls, N = active personas, via `ThreadPoolExecutor`) |
  | Judge | folded into reactions | `--judgement-mode llm` (1 extra call per reaction) |
  | Aggregation | `aggregation_started` | — |
  | Report | `artifacts_started` | `--report-mode llm` (1 call) |
  | Done | `run_finished` | — |

  For a 25-persona 8-episode full-LLM run: `8 + ⌈25/10⌉ + 25×8 + 25×8 + 1 ≈ 411 calls`.
- `GET /api/runs/{run_id}/summary` returns `verdict.json` + `metrics.json` when the run finishes; the browser renders the dashboard from that payload.
- Uploaded scripts land in `webapp/uploads/` (gitignored). Run artifacts live in `runs/{run_id}/` — the same layout the CLI writes.

### Environment variables

- `CROWD_WEB_HOST` (default `127.0.0.1`) — bind address.
- `CROWD_WEB_PORT` (default `8000`).
- `OPENAI_API_KEY` — required for any LLM-mode flag.

---

## Dashboard (standalone HTML)

Any suite run's `suite_summary.json` can be visualised without running the web app:

```bash
open dashboard.html
```

Drop a `suite_summary.json` from `runs/<suite_id>/` onto the file picker to re-render. This is the same chart set the web app uses.

---

## Two things no analytics dashboard can produce

Because real listeners never tell you what they *expected*.

**Craving delta** — `craving_end − craving_mid`. A satisfying, cleanly-resolved episode is a churn event on a serialized platform. Catches the episode that is *too well-resolved*. Needs a different fix from "boring."

**Prediction entropy** — disagreement across listeners' predictions of what happens next, bucketed into narrative frames (truth-or-proof, cover-up pressure, romance interruption…). High craving with *low* entropy means they already know what's coming and have no reason to hurry back. High craving with *high* entropy is what a working cliffhanger looks like.

Together with `drop_count × episodes_remaining` (the Fix List), these are why the report goes further than a dashboard could.

---

## How the audience is built (the short version)

One rule: **sample the numbers, generate the prose.**

The model never invents a numeric attribute. Every number a persona carries — driver intensities, session minutes, coin-spend tier, city tier — is drawn from a distribution declared in `audience_simulator/cohorts.py`. The LLM (when `--persona-mode llm`) only writes biography around that skeleton. Auditable, reproducible under a seed, and correctable when real data arrives.

Every persona lives on two axes:

- **Listening cohort** — *when and how do they listen?* (gig-worker marathon, domestic daytime, late-night private binger…) Owns session structure, tempo, payment tier. Determines the *shape* of the retention curve.
- **Need region** — *what do they want a story to do for them?* (Justice-Payoff Bingers, Slow-Burn Comfort Seekers, Tier-1 Aspirational Escapists…) Owns drivers, hooks, dealbreakers. Determines *which stories* retain them.

Neither subsumes the other. A gig worker on an eight-hour shift and a homemaker doing chores can both be Justice-Payoff listeners and drop at the same narrative failure — at different points on the clock.

Full rationale — evidence tiers, anti-stereotype slices, driver taxonomy, the join model — is in **DESIGN.md**.

---

## Modes and what they cost

Every axis of the harness can independently switch between deterministic and LLM.

|  | Deterministic (default) | LLM |
|---|---|---|
| **Beats** (`--episode-intel`) | Paragraph splitter + keyword scoring | LLM segments beats and scores decision risk |
| **Personas** (`--persona-mode`) | Distributional sampling only | Sampled skeleton + LLM-authored biography/prose |
| **Reactions** (`--engine`) | Rule-based drivers × episode signals | OpenAI Responses call per persona per episode, `strict: true` schema |
| **Judge** (`--judgement-mode`) | Off | Second-pass LLM audits the reaction against Episode Intelligence |
| **Report** (`--report-mode`) | Templated markdown from `verdict.json` | Single LLM call writes the report |

The heuristic path is free and instant. The full LLM path is `personas × episodes` API calls plus one report call — figure ~$5–15 for a 30-persona 8-episode script at `medium` reasoning effort.

---

## Guardrails, enforced not documented

- Episode Intelligence produces a per-persona *drop pressure* independently of the LLM reaction. In `advisory` mode it is logged; in `override` mode a high-pressure signal can flip an optimistic continue into a drop and record why.
- Drop-beat references are validated against the actual beat IDs of the episode. Hallucinated beat IDs are replaced with the strongest heuristic candidate.
- Reactions failing the JSON schema are retried against a fallback model list (`OPENAI_MODEL_FALLBACKS`) before the run aborts.
- A per-episode checkpoint writes `checkpoint.json` and `reactions.partial.jsonl` — a crash at episode 17 of 20 leaves 17 usable episodes and a resumable state.
- Suite mode records recommendation counts across seeds. If verdicts flip between "greenlight" and "revise" across seeds, the noise floor is louder than the signal.

---

## Layout

```
audience_simulator/
  cli.py                  argparse entry point (audience-sim)
  runner.py               main-loop orchestrator: parse → intel → personas → engine → aggregate
  suite.py                --repeats loop + suite report
  cohorts.py              India/English listener seeds, need regions, sampled attributes
  ingest.py               script → episodes → parser-emitted beats
  episode_intelligence.py per-episode driver scores, cohort-fit, drop pressure
  signals.py              keyword feature bank shared by heuristics and guardrails
  engine.py               deterministic reaction engine (rule-based)
  llm_engine.py           OpenAI Responses reaction engine (per persona per episode)
  llm_beats.py            LLM beat segmentation and scoring
  llm_personas.py         LLM persona biography enrichment
  llm_judge.py            Second-pass judge layer over LLM reactions
  prompting.py            Shared prompt builders and behavioral calibration payloads
  metrics.py              Per-episode aggregation and verdict
  insights.py             Cohort curves, drop-beat inspector, paywall map, expectation scorecard
  report_agent.py         Deterministic and LLM report-writing agents
  artifacts.py            Writes manifest, personas.jsonl, reactions.jsonl, metrics.json, report.md
  storage.py              SQLite export (runs / personas / reactions / metrics tables)
  env.py                  .env loader + model fallback resolution

sample_stories/           example scripts
runs/<run_id>/            immutable per-run artifacts (see below)
audience-simulator.html   single-file browser demo of the report format
```

Every run writes:

```
runs/<run_id>/
  manifest.json           what ran, against what, model/effort/modes
  cohort_card.json        need-region taxonomy this run used
  personas.jsonl          the audience for this run
  reactions.jsonl         one row per persona per episode
  metrics.json            per-episode aggregates
  verdict.json            recommendation + insights payload
  report.md               human-readable writeup
  run.sqlite              queryable copy of the above
  progress.jsonl          streamed event log
  checkpoint.json         resumable run state
  reactions.partial.jsonl append-as-you-go reactions (crash-safe)
  episode_intelligence.json
  llm_heuristic_bridge.json
```

---

## What's deliberately not in v1

Audio-layer modelling (VO, pacing, sound design) is out of scope — real retention drivers on an audio platform, and the simulator cannot see any of them.
Also deferred: word-of-mouth propagation between listeners; automated backtesting against real drop data; per-market YAMLs (currently India/English only; adding a market is a new cohort seed set, not a code change).

Personas are synthesised from hand-authored archetypes, not fitted from listening logs. When real session data arrives, Layer 2a (cohort seeds) is designed to be replaced by clusters discovered from session-length distributions, time-of-day histograms, inter-episode gaps, genre mix and coin-spend patterns. Layers 3–6 do not change.

---

Everything below the surface — how personas are sampled in full, what each metric measures and why, the LLM-vs-heuristic bridge, verification via suite mode — is in **[DESIGN.md](DESIGN.md)**.

The end-to-end system diagram, the agent-harness breakdown, and the data flow for a single reaction are in **[ARCHITECTURE.md](ARCHITECTURE.md)**.
