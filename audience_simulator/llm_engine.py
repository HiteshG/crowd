from __future__ import annotations

import dataclasses
import hashlib
import json
import urllib.error
import urllib.request
from typing import Any

from .env import openai_api_key, openai_model_candidates
from .episode_intelligence import persona_drop_guardrail
from .models import Episode, Persona, PersonaState, REACTION_SCHEMA, Reaction
from .prompting import build_llm_reaction_payload
from .signals import episode_signals, strongest_drop_beat
from .utils import clamp


class OpenAIResponsesEngine:
    """Optional AI reaction engine using the OpenAI Responses API.

    The simulator can run without this module. Use it only when you want the
    persona to deliberate in prose before returning schema-constrained behavior.
    """

    cohort_name = "India/English Pocket-FM Listener Panel"
    engine_name = "openai_responses_llm_v1"

    def __init__(
        self,
        seed: int,
        model: str = "gpt-5.6-luna",
        timeout_seconds: int = 90,
        reasoning_effort: str = "medium",
        guardrail_mode: str = "advisory",
        judgement_mode: str = "off",
        behavioral_guardrails: bool | None = None,
    ) -> None:
        if behavioral_guardrails is False:
            guardrail_mode = "off"
        if guardrail_mode not in {"advisory", "override", "off"}:
            raise ValueError(f"Unknown guardrail mode '{guardrail_mode}'")
        if reasoning_effort not in {"minimal", "low", "medium", "high"}:
            raise ValueError(f"Unknown reasoning effort '{reasoning_effort}'")
        if judgement_mode not in {"off", "llm"}:
            raise ValueError(f"Unknown judgement mode '{judgement_mode}'")
        self.seed = seed
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.reasoning_effort = reasoning_effort
        self.guardrail_mode = guardrail_mode
        self.behavioral_guardrails = guardrail_mode != "off"
        self.judgement_mode = judgement_mode
        self.judge = None
        if self.judgement_mode == "llm":
            from .llm_judge import OpenAIJudgementLayer

            self.judge = OpenAIJudgementLayer(
                model=model,
                reasoning_effort=reasoning_effort,
                timeout_seconds=timeout_seconds,
            )
        self.episode_intelligence_by_no: dict[int, dict[str, Any]] = {}

    def set_episode_intelligence(self, episode_intelligence_by_no: dict[int, dict[str, Any]]) -> None:
        self.episode_intelligence_by_no = episode_intelligence_by_no

    def react(
        self,
        run_id: str,
        persona: Persona,
        state: PersonaState,
        episode: Episode,
    ) -> tuple[Reaction, PersonaState]:
        episode_intelligence = self.episode_intelligence_by_no.get(episode.episode_no)
        payload = build_llm_reaction_payload(
            persona,
            state,
            episode,
            episode_intelligence,
            decision_seed=self._request_seed(run_id, persona, episode),
        )
        raw_result = self._call_model(payload, run_id, persona, episode)
        result, judgement_meta = self._apply_judgement_layer(
            persona=persona,
            state=state,
            episode=episode,
            episode_intelligence=episode_intelligence,
            raw_result=raw_result,
        )
        signals = episode_signals(episode)

        will_continue = bool(result["will_continue"])
        would_pay = bool(result["would_pay"]) and will_continue
        drop_beat = self._validated_drop_beat(result.get("drop_beat"), will_continue, episode, persona)

        craving_mid = int(clamp(int(result["craving_mid"]), 1, 10))
        craving_end = int(clamp(int(result["craving_end"]), 1, 10))
        continue_reason = str(result["continue_reason"])
        emotional_state = str(result["emotional_state"])
        guardrail = self._guardrail_adjustment(
            run_id=run_id,
            persona=persona,
            state=state,
            episode=episode,
            result=result,
            will_continue=will_continue,
        )
        applied_guardrail_override = False
        if self.guardrail_mode == "override" and will_continue and guardrail["should_drop"]:
            applied_guardrail_override = True
            will_continue = False
            would_pay = False
            drop_beat = guardrail["beat_id"] or strongest_drop_beat(episode, persona)[0]
            craving_end = min(craving_end, 5)
            continue_reason = (
                f"Drops by Episode Intelligence guardrail: {guardrail['reason']} "
                f"(pressure {guardrail['pressure']}, threshold {guardrail['threshold']}). "
                f"LLM reaction before guardrail: {str(result['continue_reason'])[:180]}"
            )
            emotional_state = "structurally at-risk despite surface curiosity"
        engagement_score = self._engagement_score(will_continue, craving_mid, craving_end)
        pay_pressure = self._pay_pressure(would_pay, signals, craving_end)
        next_state = self._update_state(persona, state, episode, signals, will_continue, would_pay)
        signals = {
            **signals,
            "guardrail_pressure": guardrail["pressure"],
            "guardrail_threshold": guardrail["threshold"],
            "guardrail_base_threshold": guardrail.get("base_threshold", 1.0),
            "guardrail_override_margin": guardrail.get("override_margin", 0.0),
            "guardrail_recommended_drop": 1.0 if guardrail["should_drop"] else 0.0,
            "guardrail_applied_override": 1.0 if applied_guardrail_override else 0.0,
            "guardrail_override": 1.0 if applied_guardrail_override else 0.0,
            "guardrail_rank": guardrail.get("rank", 0.0),
            "guardrail_abandon_pressure": guardrail.get("abandon_pressure", 0.0),
            "guardrail_cohort_fit": guardrail.get("cohort_fit", 0.0),
            "judgement_changed_decision": 1.0 if judgement_meta["changed_decision"] else 0.0,
            "judgement_changed_reasoning": 1.0 if judgement_meta["changed_reasoning"] else 0.0,
        }

        reaction = Reaction(
            run_id=run_id,
            persona_id=persona.persona_id,
            cohort=self.cohort_name,
            episode_no=episode.episode_no,
            will_continue=will_continue,
            continue_reason=continue_reason,
            would_pay=would_pay,
            pay_reason=str(result["pay_reason"]),
            drop_beat=drop_beat,
            craving_mid=craving_mid,
            craving_end=craving_end,
            next_prediction=str(result["next_prediction"]),
            emotional_state=emotional_state,
            felt_emotion=str(result["felt_emotion"]),
            emotion_shift=str(result["emotion_shift"]),
            judgement_bridge=str(result["judgement_bridge"]),
            decision_factors=_clean_decision_factors(result.get("decision_factors")),
            engagement_score=engagement_score,
            pay_pressure=pay_pressure,
            signal_json=signals,
            state_json=dataclasses.asdict(next_state),
            judgement_agent=judgement_meta["agent"],
            judgement_changed=bool(judgement_meta["changed_decision"] or judgement_meta["changed_reasoning"]),
            judgement_notes=judgement_meta["notes"],
            raw_reaction_json=raw_result if self.judgement_mode == "llm" else None,
        )
        return reaction, next_state

    def _apply_judgement_layer(
        self,
        *,
        persona: Persona,
        state: PersonaState,
        episode: Episode,
        episode_intelligence: dict[str, Any] | None,
        raw_result: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not self.judge:
            return raw_result, {
                "agent": "none",
                "changed_decision": False,
                "changed_reasoning": False,
                "notes": "judgement layer disabled",
            }
        judged, meta = self.judge.judge(
            persona=persona,
            state=state,
            episode=episode,
            episode_intelligence=episode_intelligence,
            raw_reaction=raw_result,
        )
        for extra_key in ["judgement_notes", "changed_decision", "changed_reasoning"]:
            judged.pop(extra_key, None)
        _validate_reaction_payload(judged)
        return judged, meta

    def _guardrail_adjustment(
        self,
        *,
        run_id: str,
        persona: Persona,
        state: PersonaState,
        episode: Episode,
        result: dict[str, Any],
        will_continue: bool,
    ) -> dict[str, Any]:
        if not self.behavioral_guardrails:
            return _empty_guardrail("guardrail disabled")
        return persona_drop_guardrail(
            persona=persona,
            state=state,
            episode=episode,
            episode_intelligence=self.episode_intelligence_by_no.get(episode.episode_no),
            llm_result=result,
            seed=self.seed,
            run_id=run_id,
        )

    def _validated_drop_beat(
        self,
        raw_drop_beat: Any,
        will_continue: bool,
        episode: Episode,
        persona: Persona,
    ) -> str | None:
        if will_continue:
            return None
        valid_ids = {beat.beat_id for beat in episode.beats}
        if isinstance(raw_drop_beat, str) and raw_drop_beat in valid_ids:
            return raw_drop_beat
        return strongest_drop_beat(episode, persona)[0]

    def _call_model(
        self,
        payload: dict[str, Any],
        run_id: str,
        persona: Persona,
        episode: Episode,
    ) -> dict[str, Any]:
        api_key = openai_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when using --engine llm")

        last_model_error: RuntimeError | None = None
        for candidate_model in openai_model_candidates(self.model):
            try:
                result = self._call_model_once(api_key, candidate_model, payload, run_id, persona, episode)
                return result
            except RuntimeError as exc:
                if not _is_model_availability_error(str(exc)):
                    raise
                last_model_error = exc
        if last_model_error:
            raise last_model_error
        raise RuntimeError("No OpenAI model candidates configured")

    def _call_model_once(
        self,
        api_key: str,
        model: str,
        payload: dict[str, Any],
        run_id: str,
        persona: Persona,
        episode: Episode,
    ) -> dict[str, Any]:
        request_payload = {
            "model": model,
            "input": [
                {"role": "system", "content": payload["system"]},
                {"role": "user", "content": payload["messages"][0]["content"]},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "audience_reaction",
                    "schema": REACTION_SCHEMA,
                    "strict": True,
                }
            },
            "reasoning": {"effort": self.reasoning_effort},
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI API request failed: {exc}") from exc

        data = json.loads(body)
        text = _extract_output_text(data)
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Model returned non-JSON output: {text[:500]}") from exc
        _validate_reaction_payload(result)
        return result

    def _request_seed(self, run_id: str, persona: Persona, episode: Episode) -> int:
        value = f"{self.seed}:{run_id}:{persona.persona_id}:{episode.episode_no}"
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return int(digest[:12], 16) % 2_000_000_000

    def _engagement_score(
        self,
        will_continue: bool,
        craving_mid: int,
        craving_end: int,
    ) -> float:
        base = ((craving_mid + craving_end) / 20.0) + (0.08 if will_continue else -0.10)
        return round(clamp(base, 0.0, 1.0), 4)

    def _pay_pressure(
        self,
        would_pay: bool,
        signals: dict[str, float],
        craving_end: int,
    ) -> float:
        pressure = (
            0.12
            + 0.20 * (craving_end / 10.0)
            + 0.24 * signals["ending_cliffhanger"]
            + 0.18 * signals["ending_status_reveal"]
            + 0.14 * signals["ending_romance_pressure"]
            + (0.20 if would_pay else 0.0)
        )
        return round(clamp(pressure, 0.0, 1.0), 4)

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
        if signals["ending_status_reveal"] > 0.15:
            unresolved.append(f"Episode {episode.episode_no} status reveal")
        unresolved = unresolved[-6:]

        payoff_trust = clamp(
            state.payoff_trust
            + 0.08 * signals["public_vindication"]
            + 0.06 * signals["competence"]
            - 0.05 * signals["filler"]
            - 0.05 * signals["resolved_no_hook"],
            0.0,
            1.0,
        )
        agency_trust = clamp(
            state.agency_trust
            + 0.08 * signals["agency"]
            + 0.06 * signals["competence"]
            - 0.10 * signals["agency_gap"],
            0.0,
            1.0,
        )
        summary = state.story_summary
        summary_bits = []
        if signals["romance"] > 0.18:
            summary_bits.append("romance tension")
        if signals["cliffhanger"] > 0.18:
            summary_bits.append("threat or mystery")
        if signals["public_vindication"] > 0.20:
            summary_bits.append("payoff")
        if summary_bits:
            summary = (summary + f" Ep {episode.episode_no}: " + ", ".join(summary_bits) + ".").strip()

        return PersonaState(
            persona_id=persona.persona_id,
            episodes_heard=state.episodes_heard + (1 if will_continue else 0),
            active=will_continue,
            dropped_at=None if will_continue else f"episode_{episode.episode_no}",
            story_summary=summary[-900:],
            unresolved_questions=unresolved,
            payoff_trust=round(payoff_trust, 4),
            agency_trust=round(agency_trust, 4),
            coins_spent=state.coins_spent + (30 if would_pay else 0),
        )


def _extract_output_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                return content["text"]
    raise RuntimeError(f"Could not find model output text in response: {json.dumps(data)[:500]}")


def _validate_reaction_payload(result: dict[str, Any]) -> None:
    missing = [key for key in REACTION_SCHEMA["required"] if key not in result]
    if missing:
        raise RuntimeError(f"Model output missing required keys: {missing}")


def _clean_decision_factors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    factors: list[str] = []
    for item in value:
        text = " ".join(str(item).split())[:180].strip()
        if text:
            factors.append(text)
    return factors[:5]


def _is_model_availability_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "model" in lowered
        and any(term in lowered for term in ["not found", "does not exist", "not exist", "unsupported"])
    ) or "invalid model" in lowered


def _empty_guardrail(reason: str) -> dict[str, Any]:
    return {
        "should_drop": False,
        "pressure": 0.0,
        "threshold": 1.0,
        "base_threshold": 1.0,
        "override_margin": 0.0,
        "beat_id": None,
        "reason": reason,
        "rank": 0.0,
        "abandon_pressure": 0.0,
        "cohort_fit": 0.0,
        "components": {},
    }
