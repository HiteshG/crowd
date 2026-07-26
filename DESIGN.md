# DESIGN — Audience Simulator

The **why** behind every choice: what each layer models, why it exists, and what would break if you removed it.

Read **README.md** first for the product framing and CLI. Read **ARCHITECTURE.md** for the system diagram and data flow. This document justifies the shapes those two describe.

---

## 1. Design principles

The whole system falls out of five commitments. Every trade-off elsewhere is a consequence.

### 1.1 Sample the numbers, generate the prose

The LLM never invents a numeric attribute. Every number a persona carries — `driver_intensity`, `session_minutes`, `city_tier`, `coin_spend_tier`, `historical_completion`, `pay_threshold` — is drawn from a distribution declared in `audience_simulator/cohorts.py` under a deterministic seed. LLM enrichment (`--persona-mode llm`) only writes biography around that skeleton.

**Why:** if the model is allowed to pick its own numbers, the audience shape drifts every run. Sampling makes the panel auditable (`audience-sim population --summary` prints the marginals), reproducible under a seed, and correctable when real data lands.

### 1.2 Relative claims, not absolute predictions

The report never says *"predicted retention: 34%."* It says *"episode 7 is the weakest in this script; the rewrite recovers X points against the same seeded audience."*

**Why:** the simulator is uncalibrated. A calibrated retention percentage requires a backtest against real drop data, which does not yet exist. Relative rankings and paired deltas survive persona miscalibration — if the audience is uniformly 15% too generous, both v1 and v2 shift by 15% and the delta is preserved. `verdict.json` explicitly carries a `calibration_warning` field for this reason.

### 1.3 Same audience, different scripts

The population file is generated once from `(personas, seed)` and re-used across scripts and rewrites. `compare` (via `--repeats` suite mode) only works if both runs used the same listeners.

**Why:** if the audience changes between runs, you cannot tell whether the *script* moved or the *panel* moved. Persona bias cancels in a paired difference; it does not cancel in an unpaired difference.

### 1.4 Every layer independently switchable between deterministic and LLM

Beats, personas, reactions, judge, report — each has an `--*-mode` flag. Any one can be `heuristic`/`seed`/`deterministic` while the others are LLM.

**Why:** cost and debuggability. During development you want to iterate on the report writer with fixed reactions; during real runs you want the whole stack LLM but reproducible; during smoke tests you want zero API cost. Independent switching means the same code path serves all three.

### 1.5 Crash-safe by construction

`reactions.partial.jsonl` is appended after each episode; `checkpoint.json` is rewritten after each episode; `progress.jsonl` streams events as they happen. A crash at episode 17 of 20 leaves 17 usable episodes and a resumable state.

**Why:** the LLM path is slow (minutes per episode) and involves network I/O. Losing a 40-minute run to a transient 502 is unacceptable.

---

## 2. The audience model

The heart of the system. Two orthogonal axes, sampled independently, joined at simulation time.

### 2.1 Layer 2a — Listening cohort (the *when* and *how*)

Defined in `cohorts.py` as `LISTENER_SEEDS`. Each seed carries:

- Age distribution (bounded Gaussian: mean, stdev, min, max)
- Session pattern (`marathon`, `pocket`, `late-night`, `daytime-chore`, …)
- Session-minute distribution
- Coin-spend tier weights
- City-tier weights
- Genre affinities
- Discovery channel

**Why sampled:** these are the axes real listener data eventually clusters on. Once session logs exist, this layer becomes fit-from-data rather than hand-authored; the interface stays identical, so layers 3–6 don't move.

### 2.2 Layer 2b — Need region (the *what for*)

Six shared regions, defined in `cohorts.NEED_REGIONS`:

| Region | Ships to |
|---|---|
| `justice_payoff_bingers` | Public vindication, humiliation-then-reversal, cliffhanger endings |
| `status_progression_loyalists` | Competence, ambition, status escalation |
| `household_catharsis_devotees` | Family drama, comfort, slow burn |
| `slow_burn_comfort_seekers` | Romance, family, low-stakes escalation |
| `high_churn_thrill_chasers` | Cliffhangers, thriller, revenge |
| `tier1_aspirational_escapists` | Urban modern, romance, aspirational status |

Each region owns:
- Primary drivers (weighted intensity vector: identity, wish_fulfillment, escapism, justice_seeking, comfort)
- Hooks and dealbreakers
- Cohort-fit priors used by the guardrail layer

**Why separate from the cohort:** a gig worker on an 8-hour shift and a homemaker doing chores can both be Justice-Payoff listeners and drop at the same narrative failure — at different points on the clock. One axis alone predicts the wrong half of the behavior.

### 2.3 The join

At population time (`generate_india_english_population`), each persona samples a listening cohort *and* a need region independently under the seeded RNG. The join weights determine the marginals — Justice-Payoff is 27% of india-hindi vs 17% of india-english because the cohort mix over there draws differently.

**Why independent then joined:** treating them as a single flat taxonomy (e.g. "gig-worker justice-seeker" as an atomic category) explodes the taxonomy and hides which axis owns which behavior. Keeping them separate lets us swap Layer 2a for real cluster data later without touching Layer 2b.

### 2.4 Anti-stereotype slice

Every persona carries an `anti_stereotype` field — a sampled trait that breaks the caricature the cohort × region combination would otherwise imply. A gig worker Justice-Payoff Binger might carry "prefers slow character work over shouted confrontations."

**Why:** without it, the LLM biography step collapses each combination into one archetype, and the reaction engine gets a monoculture that always drops on the same beat.

---

## 3. The reaction model

For each active persona × each episode, produce one `Reaction` record.

### 3.1 Deterministic engine (`engine.py`)

Rule-based. Inputs:
- Persona driver intensities × episode signals (`signals.py` extracts a fixed keyword feature bank per episode).
- Cohort/region priors on driver preference.
- Persona state (`payoff_trust`, `agency_trust`, unresolved questions).

Outputs a fit score → will_continue, would_pay, drop_beat, craving_mid, craving_end, next_prediction.

**Why keep it after the LLM exists:** it's the calibration floor. Any suite that flips verdict across seeds under LLM but stays stable under heuristic tells you the LLM is chasing noise, not signal.

### 3.2 LLM engine (`llm_engine.py`)

One OpenAI Responses call per persona per episode. The prompt (`prompting.build_llm_reaction_payload`) contains:
- Compact persona card (drivers, region hooks/dealbreakers, listening context)
- Persona state at start of episode
- Episode text
- Episode Intelligence for this episode (cohort-fit ranking, driver scores, ending analysis, beat table with decision-risk hints)
- Behavioral calibration payload (numeric anchors — pay pressure baseline, craving scale)

The output is constrained by `REACTION_SCHEMA` (`models.py`) with `strict: true` — either the model returns the exact JSON shape or the call fails and is retried against fallback models.

**Why Responses API with strict schema:** a 3% schema failure rate across 4,000 calls is a silently biased curve. Structured Outputs guarantees every accepted row is well-formed and every failure is counted.

### 3.3 The judge layer (`llm_judge.py`)

Optional second-pass LLM (`--judgement-mode llm`). Takes the raw reaction plus the persona, state, episode, and Episode Intelligence, and can rewrite the decision or its reasoning. Records `changed_decision` / `changed_reasoning` in the reaction row and `judgement_bridge` (a short narrative of *why* it changed).

**Why a separate call:** giving the reaction model access to Episode Intelligence in one shot conflates two skills — being a persona and being a critic. Split, the reaction model commits to a first-person read, then the judge audits it against structural pressure. Suite reports track `judgement_changed` rate as a signal of how often the two disagree.

### 3.4 Guardrail (`episode_intelligence.persona_drop_guardrail`)

Independent of the LLM reaction. Computes a per-persona *drop pressure* from Episode Intelligence: cohort-fit for this region on this episode + accumulated dealbreaker pressure + ending mismatch.

Three modes:
- `advisory` — pressure is recorded in `signal_json` but does not change the decision.
- `override` — if the LLM said continue but pressure is above threshold, flip to drop and record why.
- `off` — do nothing.

**Why not just always let the LLM decide:** LLMs are systematically optimistic about serialized fiction. The guardrail is the correction, and its threshold is auditable — every override records the pressure value, threshold, and reason, so you can inspect and calibrate.

---

## 4. Episode Intelligence

Built once per episode before simulation begins (`episode_intelligence.build_episode_intelligence`). Not a metric — a structural read of the script that the reaction engine, guardrail, judge, and report all consume.

Per episode:

- **Narrative anatomy** — core conflict, protagonist agency (drives/reacts), status quo delta, cognitive load (new entity count).
- **Driver scores** — how strongly this episode ships to each of the five drivers.
- **Beat table** — one row per beat with purpose, decision risk, emotional intensity, suspense.
- **Ending analysis** — cliffhanger strength, status reveal, romance pressure, resolved-no-hook flag.
- **Cohort fit rankings** — which of the six need regions this episode serves best.
- **Promise ledger** — running list of unresolved promises across episodes (an ending that opens three threads without closing any raises churn risk on episode +2).

**Why compute this separately from the reaction:** it forces the structural read to be persona-independent. If cohort fit for `slow_burn_comfort_seekers` was low on episode 7 across every persona in that region, you know it was the *episode*, not any given listener.

---

## 5. Metrics — what's measured and why

Aggregated in `metrics.py` from `reactions.jsonl`.

| Metric | Formula | What it catches |
|---|---|---|
| `continue_rate` | continues / active_before | Per-episode strength given who survived to hear it |
| `retention_from_start` | continues / population_size | Cumulative funnel — the number the platform cares about |
| `pay_rate` | would_pay / active_before | Willingness at this beat — paywall placement signal |
| `avg_craving_delta` | mean(craving_end − craving_mid) | Serialized-fiction anti-metric: too-satisfying is churn |
| `prediction_entropy` | Shannon entropy over bucketed `next_prediction` | Cliffhanger *quality* proxy — do listeners disagree on what comes next? |
| `top_drop_beat` | mode of `drop_beat` among droppers | Where inside the episode attention actually breaks |
| `top_prediction_buckets` | Counter over bucketed predictions | What listeners expect — surfaces expectation traps |

### 5.1 Craving delta — the anti-metric

`avg_craving_delta = mean(craving_end − craving_mid)`.

A positive delta means the episode's ending tightened craving above its middle — good for a serialized property. A *negative* delta on a well-liked episode ("satisfying, self-contained, resolved") is a churn event. It looks like a win on satisfaction but bleeds series retention.

**Why not use satisfaction:** satisfaction rewards clean resolution. On a chapter-and-verse serialized platform, clean resolution is a bug.

### 5.2 Prediction entropy — the cliffhanger check

`next_prediction` strings are bucketed by `metrics.prediction_bucket` into narrative frames (`truth_or_proof`, `coverup_pressure`, `romance_interruption`, …). Shannon entropy over those buckets tells you whether listeners agree or disagree on what happens next.

- High craving + low entropy → they already know what's coming. Not a cliffhanger; a trailer.
- High craving + high entropy → they can't guess. That's a working cliffhanger.

**Why not just trust `craving_end`:** the craving score cannot tell the difference between suspense and impatience-to-resolve. Entropy discriminates.

### 5.3 The Fix List

Implicit in `verdict.build_verdict` — the weakest episode by `continue_rate`, tie-broken by drop_count and episodes_remaining. The prioritization is: *a weak episode before the paywall is triaged as an emergency; a weak episode after the paywall is a rewrite candidate*.

---

## 6. Reports — deterministic and LLM

Two report agents, one interface (`report_agent.build_report_agent`).

### 6.1 Deterministic writer

Templated markdown from `verdict.json` + `insights.build_insights`. Sections: verdict, retention shape, weakest episode, paywall candidate, episode table, drop-beat inspector, cohort curves, expectation scorecard.

**Why keep it as the default:** it is auditable. Every number in the report traces back to a metric row. The LLM writer is one call away from making up a decimal place.

### 6.2 LLM writer

Single OpenAI call with a compact digest of the verdict + insights, constrained to a `{"markdown": string}` schema. Used when the writing needs to *interpret* the numbers into narrative — "the paywall works only if episode 6 recovers agency because…"

**Why not fully replace deterministic:** if the LLM writer hallucinates a metric, deterministic mode is the source of truth to check against.

---

## 7. Verification — the null test and suite mode

### 7.1 Suite mode (`--repeats N`)

Runs the whole loop N times with seeds `seed..seed+N-1`. Writes:
- Recommendation counts across seeds (`{"greenlight": 3, "revise": 2}` means unstable).
- Per-episode mean/min/max continue rate (the noise floor).
- `judgement_changed` rate (how often the judge disagreed with the reaction model).

**Interpretation:** any rewrite delta smaller than the min→max continue-rate spread for that episode is unproven.

### 7.2 The null test (same script, different seeds)

Suite mode against a single script *is* the null test. If the same script produces different verdicts across seeds, the noise floor is louder than the signal — that's what the run has to tell you before any claim about a rewrite is defensible.

**Why bake it in:** without an enforced noise-floor pass, any two-seed A/B is untrustworthy. Suite mode makes the noise floor a first-class artifact.

---

## 8. Providers and cost

| Path | Configuration | Cost | Speed |
|---|---|---|---|
| All heuristic | default | Zero | Seconds |
| LLM beats only | `--episode-intel llm` | ~$0.10 per script | Under a minute |
| Full LLM harness | `--engine llm --persona-mode llm --report-mode llm --episode-intel llm --judgement-mode llm` | ~$5–15 per 30-persona, 8-episode script at `medium` effort | 10–20 minutes |

The engine picks concurrency via `--max-workers` (default 8, env `AUDIENCE_SIM_MAX_WORKERS`). Per-episode reactions fan out across a `ThreadPoolExecutor`; between episodes they are strictly sequential because episode N+1's state depends on episode N's reactions.

Model resolution is `env.openai_model_candidates` — primary from `--model` or `OPENAI_MODEL`, then any comma-separated `OPENAI_MODEL_FALLBACKS`. Each candidate is tried on availability errors; unrelated errors bubble immediately. This is what makes it survive a model deprecation without a code change.

---

## 9. What's deliberately not v1

- **Audio-layer modelling** (VO, pacing, sound design). Real retention drivers on an audio platform, but the simulator cannot see any of them.
- **Word-of-mouth propagation** between listeners. Every persona reacts independently.
- **Fitted personas.** Layer 2a is hand-authored archetypes. When session logs arrive, this becomes cluster-fit; the interface above it does not change.
- **Per-market YAMLs.** Currently only India/English seeds; adding a market is a new cohort seed set in `cohorts.py`, not a code change.
- **Automated backtest.** No paired real/simulated drop-rate curve yet. Until then, the calibration warning stays on every verdict.
- **A deep-dive tier** explaining *why* an episode loses people in writer-actionable prose — currently the report locates it; the diagnosis is left to the room.

---

## 10. The one-line justification for every guardrail

- **Beat-ID validation** — hallucinated drop beats would poison the drop-beat inspector.
- **JSON schema strict mode** — silent schema drift biases the retention curve.
- **Sampled numbers, generated prose** — LLM-picked numerics are unauditable and irreproducible.
- **Same-population re-use** — persona bias only cancels in a paired difference.
- **Guardrail with logged pressure** — LLMs are optimistic on serialized fiction and the override needs to be defensible.
- **Suite-mode noise floor** — a rewrite delta smaller than the noise is not a rewrite delta.
- **Uncalibrated warning on `verdict.json`** — the moment the report claims a real-world number, the tool becomes fiction.
