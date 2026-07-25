# Audience Simulator

Runnable local harness for simulating Indian English/Hinglish serialized audio-fiction listeners.

The code follows the useful workflow pattern from MiroFish-style tools: seed story in, generated agents, simulation artifacts, machine-readable verdict, human-readable report. It is not a social-media simulator and does not include MiroFish code.

## Run 50 Personas On An 8-Episode Story

```bash
python3 -m audience_simulator run sample_stories/house_on_kaveri_lane.md --personas 50 --expect-episodes 8
```

The default engine is deterministic and dependency-free:

```bash
python3 -m audience_simulator run sample_stories/house_on_kaveri_lane.md --personas 100 --expect-episodes 8
```

To use AI reactions instead of the local heuristic engine:

```bash
OPENAI_API_KEY=... python3 -m audience_simulator run sample_stories/house_on_kaveri_lane.md --personas 30 --expect-episodes 8 --engine llm --model gpt-5-mini
```

Artifacts are written under `runs/<run_id>/`:

- `verdict.json` - machine-readable decision summary
- `report.md` - readable report
- `metrics.json` - per-episode metrics
- `personas.jsonl` - generated listener panel
- `reactions.jsonl` - one row per active persona per episode
- `run.sqlite` - queryable store
- `cohort_card.json` - India/English cohort definition
- `manifest.json` - run metadata

## Story Format

Use markdown headings:

```markdown
# Episode 1: Hook

Episode text...

# Episode 2: Payoff

Episode text...
```

The parser turns paragraphs into beat IDs like `s003_b02`; `drop_beat` points to those IDs.

## CLI

```bash
python3 -m audience_simulator run PATH_TO_STORY.md --personas 50 --expect-episodes 8
python3 -m audience_simulator population --personas 50
python3 -m audience_simulator population --personas 100 --summary
python3 -m audience_simulator prompt PATH_TO_STORY.md --episode 1 --persona-index 0
```

The `prompt` command emits the payload shape used by the schema-constrained LLM call.

## India/English Listener Model

The built-in cohort is `India/English Pocket-FM Listener Panel`.

It is intentionally auditable: a persona is built from one listening setting, one story need-region, and one MBTI type. MBTI affects only the simulated voice/decision style; it does not modify the numeric retention fields.

Listening settings:

- metro commuter
- English-medium student binger
- WFH or chores multitasker
- late-night private binger
- self-employed workday listener
- salaried office break listener
- evening household listener
- workout or evening walk listener
- lapsed returner
- long-haul offline traveller

Story need-regions:

- justice-payoff binger
- status-progression loyalist
- household catharsis devotee
- slow-burn comfort seeker
- aspirational escapist
- high-churn thrill chaser

Persona rows include `bio`, one-line `persona`, `mbti`, `cohort_id`, `region_id`, interests, profession, city tier, listening context, session length, daily minutes, spend tier, discovery channel, completion history, churn sensitivity, pay threshold, language register, and genre affinities.

Seed assumptions are inspired by Pocket FM public audience signals: young listeners, Tier-2 plus metro distribution, long daily listening, multitasking contexts, social discovery, micropayments, and core binge genres like drama, romance, thriller, horror, fantasy and sci-fi. They are also informed by the local `pocket` repo pattern of separating listening occasion from story need-region.

Metrics are uncalibrated. Use them as relative diagnosis until a backtest against real retention exists.
