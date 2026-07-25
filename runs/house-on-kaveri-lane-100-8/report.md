# Audience Simulator Report

Run ID: `house-on-kaveri-lane-100-8`
Cohort: **India/English Pocket-FM Listener Panel**
Population: **100 synthetic listeners**
Episodes: **8**

> Uncalibrated simulator output. Use rankings, drop points, and directional diagnosis until backtested against real retention.

## Verdict

- Recommendation: `major_rewrite`
- Confidence: `medium-low`
- Final retained from start: **29.0%**
- Mean continue rate: **86.8%**
- Mean craving delta: **0.89**
- Mean prediction entropy: **1.97**

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
| 1 | The Spill | 100 | 76.0% | 76.0% | 0.0% | 0.91 | 1.96 | s001_b01 |
| 2 | The Scent of Bleach | 76 | 89.5% | 68.0% | 0.0% | 0.84 | 2.09 | s002_b11 |
| 3 | The Buried Ring | 68 | 98.5% | 67.0% | 5.9% | 1.19 | 2.24 | s003_b05 |
| 4 | The Weak Link | 67 | 98.5% | 66.0% | 0.0% | 0.87 | 2.10 | s004_b01 |
| 5 | The Muddy Shoes | 66 | 63.6% | 42.0% | 0.0% | 0.80 | 1.64 | s005_b04 |
| 6 | The Cornered Animal | 42 | 100.0% | 42.0% | 0.0% | 0.74 | 1.81 | - |
| 7 | The Interrogation | 42 | 97.6% | 41.0% | 0.0% | 0.83 | 1.70 | s007_b08 |
| 8 | Washed Clean | 41 | 70.7% | 29.0% | 0.0% | 0.93 | 2.21 | s008_b01 |

## Triage

- Weakest continue point: episode 5 (The Muddy Shoes), 63.6% continue.
- First beat to inspect: `s005_b04`.
- Best paywall candidate in this run: episode 3 (The Buried Ring), 5.9% simulated pay.

## Drop-Off Insights

- Largest drop pressure is episode 5 (63.6% continue).
- Caveat: Current run uses a mixed India/English Pocket-FM-style listener panel. It covers multiple listening settings and story need-regions, but absolute retention levels are still uncalibrated until compared with real episode-level drop data.

### Retention Shape

- Episode 5 (The Muddy Shoes): lost 24 listeners (24.0% of start) in mid-season endurance; 63.6% continued.
- Episode 1 (The Spill): lost 24 listeners (24.0% of start) in opening hook; 76.0% continued.
- Episode 8 (Washed Clean): lost 12 listeners (12.0% of start) in endgame; 70.7% continued.
- Episode 2 (The Scent of Bleach): lost 8 listeners (8.0% of start) in premise validation; 89.5% continued.

- Final survivors: 29. The final panel is no longer the same audience mix as episode 1.
- Over-represented by finale: Slow-burn comfort seeker (81.0% retained), Household catharsis devotee (77.8% retained), Justice-payoff binger (23.5% retained).
- Under-represented by finale: Aspirational escapist (0.0% retained), High-churn thrill chaser (0.0% retained), Status-progression loyalist (6.7% retained).

### Episode Diagnosis

- Episode 1 (The Spill): 76.0% continue, 76.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Top drop beat `s001_b01`: [SFX: A rhythmic, frantic scrubbing sound. A harsh bristled brush against wet kitchen tiles. Heavy, ragged breathing.]
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
  Signal: positive: threat/cliffhanger language is present.
- Episode 2 (The Scent of Bleach): 89.5% continue, 68.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Top drop beat `s002_b11`: **MALINI** You clean late, Meenakshi. The house smells like bleach. Very strong.
  Signal: family-pressure risk: domestic stakes need clearer catharsis, justice, or status payoff.
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 3 (The Buried Ring): 98.5% continue, 67.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Top drop beat `s003_b05`: **MEENAKSHI** It’s his mother. I have to destroy it. If they track the GPS to our house...
  Signal: family-pressure risk: domestic stakes need clearer catharsis, justice, or status payoff.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 4 (The Weak Link): 98.5% continue, 66.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Top drop beat `s004_b01`: [SFX: The ambient noise of the school hallway fades into tense silence.]
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 5 (The Muddy Shoes): 63.6% continue, 42.0% retained from start. The episode is polarizing: some listeners follow the threat, but a large share does not see enough cohort-specific reward.
  Top drop beat `s005_b04`: **MEENAKSHI** We are not running. We are going to your aunt’s house in Mysore. By the time Malini gets her warrant tomorrow morning, we will be out of her jurisdiction, giving my lawyer time to block the search.
  Signal: family-pressure risk: domestic stakes need clearer catharsis, justice, or status payoff.
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 6 (The Cornered Animal): 100.0% continue, 42.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
  Signal: positive: public proof/vindication is present.
- Episode 7 (The Interrogation): 97.6% continue, 41.0% retained from start. The remaining listeners treated this as a stable continuation point.
  Top drop beat `s007_b08`: **MEENAKSHI** A mother's job is to protect her child. Wouldn't you agree, Malini? Or did you forget how you covered up your own son's drunk driving accident three years ago?
  Signal: family-pressure risk: domestic stakes need clearer catharsis, justice, or status payoff.
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 8 (Washed Clean): 70.7% continue, 29.0% retained from start. The episode is polarizing: some listeners follow the threat, but a large share does not see enough cohort-specific reward.
  Top drop beat `s008_b01`: [SFX: A car driving down a deserted highway. The hum of the engine. Inside the car, it is quiet.]
  Signal: low external payoff: few competence, career, revenge, or status wins for the mixed panel.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
  Signal: positive: threat/cliffhanger language is present.

### Segment Sensitivity

- Episode 1 (The Spill), spend_tier `free`: 14/39 dropped (35.9%).
- Episode 1 (The Spill), interruption `high`: 14/42 dropped (33.3%).
- Episode 5 (The Muddy Shoes), interruption `medium`: 13/31 dropped (41.9%).
- Episode 5 (The Muddy Shoes), need_region `Aspirational escapist`: 12/12 dropped (100.0%).
- Episode 5 (The Muddy Shoes), discovery `social_short_clip`: 12/28 dropped (42.9%).
- Episode 1 (The Spill), need_region `High-churn thrill chaser`: 11/16 dropped (68.8%).
- Episode 8 (Washed Clean), need_region `Justice-payoff binger`: 7/11 dropped (63.6%).
- Episode 1 (The Spill), listening_setting `English-medium student, binge between classes`: 7/17 dropped (41.2%).

### Paywall Diagnostics

- Episode 3 (The Buried Ring): 5.9% paid, average pressure-threshold gap 0.27, 5 close calls. Close-call tiers: regular: 3, heavy: 2.
- Episode 6 (The Cornered Animal): 0.0% paid, average pressure-threshold gap 0.36, 1 close calls. Close-call tiers: heavy: 1.
- Episode 4 (The Weak Link): 0.0% paid, average pressure-threshold gap 0.41, 3 close calls. Close-call tiers: heavy: 3.
- Episode 5 (The Muddy Shoes): 0.0% paid, average pressure-threshold gap 0.43, 0 close calls.

### Agent Opinion Themes

**Why Droppers Left**
- 28 agents: Drops because family pressure is not paired with enough payoff.
- 26 agents: Drops because the episode does not create enough payoff, agency, relationship, or cliffhanger pressure.
- 11 agents: Drops because the hook is too soft for a high-churn sampler.
- 3 agents: Drops because family pressure is not paired with enough payoff and the hook is too soft for a high-churn sampler.
- 2 agents: Drops because the hook is too soft for a high-churn sampler and family pressure is not paired with enough payoff.

**Why Continuers Stayed**
- 113 agents: Continues because the urban English/Hinglish setting matches the listening mode and danger and mystery are moving fast enough.
- 66 agents: Continues because the urban English/Hinglish setting matches the listening mode and the lead shows professional agency.
- 63 agents: Continues because the lead shows professional agency and the urban English/Hinglish setting matches the listening mode.
- 45 agents: Continues because career and status momentum are moving and the urban English/Hinglish setting matches the listening mode.
- 35 agents: Continues because family pressure is creating catharsis and danger and mystery are moving fast enough.

**Emotional States**
- 213 agents: engaged
- 151 agents: concerned and waiting for consequences
- 71 agents: detached
- 67 agents: emotionally invested

**Paywall Objections**
- 498 agents: Does not pay because the gate is not sharper than this listener's coin threshold.

**Expected Next Beats**
- 165 agents: The anonymous threat will connect the office plot to the family plot.
- 95 agents: The lead will choose career momentum over family pressure.
- 63 agents: The next clue will reveal who is lying.
- 45 agents: The lead will win respect by solving the next practical problem herself.
- 37 agents: The professional rival will be exposed in a public setting.


### Editorial Actions

- Rewrite episode 5 (The Muddy Shoes) first. It has 63.6% continue among active listeners.
- Inspect `s005_b04`: **MEENAKSHI** We are not running. We are going to your aunt’s house in Mysore. By the time Malini gets her warrant tomorrow morning, we will be out of her jurisdiction, giving my lawyer time to block the search.
- For this mixed panel, add a visible payoff before asking listeners to carry more danger or procedural detail: revenge progress, emotional catharsis, competence, relationship movement, or status change.
- Do not place a paywall until the ending blocks a reveal, public proof, or irreversible status move; current simulated pay pressure is weak.
- For high-stakes decisions, rerun with `--engine llm` on a smaller panel and compare the qualitative reasons against this deterministic pass.

### Missing Nuance / Model Gaps

- The deterministic engine is fast, but its story understanding is keyword/signal based; it can under-read motifs like guilt, moral inversion, voice performance, and cultural texture unless they map to known signals.
- Current reports summarize agent reasons as repeated buckets; an LLM run can produce richer per-persona explanations, but costs more time and API calls.
- The run is not calibrated against real Pocket-FM episode retention, ad source, coin conversion, or completion logs, so absolute percentages should be treated as directional.
- The simulator does not yet test alternate edits, paywall placement variants, episode thumbnails/hooks, or narration quality, all of which can change actual release performance.

## Prediction Buckets

- Episode 1: threat_bridge: 43, competence_win: 34, career_over_family: 9, status_reveal: 8
- Episode 2: threat_bridge: 32, competence_win: 17, career_over_family: 15, status_reveal: 8
- Episode 3: competence_win: 20, career_over_family: 16, romance_interruption: 15, public_exposure: 10
- Episode 4: competence_win: 28, career_over_family: 19, public_exposure: 10, status_reveal: 4
- Episode 5: threat_bridge: 28, career_over_family: 21, competence_win: 16, romance_interruption: 1
- Episode 6: threat_bridge: 20, competence_win: 11, public_exposure: 8, career_over_family: 2
- Episode 7: threat_bridge: 15, competence_win: 15, career_over_family: 11, public_exposure: 1
- Episode 8: threat_bridge: 17, competence_win: 10, romance_interruption: 5, public_exposure: 4
