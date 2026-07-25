# Audience Simulator Report

Run ID: `smoke-50-8`
Cohort: **India/English Aspirational Escapists**
Population: **50 synthetic listeners**
Episodes: **8**

> Uncalibrated simulator output. Use rankings, drop points, and directional diagnosis until backtested against real retention.

## Verdict

- Recommendation: `greenlight_for_pilot`
- Confidence: `medium`
- Final retained from start: **82.0%**
- Mean continue rate: **97.8%**
- Mean craving delta: **1.12**
- Mean prediction entropy: **2.24**

## India/English Cohort Model

- Market: India, English/Hinglish, mostly Tier 1 with Tier 2 aspirational spillover
- Drivers: identity, wish_fulfillment, escapism
- Retention hooks: competence win, public professional vindication, status or ownership reveal, romance that supports ambition, office/startup/social-mobility stakes
- Drop triggers: lead becomes passive, ambition collapses into pure romance, family melodrama crowds out the modern setting, regressive gender framing, translated or unnatural English register, filler before the first competence payoff
- Pay triggers: gate before public vindication, gate before status reveal, gate before career/relationship collision

## Episode Metrics

| Ep | Title | Active | Continue | Retained | Pay | Craving Delta | Entropy | Top Drop Beat |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | The Pitch | 50 | 100.0% | 100.0% | 50.0% | 0.54 | 2.31 | - |
| 2 | Public Proof | 50 | 100.0% | 100.0% | 68.0% | 1.20 | 2.53 | - |
| 3 | The Family Ultimatum | 50 | 100.0% | 100.0% | 80.0% | 1.92 | 2.03 | - |
| 4 | Board Vote | 50 | 100.0% | 100.0% | 80.0% | 0.92 | 2.46 | - |
| 5 | The Viral Clip | 50 | 100.0% | 100.0% | 86.0% | 1.52 | 1.89 | - |
| 6 | Police At Reception | 50 | 100.0% | 100.0% | 80.0% | 2.16 | 2.55 | - |
| 7 | The Engagement Contract | 50 | 82.0% | 82.0% | 10.0% | 0.60 | 1.87 | s007_b02 |
| 8 | Mother's Testimony | 41 | 100.0% | 82.0% | 95.1% | 0.12 | 2.24 | - |

## Triage

- Weakest continue point: episode 7 (The Engagement Contract), 82.0% continue.
- First beat to inspect: `s007_b02`.
- Best paywall candidate in this run: episode 8 (Mother's Testimony), 95.1% simulated pay.

## Prediction Buckets

- Episode 1: public_exposure: 17, career_over_family: 10, threat_bridge: 10, competence_win: 8
- Episode 2: public_exposure: 13, status_reveal: 10, romance_interruption: 7, career_over_family: 7
- Episode 3: career_over_family: 16, threat_bridge: 15, status_reveal: 14, romance_interruption: 3
- Episode 4: romance_interruption: 11, status_reveal: 11, public_exposure: 9, competence_win: 9
- Episode 5: career_over_family: 19, threat_bridge: 16, public_exposure: 11, status_reveal: 3
- Episode 6: competence_win: 12, career_over_family: 9, status_reveal: 8, public_exposure: 8
- Episode 7: status_reveal: 19, threat_bridge: 16, career_over_family: 9, romance_interruption: 6
- Episode 8: romance_interruption: 14, career_over_family: 10, public_exposure: 9, threat_bridge: 4
