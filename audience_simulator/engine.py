from __future__ import annotations

import dataclasses
import hashlib
import random

from .cohorts import INDIA_ENGLISH_COHORT_NAME
from .models import Episode, Persona, PersonaState, Reaction
from .signals import episode_signals, strongest_drop_beat
from .utils import clamp, weighted_choice


class IndiaEnglishHeuristicEngine:
    """Deterministic local engine for India/English listener behavior."""

    cohort_name = INDIA_ENGLISH_COHORT_NAME
    engine_name = "india_english_heuristic_v1"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def react(
        self,
        run_id: str,
        persona: Persona,
        state: PersonaState,
        episode: Episode,
    ) -> tuple[Reaction, PersonaState]:
        rng_seed = f"{self.seed}:{run_id}:{persona.persona_id}:{episode.episode_no}"
        rng = random.Random(hashlib.sha256(rng_seed.encode("utf-8")).hexdigest())
        signals = episode_signals(episode)

        identity = persona.driver_intensity["identity"]
        wish = persona.driver_intensity["wish_fulfillment"]
        escapism = persona.driver_intensity["escapism"]
        justice = persona.driver_intensity["justice_seeking"]
        comfort = persona.driver_intensity["comfort"]
        romance_affinity = max(
            persona.genre_affinity.get("modern_romance", 0.0),
            persona.genre_affinity.get("dark_romance", 0.0),
        )
        family_affinity = persona.genre_affinity.get("family_drama", 0.0)
        thriller_affinity = max(
            persona.genre_affinity.get("revenge", 0.0),
            persona.genre_affinity.get("crime_mystery", 0.0),
            persona.genre_affinity.get("horror", 0.0),
        )
        progression_affinity = max(
            persona.genre_affinity.get("system_progression", 0.0),
            persona.genre_affinity.get("office_drama", 0.0),
        )
        mystery_pressure = max(signals["cliffhanger"], signals["ending_cliffhanger"])

        ambition_fit = 0.22 * identity * signals["ambition"]
        competence_fit = 0.25 * max(identity, wish) * signals["competence"]
        status_fit = 0.18 * max(wish, progression_affinity) * max(signals["status"], signals["ending_status_reveal"])
        urban_fit = 0.10 * signals["urban_modern"]
        justice_fit = 0.13 * justice * max(signals["humiliation"], signals["public_vindication"])
        romance_fit = 0.12 * romance_affinity * signals["romance"]
        if (
            persona.region_id == "tier1_aspirational_escapists"
            and signals["ambition"] < 0.10
            and signals["competence"] < 0.10
        ):
            romance_fit *= 0.45
        family_fit = 0.12 * max(family_affinity, comfort) * signals["family"]
        if persona.region_id not in {"household_catharsis_devotees", "slow_burn_comfort_seekers", "justice_payoff_bingers"}:
            family_fit *= 0.35
        thriller_fit = 0.15 * thriller_affinity * max(
            signals["humiliation"],
            signals["cliffhanger"],
            signals["ending_cliffhanger"],
        )
        progression_fit = 0.11 * progression_affinity * max(signals["status"], signals["competence"])
        cliffhanger_fit = 0.16 * escapism * signals["ending_cliffhanger"]
        comfort_fit = 0.09 * comfort * max(signals["romance"], signals["family"])
        language_fit = self._language_fit(persona, signals)

        family_penalty = 0.17 * signals["family_only"]
        if persona.region_id in {"household_catharsis_devotees", "slow_burn_comfort_seekers"}:
            family_penalty *= 0.20
        elif persona.anti_stereotype == "family_bridge":
            family_penalty *= 0.35
        passive_penalty = 0.20 * signals["agency_gap"]
        if persona.anti_stereotype == "ambition_required":
            passive_penalty *= 1.35
        regressive_penalty = 0.15 * signals["regressive"]
        filler_penalty = 0.13 * signals["filler"]
        if persona.region_id == "high_churn_thrill_chasers" and mystery_pressure < 0.14:
            filler_penalty += 0.06
        exposition_penalty = 0.08 * signals["exposition_load"] * (1.0 - persona.narrative_patience)
        if persona.interruption_load == "high":
            exposition_penalty *= 1.25
        resolved_penalty = 0.08 * signals["resolved_no_hook"]
        trust_bonus = 0.05 * state.payoff_trust + 0.04 * state.agency_trust
        fatigue_penalty = 0.10 + 0.10 * persona.churn_sensitivity if episode.episode_no > persona.commitment_tolerance else 0.0
        noise = rng.gauss(0.0, 0.045)

        engagement_score = clamp(
            0.47
            + ambition_fit
            + competence_fit
            + status_fit
            + urban_fit
            + justice_fit
            + romance_fit
            + family_fit
            + thriller_fit
            + progression_fit
            + cliffhanger_fit
            + comfort_fit
            + language_fit
            + trust_bonus
            - family_penalty
            - passive_penalty
            - regressive_penalty
            - filler_penalty
            - exposition_penalty
            - resolved_penalty
            - fatigue_penalty
            + noise,
            0.0,
            1.0,
        )
        continue_threshold = clamp(
            0.53
            + persona.churn_sensitivity * 0.15
            - persona.narrative_patience * 0.12
            + self._region_threshold_shift(persona)
            - 0.05 * clamp(persona.historical_completion - 0.50, 0.0, 0.50)
            + 0.04 * clamp(0.45 - persona.historical_completion, 0.0, 0.45),
            0.36,
            0.72,
        )
        will_continue = engagement_score >= continue_threshold

        pay_pressure = self._pay_pressure(persona, state, signals, engagement_score)
        would_pay = will_continue and pay_pressure >= persona.pay_threshold

        risky_beat, risk_score = strongest_drop_beat(episode, persona)
        if not will_continue:
            drop_beat = risky_beat
        elif risk_score > 0.62 and rng.random() < risk_score - 0.30:
            drop_beat = risky_beat
        else:
            drop_beat = None

        craving_mid = round(1 + 9 * clamp(engagement_score - 0.10 + signals["event_density"] * 0.06, 0.0, 1.0))
        craving_end = round(
            1
            + 9
            * clamp(
                engagement_score
                + 0.15 * signals["ending_cliffhanger"]
                + 0.11 * signals["ending_status_reveal"]
                + 0.07 * signals["ending_romance_pressure"]
                - 0.09 * signals["resolved_no_hook"],
                0.0,
                1.0,
            )
        )

        craving_mid_int = int(clamp(craving_mid, 1, 10))
        craving_end_int = int(clamp(craving_end, 1, 10))
        emotional_state = self._emotional_state(will_continue, engagement_score, signals)
        next_state = self._update_state(persona, state, episode, signals, will_continue, would_pay)
        reaction = Reaction(
            run_id=run_id,
            persona_id=persona.persona_id,
            cohort=self.cohort_name,
            episode_no=episode.episode_no,
            will_continue=will_continue,
            continue_reason=self._continue_reason(will_continue, signals, persona),
            would_pay=would_pay,
            pay_reason=self._pay_reason(would_pay, pay_pressure, persona, signals),
            drop_beat=drop_beat,
            craving_mid=craving_mid_int,
            craving_end=craving_end_int,
            next_prediction=self._prediction(signals, persona, rng),
            emotional_state=emotional_state,
            felt_emotion=self._felt_emotion(will_continue, emotional_state, signals),
            emotion_shift=self._emotion_shift(craving_mid_int, craving_end_int),
            judgement_bridge=self._judgement_bridge(
                will_continue,
                emotional_state,
                craving_mid_int,
                craving_end_int,
                persona,
                signals,
            ),
            decision_factors=self._decision_factors(
                will_continue,
                persona,
                signals,
                drop_beat,
            ),
            engagement_score=round(engagement_score, 4),
            pay_pressure=round(pay_pressure, 4),
            signal_json=signals,
            state_json=dataclasses.asdict(next_state),
        )
        return reaction, next_state

    def _language_fit(self, persona: Persona, signals: dict[str, float]) -> float:
        hinglish = signals["hinglish"]
        if persona.language_register == "Hinglish":
            return 0.055 * clamp(hinglish + 0.35, 0.0, 1.0)
        if persona.language_register == "urban English":
            return 0.035 * clamp(signals["urban_modern"] + hinglish * 0.4, 0.0, 1.0)
        if persona.language_register == "polished English":
            return 0.025 * signals["urban_modern"] - 0.035 * max(0.0, hinglish - 0.55)
        return 0.025 * signals["event_density"]

    def _region_threshold_shift(self, persona: Persona) -> float:
        shifts = {
            "slow_burn_comfort_seekers": -0.055,
            "household_catharsis_devotees": -0.035,
            "status_progression_loyalists": -0.020,
            "justice_payoff_bingers": -0.010,
            "tier1_aspirational_escapists": 0.010,
            "high_churn_thrill_chasers": 0.060,
        }
        shift = shifts.get(persona.region_id, 0.0)
        if persona.session_pattern == "trial":
            shift += 0.05
        if persona.interruption_load == "high":
            shift += 0.015
        return shift

    def _pay_pressure(
        self,
        persona: Persona,
        state: PersonaState,
        signals: dict[str, float],
        engagement_score: float,
    ) -> float:
        pressure = (
            0.10
            + 0.30 * signals["ending_cliffhanger"]
            + 0.26 * signals["ending_status_reveal"]
            + 0.19 * signals["public_vindication"]
            + 0.16 * signals["ending_romance_pressure"] * persona.genre_affinity["modern_romance"]
            + 0.10 * max(signals["humiliation"], signals["public_vindication"]) * persona.driver_intensity["justice_seeking"]
            + 0.08 * max(signals["status"], signals["competence"]) * persona.genre_affinity.get("system_progression", 0.0)
            + 0.06 * min(len(state.unresolved_questions), 4)
            + 0.12 * clamp(engagement_score - 0.50, 0.0, 1.0)
        )
        if signals["resolved_no_hook"]:
            pressure -= 0.14
        if persona.anti_stereotype == "paywall_skeptic":
            pressure -= 0.08
        if persona.region_id == "slow_burn_comfort_seekers" and signals["ending_romance_pressure"] > 0.25:
            pressure += 0.08
        if persona.region_id == "high_churn_thrill_chasers" and signals["ending_cliffhanger"] < 0.10:
            pressure -= 0.06
        return clamp(pressure, 0.0, 1.0)

    def _continue_reason(self, will_continue: bool, signals: dict[str, float], persona: Persona) -> str:
        positives = [
            ("the lead makes active choices under pressure", signals["agency"] + signals["competence"]),
            ("ambition or status momentum is moving", signals["ambition"] + signals["status"]),
            ("the urban English/Hinglish setting matches the listening mode", signals["urban_modern"] + signals["hinglish"] * 0.5),
            ("the relationship pressure is emotionally useful", signals["romance"] * max(persona.genre_affinity.get("modern_romance", 0.0), persona.genre_affinity.get("dark_romance", 0.0))),
            ("family pressure is creating catharsis", signals["family"] * persona.genre_affinity.get("family_drama", 0.0)),
            ("danger and mystery are moving fast enough", max(signals["cliffhanger"], signals["humiliation"]) * max(persona.genre_affinity.get("crime_mystery", 0.0), persona.genre_affinity.get("revenge", 0.0))),
            ("the ending leaves a live reveal", signals["ending_cliffhanger"] + signals["ending_status_reveal"]),
            ("public humiliation is answered with visible proof", signals["humiliation"] + signals["public_vindication"]),
        ]
        negatives = [
            ("family pressure is not paired with enough payoff", signals["family_only"] * (1.0 - persona.genre_affinity.get("family_drama", 0.0))),
            ("the protagonist feels passive", signals["agency_gap"]),
            ("the episode reads like recap or filler", signals["filler"] + signals["exposition_load"]),
            ("the ending resolves too cleanly for a serial", signals["resolved_no_hook"]),
            ("the gender or family framing feels regressive", signals["regressive"]),
            ("the hook is too soft for a high-churn sampler", 0.30 if persona.region_id == "high_churn_thrill_chasers" and signals["ending_cliffhanger"] < 0.10 else 0.0),
        ]
        if will_continue:
            reasons = [text for text, score in sorted(positives, key=lambda item: item[1], reverse=True)[:2] if score > 0.12]
            if not reasons:
                reasons = ["there is enough unresolved story pressure for this listener"]
            return "Continues because " + " and ".join(reasons) + "."
        reasons = [text for text, score in sorted(negatives, key=lambda item: item[1], reverse=True)[:2] if score > 0.08]
        if not reasons:
            reasons = ["the episode does not create enough payoff, agency, relationship, or cliffhanger pressure"]
        return "Drops because " + " and ".join(reasons) + "."

    def _pay_reason(
        self,
        would_pay: bool,
        pay_pressure: float,
        persona: Persona,
        signals: dict[str, float],
    ) -> str:
        if would_pay:
            if signals["ending_status_reveal"] >= signals["ending_cliffhanger"]:
                return "Pays because the gate blocks a status, identity, or truth reveal."
            if signals["ending_romance_pressure"] > 0.35 and persona.genre_affinity.get("modern_romance", 0.0) > 0.55:
                return "Pays because the relationship beat is unresolved and emotionally charged."
            if signals["humiliation"] > 0.25 or signals["public_vindication"] > 0.25:
                return "Pays because the gate blocks a revenge or justice payoff."
            return "Pays because the ending leaves enough unresolved pressure to justify coins."
        if pay_pressure < persona.pay_threshold:
            return "Does not pay because the gate is not sharper than this listener's coin threshold."
        return "Does not pay because the story interest is not strong enough to survive a paywall."

    def _prediction(self, signals: dict[str, float], persona: Persona, rng: random.Random) -> str:
        options = []
        if signals["public_vindication"] + signals["competence"] > 0.12:
            options.append(
                (
                    "A practical clue or proof will force the truth closer to the surface.",
                    signals["public_vindication"] + signals["competence"],
                )
            )
        if signals["family"] + signals["agency"] > 0.12:
            options.append(
                (
                    "Meenakshi or Tara will make another risky cover-up choice to protect the family.",
                    signals["family"] + signals["agency"] + persona.driver_intensity["identity"] * 0.2,
                )
            )
        if signals["romance"] + signals["ending_romance_pressure"] > 0.18:
            options.append(
                (
                    "A relationship confession will be interrupted before it can settle.",
                    signals["romance"] + signals["ending_romance_pressure"],
                )
            )
        if signals["ending_status_reveal"] + signals["status"] > 0.18:
            options.append(
                (
                    "A hidden status or identity truth will surface at the worst possible moment.",
                    signals["ending_status_reveal"] + signals["status"],
                )
            )
        if signals["cliffhanger"] + signals["family"] > 0.12:
            options.append(
                (
                    "The police trail or hidden body will tighten pressure around the family.",
                    signals["cliffhanger"] + signals["family"],
                )
            )
        if signals["competence"] + signals["agency"] > 0.12:
            options.append(
                (
                    "The lead will try a tactical move to stay ahead of the next threat.",
                    signals["competence"] + signals["agency"],
                )
            )
        if signals["family"] * persona.genre_affinity.get("family_drama", 0.0) > 0.12:
            options.append(
                (
                    "A family secret or guilt will become the next emotional trap.",
                    signals["family"] * persona.genre_affinity.get("family_drama", 0.0),
                )
            )
        if signals["cliffhanger"] * persona.genre_affinity.get("crime_mystery", 0.0) > 0.10:
            options.append(
                (
                    "The next clue will reveal who is lying.",
                    signals["cliffhanger"] * persona.genre_affinity.get("crime_mystery", 0.0),
                )
            )
        if signals["humiliation"] * persona.genre_affinity.get("revenge", 0.0) > 0.10:
            options.append(
                (
                    "The setback will turn into a revenge move.",
                    signals["humiliation"] * persona.genre_affinity.get("revenge", 0.0),
                )
            )
        if not options:
            options = [
                ("A clue will make the cover-up harder to sustain.", 0.40),
                ("The next episode will test whether the secret stays buried.", 0.35),
                ("A character close to the secret will make a mistake.", 0.25),
            ]
        return weighted_choice(rng, options)

    def _emotional_state(self, will_continue: bool, score: float, signals: dict[str, float]) -> str:
        if not will_continue and signals["agency_gap"] > 0.20:
            return "frustrated by lost agency"
        if not will_continue:
            return "detached"
        if score > 0.78 and signals["ending_cliffhanger"] > 0.20:
            return "impatient for the next reveal"
        if signals["public_vindication"] > 0.35:
            return "energized by visible payoff"
        if signals["romance"] > 0.25:
            return "emotionally invested"
        if signals["family"] > 0.25:
            return "concerned and waiting for consequences"
        return "engaged"

    def _felt_emotion(self, will_continue: bool, emotional_state: str, signals: dict[str, float]) -> str:
        if not will_continue:
            return emotional_state
        if signals["ending_cliffhanger"] > 0.20:
            return "tense curiosity"
        if signals["public_vindication"] > 0.30:
            return "satisfied momentum"
        if signals["resolved_no_hook"] > 0.30:
            return "settled but less urgent"
        return emotional_state

    def _emotion_shift(self, craving_mid: int, craving_end: int) -> str:
        delta = craving_end - craving_mid
        if delta >= 2:
            return "craving rose sharply by the ending"
        if delta == 1:
            return "craving rose modestly by the ending"
        if delta == 0:
            return "emotion held steady through the ending"
        if delta == -1:
            return "craving softened by the ending"
        return "craving dropped sharply by the ending"

    def _judgement_bridge(
        self,
        will_continue: bool,
        emotional_state: str,
        craving_mid: int,
        craving_end: int,
        persona: Persona,
        signals: dict[str, float],
    ) -> str:
        direction = "starts the next episode" if will_continue else "stops here"
        delta = craving_end - craving_mid
        if will_continue and delta < 0:
            return (
                f"{persona.region_label} still {direction} because {emotional_state} outweighs "
                "the softened craving for this persona."
            )
        if will_continue:
            return f"{persona.region_label} {direction} because the ending emotion creates enough next-play pull."
        if signals["resolved_no_hook"] > 0.30:
            return f"{persona.region_label} {direction} because the ending releases tension without a strong new hook."
        return f"{persona.region_label} {direction} because the episode emotion does not overcome churn pressure."

    def _decision_factors(
        self,
        will_continue: bool,
        persona: Persona,
        signals: dict[str, float],
        drop_beat: str | None,
    ) -> list[str]:
        factors = [
            f"region={persona.region_label}",
            f"churn={persona.churn_sensitivity:.2f}",
            f"patience={persona.narrative_patience:.2f}",
        ]
        if signals["ending_cliffhanger"] > 0.20:
            factors.append("ending cliffhanger creates pull")
        if signals["resolved_no_hook"] > 0.30:
            factors.append("ending resolves tension")
        if signals["agency"] > 0.20:
            factors.append("lead agency supports continuation")
        if drop_beat:
            factors.append(f"drop beat={drop_beat}")
        if not will_continue and signals["family_only"] > 0.20:
            factors.append("family pressure lacks enough cross-genre payoff")
        return factors[:5]

    def _update_state(
        self,
        persona: Persona,
        state: PersonaState,
        episode: Episode,
        signals: dict[str, float],
        will_continue: bool,
        would_pay: bool,
    ) -> PersonaState:
        unresolved = list(state.unresolved_questions)
        if signals["ending_cliffhanger"] > 0.20:
            unresolved.append(f"Episode {episode.episode_no} ending reveal")
        if signals["public_vindication"] > 0.30 and unresolved:
            unresolved = unresolved[-3:]
        if len(unresolved) > 6:
            unresolved = unresolved[-6:]

        payoff_trust = clamp(
            state.payoff_trust
            + 0.10 * signals["public_vindication"]
            + 0.08 * signals["competence"]
            - 0.07 * signals["filler"]
            - 0.06 * signals["resolved_no_hook"],
            0.0,
            1.0,
        )
        agency_trust = clamp(
            state.agency_trust
            + 0.10 * signals["agency"]
            + 0.08 * signals["competence"]
            - 0.12 * signals["agency_gap"]
            - 0.08 * signals["regressive"],
            0.0,
            1.0,
        )
        summary_bits = []
        if signals["ambition"] > 0.15:
            summary_bits.append("career stakes")
        if signals["public_vindication"] > 0.20:
            summary_bits.append("public proof/payoff")
        if signals["family"] > 0.18:
            summary_bits.append("family pressure")
        if signals["romance"] > 0.18:
            summary_bits.append("romance tension")
        summary = state.story_summary
        if summary_bits:
            summary = (summary + f" Ep {episode.episode_no}: " + ", ".join(summary_bits) + ".").strip()
        summary = summary[-900:]

        return PersonaState(
            persona_id=persona.persona_id,
            episodes_heard=state.episodes_heard + (1 if will_continue else 0),
            active=will_continue,
            dropped_at=None if will_continue else f"episode_{episode.episode_no}",
            story_summary=summary,
            unresolved_questions=unresolved,
            payoff_trust=round(payoff_trust, 4),
            agency_trust=round(agency_trust, 4),
            coins_spent=state.coins_spent + (30 if would_pay else 0),
        )
