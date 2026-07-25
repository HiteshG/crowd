# Audience Simulator Report

Run ID: `brahmastra-30-ep1`
Cohort: **India/English Aspirational Escapists**
Population: **30 synthetic listeners**
Episodes: **1**

> Uncalibrated simulator output. Use rankings, drop points, and directional diagnosis until backtested against real retention.

## Verdict

- Recommendation: `major_rewrite`
- Confidence: `medium-low`
- Final retained from start: **30.0%**
- Mean continue rate: **30.0%**
- Mean craving delta: **0.80**
- Mean prediction entropy: **1.86**

## India/English Cohort Model

- Market: India, English/Hinglish, mostly Tier 1 with Tier 2 aspirational spillover
- Drivers: identity, wish_fulfillment, escapism
- Retention hooks: competence win, public professional vindication, status or ownership reveal, romance that supports ambition, office/startup/social-mobility stakes
- Drop triggers: lead becomes passive, ambition collapses into pure romance, family melodrama crowds out the modern setting, regressive gender framing, translated or unnatural English register, filler before the first competence payoff
- Pay triggers: gate before public vindication, gate before status reveal, gate before career/relationship collision

## Episode Metrics

| Ep | Title | Active | Continue | Retained | Pay | Craving Delta | Entropy | Top Drop Beat |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | "The Fire That Remembers" | 30 | 30.0% | 30.0% | 0.0% | 0.80 | 1.86 | s001_b10 |

## Triage

- Weakest continue point: episode 1 ("The Fire That Remembers"), 30.0% continue.
- First beat to inspect: `s001_b10`.
- Best paywall candidate in this run: episode 1 ("The Fire That Remembers"), 0.0% simulated pay.

## Prediction Buckets

- Episode 1: career_over_family: 11, threat_bridge: 10, public_exposure: 6, status_reveal: 3
