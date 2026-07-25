# Audience Simulator Report

Run ID: `kaveri-30-8`
Cohort: **India/English Aspirational Escapists**
Population: **30 synthetic listeners**
Episodes: **8**

> Uncalibrated simulator output. Use rankings, drop points, and directional diagnosis until backtested against real retention.

## Verdict

- Recommendation: `major_rewrite`
- Confidence: `medium-low`
- Final retained from start: **0.0%**
- Mean continue rate: **33.6%**
- Mean craving delta: **0.52**
- Mean prediction entropy: **0.66**

## India/English Cohort Model

- Market: India, English/Hinglish, mostly Tier 1 with Tier 2 aspirational spillover
- Drivers: identity, wish_fulfillment, escapism
- Retention hooks: competence win, public professional vindication, status or ownership reveal, romance that supports ambition, office/startup/social-mobility stakes
- Drop triggers: lead becomes passive, ambition collapses into pure romance, family melodrama crowds out the modern setting, regressive gender framing, translated or unnatural English register, filler before the first competence payoff
- Pay triggers: gate before public vindication, gate before status reveal, gate before career/relationship collision

## Episode Metrics

| Ep | Title | Active | Continue | Retained | Pay | Craving Delta | Entropy | Top Drop Beat |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | The Spill | 30 | 56.7% | 56.7% | 0.0% | 0.90 | 2.15 | s001_b01 |
| 2 | The Scent of Bleach | 17 | 11.8% | 6.7% | 0.0% | 0.76 | 2.13 | s002_b11 |
| 3 | The Buried Ring | 2 | 100.0% | 6.7% | 0.0% | 1.00 | -0.00 | - |
| 4 | The Weak Link | 2 | 100.0% | 6.7% | 0.0% | 0.50 | 1.00 | - |
| 5 | The Muddy Shoes | 2 | 0.0% | 0.0% | 0.0% | 1.00 | -0.00 | s005_b04 |
| 6 | The Cornered Animal | 0 | 0.0% | 0.0% | 0.0% | 0.00 | 0.00 | - |
| 7 | The Interrogation | 0 | 0.0% | 0.0% | 0.0% | 0.00 | 0.00 | - |
| 8 | Washed Clean | 0 | 0.0% | 0.0% | 0.0% | 0.00 | 0.00 | - |

## Triage

- Weakest continue point: episode 5 (The Muddy Shoes), 0.0% continue.
- First beat to inspect: `s005_b04`.
- Best paywall candidate in this run: episode 1 (The Spill), 0.0% simulated pay.

## Drop-Off Insights

- Largest drop pressure is episode 2 (11.8% continue).
- Caveat: Current run uses India/English Aspirational Escapists. This cohort is strict about agency, competence, status movement, and urban aspiration. Crime-thriller or maternal-protection stories need a separate cohort before treating absolute drop levels as calibrated.

### Episode Diagnosis

- Episode 1 (The Spill): 56.7% continue, 56.7% retained from start. The episode is polarizing: some listeners follow the threat, but a large share does not see enough cohort-specific reward.
  Top drop beat `s001_b01`: [SFX: A rhythmic, frantic scrubbing sound. A harsh bristled brush against wet kitchen tiles. Heavy, ragged breathing.]
  Signal: low aspirational payoff: few competence, career, or status wins for this cohort.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
  Signal: positive: threat/cliffhanger language is present.
- Episode 2 (The Scent of Bleach): 11.8% continue, 6.7% retained from start. The main drop is cohort-fit related: the story has danger, but not enough aspiration, competence payoff, or status movement for this India/English aspirational panel.
  Top drop beat `s002_b11`: **MALINI** You clean late, Meenakshi. The house smells like bleach. Very strong.
  Signal: family-pressure risk: domestic stakes crowd out aspiration/status movement.
  Signal: low aspirational payoff: few competence, career, or status wins for this cohort.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 3 (The Buried Ring): 100.0% continue, 6.7% retained from start. The remaining listeners treated this as a stable continuation point.
  Signal: family-pressure risk: domestic stakes crowd out aspiration/status movement.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 4 (The Weak Link): 100.0% continue, 6.7% retained from start. The remaining listeners treated this as a stable continuation point.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.
- Episode 5 (The Muddy Shoes): 0.0% continue, 0.0% retained from start. The main drop is cohort-fit related: the story has danger, but not enough aspiration, competence payoff, or status movement for this India/English aspirational panel.
  Top drop beat `s005_b04`: **MEENAKSHI** We are not running. We are going to your aunt’s house in Mysore. By the time Malini gets her warrant tomorrow morning, we will be out of her jurisdiction, giving my lawyer time to block the search.
  Signal: family-pressure risk: domestic stakes crowd out aspiration/status movement.
  Signal: low aspirational payoff: few competence, career, or status wins for this cohort.
  Signal: weak paywall pressure: ending is not a status/reveal gate for this cohort.

### Agent Opinion Themes

**Why Droppers Left**
- 17 agents: Drops because family pressure crowds out the aspiration arc.
- 13 agents: Drops because the episode does not create enough aspiration, agency, or cliffhanger pressure.

**Why Continuers Stayed**
- 17 agents: Continues because the urban English/Hinglish setting matches the listening mode.
- 2 agents: Continues because career and status momentum are moving and the urban English/Hinglish setting matches the listening mode.
- 2 agents: Continues because the lead shows professional agency and the urban English/Hinglish setting matches the listening mode.
- 2 agents: Continues because the urban English/Hinglish setting matches the listening mode and the lead shows professional agency.

**Emotional States**
- 30 agents: detached
- 21 agents: engaged
- 2 agents: curious but watching the ambition arc

**Paywall Objections**
- 53 agents: Does not pay because the gate is not sharper than this listener's coin threshold.

**Expected Next Beats**
- 21 agents: The anonymous threat will connect the office plot to the family plot.
- 14 agents: The lead will choose career momentum over family pressure.
- 5 agents: A relationship confession will be interrupted by a workplace crisis.
- 5 agents: The professional rival will be exposed in a public setting.
- 4 agents: The hidden status or ownership truth will come out at the worst possible moment.


### Editorial Actions

- Rewrite episode 5 (The Muddy Shoes) first. It has 0.0% continue among active listeners.
- Inspect `s005_b04`: **MEENAKSHI** We are not running. We are going to your aunt’s house in Mysore. By the time Malini gets her warrant tomorrow morning, we will be out of her jurisdiction, giving my lawyer time to block the search.
- For this cohort, add a visible competence/status payoff before asking listeners to carry more danger or procedural detail.
- Do not place a paywall until the ending blocks a reveal, public proof, or irreversible status move; current simulated pay pressure is weak.
- Run a second cohort for crime-thriller or maternal-protection listeners before making a final story-level call.

## Prediction Buckets

- Episode 1: threat_bridge: 14, career_over_family: 6, romance_interruption: 4, status_reveal: 2
- Episode 2: career_over_family: 7, threat_bridge: 5, status_reveal: 2, competence_win: 1
- Episode 3: public_exposure: 2
- Episode 4: career_over_family: 1, competence_win: 1
- Episode 5: threat_bridge: 2
- Episode 6: none
- Episode 7: none
- Episode 8: none
