from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import urllib.error
import urllib.request
from typing import Any

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
        model: str = "gpt-5-mini",
        temperature: float = 0.3,
        timeout_seconds: int = 90,
    ) -> None:
        self.seed = seed
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def react(
        self,
        run_id: str,
        persona: Persona,
        state: PersonaState,
        episode: Episode,
    ) -> tuple[Reaction, PersonaState]:
        payload = build_llm_reaction_payload(persona, state, episode)
        result = self._call_model(payload, run_id, persona, episode)
        signals = episode_signals(episode)

        will_continue = bool(result["will_continue"])
        would_pay = bool(result["would_pay"]) and will_continue
        drop_beat = result.get("drop_beat")
        if not will_continue and not drop_beat:
            drop_beat = strongest_drop_beat(episode, persona)[0]

        craving_mid = int(clamp(int(result["craving_mid"]), 1, 10))
        craving_end = int(clamp(int(result["craving_end"]), 1, 10))
        engagement_score = self._engagement_score(will_continue, craving_mid, craving_end)
        pay_pressure = self._pay_pressure(would_pay, signals, craving_end)
        next_state = self._update_state(persona, state, episode, signals, will_continue, would_pay)

        reaction = Reaction(
            run_id=run_id,
            persona_id=persona.persona_id,
            cohort=self.cohort_name,
            episode_no=episode.episode_no,
            will_continue=will_continue,
            continue_reason=str(result["continue_reason"]),
            would_pay=would_pay,
            pay_reason=str(result["pay_reason"]),
            drop_beat=drop_beat,
            craving_mid=craving_mid,
            craving_end=craving_end,
            next_prediction=str(result["next_prediction"]),
            emotional_state=str(result["emotional_state"]),
            engagement_score=engagement_score,
            pay_pressure=pay_pressure,
            signal_json=signals,
            state_json=dataclasses.asdict(next_state),
        )
        return reaction, next_state

    def _call_model(
        self,
        payload: dict[str, Any],
        run_id: str,
        persona: Persona,
        episode: Episode,
    ) -> dict[str, Any]:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when using --engine llm")

        request_payload = {
            "model": self.model,
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
            "temperature": self.temperature,
            "seed": self._request_seed(run_id, persona, episode),
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
