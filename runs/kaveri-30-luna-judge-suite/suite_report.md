# House On Kaveri Lane - Audience Simulation Suite Report

Suite `kaveri-30-luna-judge-suite` | 3 main-loop runs | 30 personas/run | model `gpt-5.6-luna` | reasoning `medium` | judgement `llm`
> Uncalibrated simulator output. Use agreement across runs as directional signal, not calibrated audience truth.

## Verdict Across Runs

- Recommendation counts: {'major_rewrite': 3}
- Final retained index: mean 0.0, range 0.0-0.0.
- Judge changed final decisions for 46 of 461 persona-episode reactions (10.0%); reasoning was rewritten for 100.0%.

## Episode Stability

| Ep | Title | Mean continue | Range | Mean retained idx | Mean pay | Craving delta | Mean drops | Top drop beats |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | The Spill | 98.9% | 96.7%-100.0% | 98.9 | 6.7% | 1.59 | 0.3 | s001_b06 (1) |
| 2 | The Scent of Bleach | 98.9% | 96.7%-100.0% | 97.8 | 7.9% | 1.65 | 0.3 | s002_b05 (1) |
| 3 | The Buried Ring | 66.8% | 27.6%-86.7% | 65.6 | 2.3% | 0.08 | 9.7 | s003_b10 (21), s003_b07 (4), s003_b06 (4) |
| 4 | The Weak Link | 77.7% | 64.0%-100.0% | 46.7 | 9.6% | 1.59 | 5.7 | s004_b06 (9), s004_b01 (8) |
| 5 | The Muddy Shoes | 95.8% | 87.5%-100.0% | 45.6 | 12.0% | 1.47 | 0.3 | s005_b07 (1) |
| 6 | The Cornered Animal | 76.4% | 62.5%-100.0% | 32.2 | 0.0% | -0.52 | 4.0 | s006_b05 (6), s006_b01 (4), s006_b09 (2) |
| 7 | The Interrogation | 82.2% | 66.7%-100.0% | 25.6 | 15.6% | -0.85 | 2.0 | s007_b07 (4), s007_b08 (1), s007_b05 (1) |
| 8 | Washed Clean | 0.0% | 0.0%-0.0% | 0.0 | 0.0% | -4.12 | 7.7 | s008_b06 (9), s008_b01 (7), s008_b08 (3), s008_b03 (2) |

## Run Details

| Run | Seed | Recommendation | Final idx | Weakest ep | Paywall candidate |
|---|---:|---|---:|---|---|
| `kaveri-30-luna-judge-suite-r01-s7` | 7 | major_rewrite | 0.0 | 8 Washed Clean | 5 The Muddy Shoes |
| `kaveri-30-luna-judge-suite-r02-s8` | 8 | major_rewrite | 0.0 | 8 Washed Clean | 1 The Spill |
| `kaveri-30-luna-judge-suite-r03-s9` | 9 | major_rewrite | 0.0 | 8 Washed Clean | 7 The Interrogation |

## Emotion To Judgement Signals

- 1 agent-episodes: Although the story has weak fit with Arjun’s usual ambition-and-status interests, the direct confrontation hook is unusually strong, the danger is immediately legible, and the episode suits his interrupted listening context. That specific crisis outweighs the low region fit for one more free episode.
- 1 agent-episodes: The strong crisis cliffhanger is more compelling than the episode's low initial payoff trust: Neha has a clear next-play question—what does Malini know, and can they keep her out?
- 1 agent-episodes: The episode gives danger from its opening, concrete evidence risks through the cover story and missing phone, and a direct confrontation at the end. That specific imminent payoff outweighs churn pressure and supports starting Episode 2.
- 1 agent-episodes: The ending's concrete confrontation threat outweighs the low regional fit for one more episode, but it does not yet establish enough payoff trust to justify payment.
- 1 agent-episodes: Although the episode lacks Diya’s preferred status progression and power fantasy, its fast, easy-to-follow escalation and concrete confrontation create a stronger immediate counterweight than the low region fit and churn pressure.
- 1 agent-episodes: Although payoff trust is still low and churn pressure is unusually high, the hook is concrete rather than generic: Malini is at the door now, and the missing phone threatens the cover-up. The free episode also removes her main testing barrier.
- 1 agent-episodes: Kabir's justice need is not yet satisfied, but the threat of public exposure is a credible first step toward consequence. That concrete crisis hook outweighs the borderline fit and low payoff trust for one more free episode.
- 1 agent-episodes: Craving rises rather than settles because the final beat introduces a direct confrontation, not merely a vague mystery. That concrete imminent threat is strong enough to overcome Arjun’s lower need-region fit and continue once, but not strong enough to create payment trust.

## Methods

- Main loop per repeat: LLM story beats -> seeded persona panel -> LLM persona reaction -> LLM judge final decision -> state update -> next episode.
- Episode intelligence mode: `auto`.
- Guardrail mode: `advisory`; judge decisions are LLM decisions, not parser decisions.
- Individual run reports live in each repeat run directory under this suite directory.
