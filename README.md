# Crowd

**A synthetic audience simulation system for serialized audio fiction.**

Crowd plays a script to a few hundred synthetic listeners, episode by episode, and turns their decisions into a ranked list of which episodes to fix, where to put the paywall, and which cohort the story is actually for.

---

## Why this exists

Every writers' room has the same argument: *"episode 7 is fine, the drop is at 9."*
Nobody can prove it. Analytics tell you where retention fell — never *why*, never *which of the six things you might change would move it*, and never before the episode ships.

Crowd is a focus group you can run on a laptop in an afternoon. It doesn't predict retention percentages. It answers the questions the room actually has:

- **Where should I spend limited rewrite hours?** — the Fix List ranks every episode by money at risk, so a weak episode *before* the paywall is triaged as the emergency it is.
- **Did the rewrite actually work?** — same audience, v1 vs v2, paired delta. Persona bias cancels in the difference.
- **Who is this story for?** — six need-regions ranked, with the specific dealbreaker the script trips for each.
- **Is that cliffhanger actually a cliffhanger?** — prediction disagreement tells you whether listeners genuinely don't know what happens next, or already do and won't hurry back.
- **Which episode looks satisfying but is quietly killing the series?** — craving delta catches the episode that resolves too cleanly, invisible to a satisfaction score.

Reports say *"episode 7 is the weakest in this script; the rewrite recovers X points in paired simulation"* — never *"predicted retention: 34%."* Relative claims survive persona miscalibration. Absolute claims, with no data behind them, would be indefensible.

---

## What you get

| Capability | What it produces |
|---|---|
| **Episode ranking within a script** | Which ones are weakest, relative to the rest |
| **Paired rewrite deltas** | Same audience, v1 vs v2 — did the fix land? |
| **Cross-script ranking** | Script A vs script B against the same panel |
| **Drop-beat localisation** | Where *inside* an episode attention breaks |
| **Cohort divergence** | Which of the six need-regions engages most (directional) |
| **Filler detection** | Beats that move nothing, ordered by the drop rate of the episode they sit in |
| **Paywall placement** | Where the willingness-to-pay curve inflects |

---

## The mental model — it's a focus group

Each command is one step of running one.

| Command | Plain English |
|---|---|
| `ingest` | Prepare the script — split into episodes, tag story beats |
| `personas` | Hire the test audience, saved to a file and reused forever |
| `simulate` | Hold the screening — episode by episode, continue/drop, pay/not |
| `report` | Write it up — fix list, retention curve, paywall map |
| `compare` | Two screenings — did the rewrite work, and by how much? |

---

## Quickstart

Runs offline on the bundled sample with `--provider mock` — no API key, no cost.

```bash
# 1. Prepare the script
pocketsim ingest --script scripts/script1.txt --series script1 \
                 --market india-hindi --provider mock

# 2. Hire the audience (once — reused for every run after this)
pocketsim personas build --market india-hindi --count 25 --seed 42 \
                 --out populations/script1-25.json --provider mock

# 3. Read a few of them — this is the validity gate
pocketsim personas inspect --population populations/script1-25.json -n 3

# 4. Hold the screening
pocketsim simulate --series script1 --population populations/script1-25.json \
                   --run-id script1-smoke --provider mock

# 5. Write it up
pocketsim report --run script1-smoke --format html --open
```

Then the loop that earns its keep — a writer rewrites episode 7:

```bash
pocketsim ingest   --script scripts/script1-v2.txt --series script1-v2 --market india-hindi
pocketsim simulate --series script1-v2 --population populations/script1-25.json \
                   --run-id script1-v2 --provider mock
pocketsim compare  --base script1-smoke --against script1-v2
```

For real runs, drop `--provider mock` (defaults to `openai-api`) and start with `--limit-episodes 3` to smoke-test for about a dollar.

---

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env      # add OPENAI_API_KEY
```

Python 3.11+.

---

## Two things no analytics dashboard can produce

Because real listeners never tell you what they *expected*.

**Craving delta** — `craving_end − craving_mid`. A satisfying, cleanly-resolved episode is a churn event on a serialized platform. Catches the episode that is *too well-resolved*. Needs a different fix from "boring."

**Prediction disagreement** — mean pairwise distance between what listeners think happens next. High craving with *low* disagreement means they already know what's coming and have no reason to hurry back. High craving with *high* disagreement is what a working cliffhanger looks like.

Together with `drop_rate × active_share × episodes_remaining` (the Fix List), these are why the report goes further than a dashboard could.

---

## How the audience is built (the short version)

One rule: **sample the numbers, generate the prose.**

The model never invents a numeric attribute. Every number a persona carries is drawn from a distribution declared in `markets/*.yaml`; the LLM only writes biography around that skeleton. Auditable, reproducible under a seed, and correctable when real data arrives.

Every persona lives on two axes:

- **Occasion cohort** — *when and how do they listen?* (gig-worker marathon, domestic daytime, late-night private binger…) Owns session structure, tempo, payment tier. Determines the *shape* of the retention curve.
- **Need region** — *what do they want a story to do for them?* (Justice-Payoff Bingers, Slow-Burn Comfort Seekers, Tier-1 Aspirational Escapists…) Owns drivers, hooks, dealbreakers. Determines *which stories* retain them.

Neither subsumes the other. A gig worker on an eight-hour shift and a homemaker doing chores can both be Justice-Payoff listeners and drop at the same narrative failure — at different points on the clock. One axis alone predicts the wrong half of the behaviour.

The six need-regions are shared across markets (a region is platform identity). What each market contributes is the *join* — which regions its occasions draw from — so Hindi and English come out with sharply different marginals:

| Region | india-hindi | india-english |
|---|---:|---:|
| Justice-Payoff Bingers | 27% | 17% |
| Status-Progression Loyalists | 20% | 11% |
| Household-Catharsis Devotees | 16% | 7% |
| Slow-Burn Comfort Seekers | 14% | 24% |
| High-Churn Thrill Chasers | 13% | 20% |
| Tier-1 Aspirational Escapists | 10% | 22% |

Full rationale — evidence tiers, anti-stereotype slices, the join model — is in **DESIGN.md**.

---

## The null test — the most important check in the system

```bash
pocketsim simulate --series naagin --population populations/ih-300.json --run-id nt-a
pocketsim simulate --series naagin --population populations/ih-300.json --run-id nt-b
pocketsim compare  --base nt-a --against nt-b
```

Same script, same audience, run twice — so nothing changed. Whatever this reports is the noise floor of your configuration. Any rewrite delta smaller than that number is unproven. `compare` detects this case automatically and labels it.

---

## Providers

|  | `openai-api` (default) | `codex-cli` | `mock` |
|---|---|---|---|
| Schema guarantee | Structured Outputs, `strict: true` | Best-effort + repair retry | Always valid |
| Cost | ~$15–30 per full run | Zero marginal | Zero |
| Speed | Async fan-out | Subprocess pool | Instant |

Production runs go through the API — a 3% schema failure rate across 4,000 calls is a silently biased curve. Persona synthesis and smoke tests go through Codex CLI for free. `mock` is deterministic and offline; the whole pipeline including the null test runs with no key.

---

## Guards, enforced not documented

- Comparing runs with different populations refuses to report a number and exits 2.
- A population built for one market cannot be used to simulate another.
- `personas build` exits 2 if the diversity audit fails.
- Schema failures are counted and reported as a percentage — dropped from the dataset, so the curve is biased by exactly that much.
- `verdict.json` is checked before it is written: any field name that would assert a calibrated real-world prediction (`predicted_*`, `expected_retention`, …) fails the write.
- `runs/<run-id>/report/learning.md` records run setup, persona generation, validation checks, outcomes and automatic harness warnings.

---

## Layout

```
markets/          india-hindi.yaml, india-english.yaml   ← occasion cohorts, per market
  _ontology.yaml  drivers · hook/dealbreaker banks · 6 need regions   ← shared, imported
scripts/          raw .txt scripts
series/<name>/    episodes.json + beats.json             ← ingest output, reused across runs
populations/      generated audiences, versioned by seed
runs/<run_id>/
  manifest.json   what ran, against what, which population fingerprint
  input/          provenance copies
  reactions.jsonl written during the run — a crash at ep 17 of 20 leaves 17 usable
  report/         verdict.json · report.md · report.html
  logs/run.log
src/pocketsim/    cli · config · ingest · personas · llm · schema · simulate · metrics · report · store
```

Simulating is slow and costs money; reporting is instant and free — so you simulate once and re-report as metrics get added. The population file is reused across runs on purpose: `compare` only works if both runs used the same listeners, so persona bias cancels in the difference and you know the *script* moved, not the audience.

---

## What's deliberately not in v1

Audio-layer modelling (VO, pacing, sound design) is out of scope — real retention drivers on an audio platform, and the simulation cannot see any of them. Also deferred: word-of-mouth propagation between listeners; a deep-dive tier explaining *why* an episode loses people in writer-actionable prose rather than just locating it; US and Tamil/Telugu markets (both are a new YAML file, no code change).

Personas today are synthesised from hand-authored archetypes, not fitted from listening logs, and no backtest has been run. Layer 2a is designed to be replaced by clusters discovered from session-length distributions, time-of-day histograms, inter-episode gaps, genre mix and coin-spend patterns when that data arrives. Layers 3–6 do not change.

---

Everything below the surface — how personas are synthesised in full, what gets measured and why, provider tradeoffs, markets, verification, and the parts of the source ontology deliberately not merged yet — is in **DESIGN.md**.
