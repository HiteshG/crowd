# Audience Simulator Report

Run ID: `kaveri-100-8-enriched`
Cohort: **India/English Pocket-FM Listener Panel**
Population: **100 synthetic listeners**
Episodes: **8**

> Uncalibrated simulator output. Use rankings, drop points, and directional diagnosis until backtested against real retention.

## Verdict

- Recommendation: `major_rewrite`
- Confidence: `medium-low`
- Final retained from start: **30.0%**
- Mean continue rate: **87.4%**
- Mean craving delta: **0.89**
- Mean prediction entropy: **1.84**

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
| 1 | The Spill | 100 | 81.0% | 81.0% | 0.0% | 0.77 | 2.07 | s001_b01 |
| 2 | The Scent of Bleach | 81 | 87.7% | 71.0% | 0.0% | 0.84 | 1.87 | s002_b11 |
| 3 | The Buried Ring | 71 | 100.0% | 71.0% | 5.6% | 1.35 | 2.27 | - |
| 4 | The Weak Link | 71 | 97.2% | 69.0% | 0.0% | 0.87 | 1.96 | s004_b01 |
| 5 | The Muddy Shoes | 69 | 58.0% | 40.0% | 0.0% | 0.80 | 1.73 | s005_b04 |
| 6 | The Cornered Animal | 40 | 100.0% | 40.0% | 2.5% | 0.78 | 1.61 | - |
| 7 | The Interrogation | 40 | 100.0% | 40.0% | 0.0% | 0.85 | 1.47 | - |
| 8 | Washed Clean | 40 | 75.0% | 30.0% | 0.0% | 0.90 | 1.73 | s008_b01 |

## Triage

- Weakest continue point: episode 5 (The Muddy Shoes), 58.0% continue.
- First beat to inspect: `s005_b04`.
- Best paywall candidate in this run: episode 3 (The Buried Ring), 5.6% simulated pay.

## Drop-Off Insights

- Largest drop pressure is episode 5 (58.0% continue).
- Caveat: Current run uses a mixed India/English Pocket-FM-style listener panel. It covers multiple listening settings and story need-regions, but absolute retention levels are still uncalibrated until compared with real episode-level drop data.

### Episode Diagnosis

- Episode 1 (The Spill): 81.0% continue, 81.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Top drop beat `s001_b01`: [SFX: A rhythmic, frantic scrubbing sound. A harsh bristled brush against wet kitchen tiles. Heavy, ragged breathing.]
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
  Signal: positive: threat/cliffhanger language is present.
- Episode 2 (The Scent of Bleach): 87.7% continue, 71.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Top drop beat `s002_b11`: **MALINI** You clean late, Meenakshi. The house smells like bleach. Very strong.
  Signal: family-pressure risk: domestic stakes need clearer catharsis, justice, or status payoff.
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 3 (The Buried Ring): 100.0% continue, 71.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Signal: family-pressure risk: domestic stakes need clearer catharsis, justice, or status payoff.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 4 (The Weak Link): 97.2% continue, 69.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Top drop beat `s004_b01`: [SFX: The ambient noise of the school hallway fades into tense silence.]
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 5 (The Muddy Shoes): 58.0% continue, 40.0% retained from start. The episode is polarizing: some listeners follow the threat, but a large share does not see enough cohort-specific reward.
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
- Episode 8 (Washed Clean): 75.0% continue, 30.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Top drop beat `s008_b01`: [SFX: A car driving down a deserted highway. The hum of the engine. Inside the car, it is quiet.]
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
  Signal: positive: threat/cliffhanger language is present.

### Agent Opinion Themes

**Why Droppers Left**
- 36 agents: Drops because family pressure is not paired with enough payoff.
- 18 agents: Drops because the episode does not create enough payoff, agency, relationship, or cliffhanger pressure.
- 13 agents: Drops because the hook is too soft for a high-churn sampler.
- 2 agents: Drops because family pressure is not paired with enough payoff and the hook is too soft for a high-churn sampler.
- 1 agents: Drops because the hook is too soft for a high-churn sampler and family pressure is not paired with enough payoff.

**Why Continuers Stayed**
- 116 agents: Continues because the urban English/Hinglish setting matches the listening mode and danger and mystery are moving fast enough.
- 69 agents: Continues because the urban English/Hinglish setting matches the listening mode and the lead shows professional agency.
- 67 agents: Continues because the lead shows professional agency and the urban English/Hinglish setting matches the listening mode.
- 48 agents: Continues because career and status momentum are moving and the urban English/Hinglish setting matches the listening mode.
- 36 agents: Continues because family pressure is creating catharsis and danger and mystery are moving fast enough.

**Emotional States**
- 220 agents: engaged
- 151 agents: concerned and waiting for consequences
- 71 agents: emotionally invested
- 70 agents: detached

**Paywall Objections**
- 507 agents: Does not pay because the gate is not sharper than this listener's coin threshold.

**Expected Next Beats**
- 165 agents: The anonymous threat will connect the office plot to the family plot.
- 114 agents: The lead will choose career momentum over family pressure.
- 57 agents: The lead will win respect by solving the next practical problem herself.
- 43 agents: The professional rival will be exposed in a public setting.
- 41 agents: The next clue will reveal who is lying.


### Editorial Actions

- Rewrite episode 5 (The Muddy Shoes) first. It has 58.0% continue among active listeners.
- Inspect `s005_b04`: **MEENAKSHI** We are not running. We are going to your aunt’s house in Mysore. By the time Malini gets her warrant tomorrow morning, we will be out of her jurisdiction, giving my lawyer time to block the search.
- For this mixed panel, add a visible payoff before asking listeners to carry more danger or procedural detail: revenge progress, emotional catharsis, competence, relationship movement, or status change.
- Do not place a paywall until the ending blocks a reveal, public proof, or irreversible status move; current simulated pay pressure is weak.
- For high-stakes decisions, rerun with `--engine llm` on a smaller panel and compare the qualitative reasons against this deterministic pass.

## Prediction Buckets

- Episode 1: threat_bridge: 44, competence_win: 25, career_over_family: 17, status_reveal: 6
- Episode 2: career_over_family: 30, threat_bridge: 26, competence_win: 16, status_reveal: 9
- Episode 3: competence_win: 19, romance_interruption: 18, public_exposure: 13, career_over_family: 11
- Episode 4: competence_win: 29, career_over_family: 24, public_exposure: 11, status_reveal: 3
- Episode 5: threat_bridge: 28, career_over_family: 22, competence_win: 17, public_exposure: 1
- Episode 6: threat_bridge: 19, public_exposure: 13, competence_win: 7, romance_interruption: 1
- Episode 7: threat_bridge: 20, competence_win: 13, career_over_family: 7
- Episode 8: competence_win: 18, threat_bridge: 16, career_over_family: 3, public_exposure: 1
