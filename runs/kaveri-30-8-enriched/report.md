# Audience Simulator Report

Run ID: `kaveri-30-8-enriched`
Cohort: **India/English Pocket-FM Listener Panel**
Population: **30 synthetic listeners**
Episodes: **8**

> Uncalibrated simulator output. Use rankings, drop points, and directional diagnosis until backtested against real retention.

## Verdict

- Recommendation: `major_rewrite`
- Confidence: `medium-low`
- Final retained from start: **26.7%**
- Mean continue rate: **86.6%**
- Mean craving delta: **0.93**
- Mean prediction entropy: **1.66**

## India/English Cohort Model

- Model: Auditable seed mix: listening occasion x story need-region x MBTI voice layer
- Market: India, English/Hinglish, Pocket-FM-style serialized audio fiction
- Drivers: identity, wish_fulfillment, escapism, justice_seeking, comfort, power_fantasy, belonging
- Retention hooks: early emotional injury with a clear revenge or justice promise, competence wins and public vindication, romance pressure with secrets, status gaps, or forced proximity, high-frequency cliffhangers and unanswered identity/status reveals, clear English/Hinglish voice that does not feel translated
- Drop triggers: slow setup without a promise of payoff, too many names, timelines, or lore rules for multitasking listeners, passive protagonist after the hook, paywall after a resolved ending, expensive coin ask before character attachment is strong
- Pay triggers: gate before revenge, confession, rescue, or status reveal, gate after a public humiliation or betrayal, gate when the listener already trusts the story to pay off promises
- MBTI scope: Voice and decision-style only; it does not alter numeric retention fields.

Source basis:

- Pocket FM India 2025 public insights: youth-heavy, long daily listening, multitasking, social discovery, micro-payments.
- Pocket FM app surface: romance, drama, fantasy/sci-fi, horror and thriller are core binge genres.
- Local pocket repo pattern: sample listener occasion separately from story need-region.

Listener settings:

- Metro commuter, cab or metro rail (17%, commute, binge)
- English-medium student, binge between classes (17%, study break, binge)
- WFH or chores multitasker (13%, chores or low-focus work, drip)
- Late-night private binger (14%, late-night unwind, binge)
- Self-employed workday listener (12%, shop, deliveries, or business admin, drip)
- Salaried office break listener (10%, work breaks, drip)
- Evening household listener (7%, cooking, family downtime, or bedtime, drip)
- Workout or evening walk listener (5%, gym, run, or evening walk, binge)
- Lapsed returner testing a new show (3%, trying a recommended comeback series, trial)
- Long-haul traveller with offline downloads (2%, intercity train, bus, or flight, binge)

## Episode Metrics

| Ep | Title | Active | Continue | Retained | Pay | Craving Delta | Entropy | Top Drop Beat |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | The Spill | 30 | 83.3% | 83.3% | 0.0% | 0.93 | 2.22 | s001_b01 |
| 2 | The Scent of Bleach | 25 | 88.0% | 73.3% | 0.0% | 0.96 | 1.91 | s002_b11 |
| 3 | The Buried Ring | 22 | 100.0% | 73.3% | 4.5% | 1.32 | 2.28 | - |
| 4 | The Weak Link | 22 | 100.0% | 73.3% | 0.0% | 0.82 | 1.44 | - |
| 5 | The Muddy Shoes | 22 | 54.5% | 40.0% | 0.0% | 0.95 | 1.49 | s005_b04 |
| 6 | The Cornered Animal | 12 | 100.0% | 40.0% | 0.0% | 0.75 | 0.65 | - |
| 7 | The Interrogation | 12 | 100.0% | 40.0% | 0.0% | 0.83 | 1.55 | - |
| 8 | Washed Clean | 12 | 66.7% | 26.7% | 0.0% | 0.83 | 1.73 | s008_b01 |

## Triage

- Weakest continue point: episode 5 (The Muddy Shoes), 54.5% continue.
- First beat to inspect: `s005_b04`.
- Best paywall candidate in this run: episode 3 (The Buried Ring), 4.5% simulated pay.

## Drop-Off Insights

- Largest drop pressure is episode 5 (54.5% continue).
- Caveat: Current run uses a mixed India/English Pocket-FM-style listener panel. It covers multiple listening settings and story need-regions, but absolute retention levels are still uncalibrated until compared with real episode-level drop data.

### Episode Diagnosis

- Episode 1 (The Spill): 83.3% continue, 83.3% retained from start. The remaining listeners treated this as a stable continuation point.
  Top drop beat `s001_b01`: [SFX: A rhythmic, frantic scrubbing sound. A harsh bristled brush against wet kitchen tiles. Heavy, ragged breathing.]
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
  Signal: positive: threat/cliffhanger language is present.
- Episode 2 (The Scent of Bleach): 88.0% continue, 73.3% retained from start. The remaining listeners treated this as a stable continuation point.
  Top drop beat `s002_b11`: **MALINI** You clean late, Meenakshi. The house smells like bleach. Very strong.
  Signal: family-pressure risk: domestic stakes need clearer catharsis, justice, or status payoff.
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 3 (The Buried Ring): 100.0% continue, 73.3% retained from start. The remaining listeners treated this as a stable continuation point.
  Signal: family-pressure risk: domestic stakes need clearer catharsis, justice, or status payoff.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 4 (The Weak Link): 100.0% continue, 73.3% retained from start. The remaining listeners treated this as a stable continuation point.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 5 (The Muddy Shoes): 54.5% continue, 40.0% retained from start. The episode is polarizing: some listeners follow the threat, but a large share does not see enough cohort-specific reward.
  Top drop beat `s005_b04`: **MEENAKSHI** We are not running. We are going to your aunt’s house in Mysore. By the time Malini gets her warrant tomorrow morning, we will be out of her jurisdiction, giving my lawyer time to block the search.
  Signal: family-pressure risk: domestic stakes need clearer catharsis, justice, or status payoff.
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 6 (The Cornered Animal): 100.0% continue, 40.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
  Signal: positive: public proof/vindication is present.
- Episode 7 (The Interrogation): 100.0% continue, 40.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Signal: family-pressure risk: domestic stakes need clearer catharsis, justice, or status payoff.
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 8 (Washed Clean): 66.7% continue, 26.7% retained from start. The episode is polarizing: some listeners follow the threat, but a large share does not see enough cohort-specific reward.
  Top drop beat `s008_b01`: [SFX: A car driving down a deserted highway. The hum of the engine. Inside the car, it is quiet.]
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
  Signal: positive: threat/cliffhanger language is present.

### Agent Opinion Themes

**Why Droppers Left**
- 11 agents: Drops because family pressure is not paired with enough payoff.
- 5 agents: Drops because the episode does not create enough payoff, agency, relationship, or cliffhanger pressure.
- 4 agents: Drops because the hook is too soft for a high-churn sampler.
- 1 agents: Drops because the hook is too soft for a high-churn sampler and family pressure is not paired with enough payoff.
- 1 agents: Drops because family pressure is not paired with enough payoff and the hook is too soft for a high-churn sampler.

**Why Continuers Stayed**
- 34 agents: Continues because the urban English/Hinglish setting matches the listening mode and danger and mystery are moving fast enough.
- 22 agents: Continues because the lead shows professional agency and the urban English/Hinglish setting matches the listening mode.
- 22 agents: Continues because the urban English/Hinglish setting matches the listening mode and the lead shows professional agency.
- 14 agents: Continues because career and status momentum are moving and the urban English/Hinglish setting matches the listening mode.
- 11 agents: Continues because family pressure is creating catharsis and danger and mystery are moving fast enough.

**Emotional States**
- 67 agents: engaged
- 46 agents: concerned and waiting for consequences
- 22 agents: detached
- 22 agents: emotionally invested

**Paywall Objections**
- 156 agents: Does not pay because the gate is not sharper than this listener's coin threshold.

**Expected Next Beats**
- 48 agents: The anonymous threat will connect the office plot to the family plot.
- 38 agents: The lead will choose career momentum over family pressure.
- 16 agents: The next clue will reveal who is lying.
- 13 agents: A family secret will become the next emotional trap.
- 13 agents: The professional rival will be exposed in a public setting.


### Editorial Actions

- Rewrite episode 5 (The Muddy Shoes) first. It has 54.5% continue among active listeners.
- Inspect `s005_b04`: **MEENAKSHI** We are not running. We are going to your aunt’s house in Mysore. By the time Malini gets her warrant tomorrow morning, we will be out of her jurisdiction, giving my lawyer time to block the search.
- For this mixed panel, add a visible payoff before asking listeners to carry more danger or procedural detail: revenge progress, emotional catharsis, competence, relationship movement, or status change.
- Do not place a paywall until the ending blocks a reveal, public proof, or irreversible status move; current simulated pay pressure is weak.
- For high-stakes decisions, rerun with `--engine llm` on a smaller panel and compare the qualitative reasons against this deterministic pass.

## Prediction Buckets

- Episode 1: career_over_family: 9, threat_bridge: 9, competence_win: 7, romance_interruption: 2
- Episode 2: threat_bridge: 10, competence_win: 6, status_reveal: 5, career_over_family: 4
- Episode 3: romance_interruption: 6, public_exposure: 5, competence_win: 4, career_over_family: 4
- Episode 4: competence_win: 12, career_over_family: 6, public_exposure: 4
- Episode 5: career_over_family: 10, threat_bridge: 8, competence_win: 4
- Episode 6: threat_bridge: 10, competence_win: 2
- Episode 7: threat_bridge: 5, career_over_family: 4, competence_win: 3
- Episode 8: competence_win: 6, threat_bridge: 3, public_exposure: 2, career_over_family: 1
