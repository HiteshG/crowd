# Audience Simulator Report

Run ID: `ember-crown-30-8`
Cohort: **India/English Aspirational Escapists**
Population: **30 synthetic listeners**
Episodes: **8**

> Uncalibrated simulator output. Use rankings, drop points, and directional diagnosis until backtested against real retention.

## Verdict

- Recommendation: `major_rewrite`
- Confidence: `medium-low`
- Final retained from start: **0.0%**
- Mean continue rate: **9.2%**
- Mean craving delta: **0.19**
- Mean prediction entropy: **0.54**

## India/English Cohort Model

- Market: India, English/Hinglish, mostly Tier 1 with Tier 2 aspirational spillover
- Drivers: identity, wish_fulfillment, escapism
- Retention hooks: competence win, public professional vindication, status or ownership reveal, romance that supports ambition, office/startup/social-mobility stakes
- Drop triggers: lead becomes passive, ambition collapses into pure romance, family melodrama crowds out the modern setting, regressive gender framing, translated or unnatural English register, filler before the first competence payoff
- Pay triggers: gate before public vindication, gate before status reveal, gate before career/relationship collision

## Episode Metrics

| Ep | Title | Active | Continue | Retained | Pay | Craving Delta | Entropy | Top Drop Beat |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | The Flame in the Lens | 30 | 73.3% | 73.3% | 0.0% | 0.73 | 2.11 | s001_b01 |
| 2 | The Escape | 22 | 0.0% | 0.0% | 0.0% | 0.82 | 2.17 | s002_b01 |
| 3 | The Safehouse | 0 | 0.0% | 0.0% | 0.0% | 0.00 | 0.00 | - |
| 4 | The First Spark | 0 | 0.0% | 0.0% | 0.0% | 0.00 | 0.00 | - |
| 5 | The Toll of Ash | 0 | 0.0% | 0.0% | 0.0% | 0.00 | 0.00 | - |
| 6 | The Temple of Cinders | 0 | 0.0% | 0.0% | 0.0% | 0.00 | 0.00 | - |
| 7 | The Awakening | 0 | 0.0% | 0.0% | 0.0% | 0.00 | 0.00 | - |
| 8 | The Ember Crown | 0 | 0.0% | 0.0% | 0.0% | 0.00 | 0.00 | - |

## Triage

- Weakest continue point: episode 2 (The Escape), 0.0% continue.
- First beat to inspect: `s002_b01`.
- Best paywall candidate in this run: episode 1 (The Flame in the Lens), 0.0% simulated pay.

## Prediction Buckets

- Episode 1: status_reveal: 9, competence_win: 8, career_over_family: 7, threat_bridge: 5
- Episode 2: career_over_family: 8, threat_bridge: 7, romance_interruption: 3, public_exposure: 2
- Episode 3: none
- Episode 4: none
- Episode 5: none
- Episode 6: none
- Episode 7: none
- Episode 8: none
