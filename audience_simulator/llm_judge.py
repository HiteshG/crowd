from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .env import openai_api_key, openai_model_candidates
from .ingest import format_beat_map
from .models import Episode, Persona, PersonaState, REACTION_SCHEMA
from .prompting import behavioral_calibration, compact_episode_intelligence


JUDGEMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        **REACTION_SCHEMA["properties"],
        "judgement_notes": {"type": "string"},
        "changed_decision": {"type": "boolean"},
        "changed_reasoning": {"type": "boolean"},
    },
    "required": [
        *REACTION_SCHEMA["required"],
        "judgement_notes",
        "changed_decision",
        "changed_reasoning",
    ],
    "additionalProperties": False,
}


class OpenAIJudgementLayer:
    agent_name = "openai_reaction_judge_v1"

    def __init__(
        self,
        *,
        model: str = "gpt-5.6-luna",
        reasoning_effort: str = "medium",
        timeout_seconds: int = 90,
    ) -> None:
        if reasoning_effort not in {"minimal", "low", "medium", "high"}:
            raise ValueError(f"Unknown reasoning effort '{reasoning_effort}'")
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.timeout_seconds = timeout_seconds

    def judge(
        self,
        *,
        persona: Persona,
        state: PersonaState,
        episode: Episode,
        episode_intelligence: dict[str, Any] | None,
        raw_reaction: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        api_key = openai_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when using --judgement-mode llm")

        last_model_error: RuntimeError | None = None
        for candidate_model in openai_model_candidates(self.model):
            try:
                result = self._judge_once(
                    api_key=api_key,
                    model=candidate_model,
                    persona=persona,
                    state=state,
                    episode=episode,
                    episode_intelligence=episode_intelligence,
                    raw_reaction=raw_reaction,
                )
                self.model = candidate_model
                return result, judgement_meta(result, raw_reaction, self.agent_name)
            except RuntimeError as exc:
                if not _is_model_availability_error(str(exc)):
                    raise
                last_model_error = exc
        if last_model_error:
            raise last_model_error
        raise RuntimeError("No OpenAI model candidates configured")

    def _judge_once(
        self,
        *,
        api_key: str,
        model: str,
        persona: Persona,
        state: PersonaState,
        episode: Episode,
        episode_intelligence: dict[str, Any] | None,
        raw_reaction: dict[str, Any],
    ) -> dict[str, Any]:
        request_payload = {
            "model": model,
            "input": [
                {"role": "system", "content": judgement_system_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        judgement_payload(
                            persona=persona,
                            state=state,
                            episode=episode,
                            episode_intelligence=episode_intelligence,
                            raw_reaction=raw_reaction,
                        ),
                        ensure_ascii=False,
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "audience_reaction_judgement",
                    "schema": JUDGEMENT_SCHEMA,
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
            raise RuntimeError(f"Judge returned non-JSON output: {text[:500]}") from exc
        missing = [key for key in JUDGEMENT_SCHEMA["required"] if key not in result]
        if missing:
            raise RuntimeError(f"Judge output missing required keys: {missing}")
        return result


def judgement_system_prompt() -> str:
    return (
        "You are the judgement layer for an audience simulator. A persona agent has "
        "already reacted to one episode. Your job is to audit and finalize the behavioral "
        "decision with sharp emotion-to-judgement reasoning.\n\n"
        "You are not a copy editor. You are deciding whether this specific listener starts "
        "the next episode in their normal listening window. You may keep or revise the raw "
        "reaction. Do not target a quota of drops. Do not rubber-stamp weak reasoning.\n\n"
        "Decision standards:\n"
        "- Continue requires more than generic curiosity. There must be a specific next-play "
        "hook, emotional need, genre fit, payoff trust, or habit/context reason strong enough "
        "for this persona.\n"
        "- Drop is correct when emotion settles, trust erodes, the gate is weak, the episode "
        "does not serve the persona's need-region, or the listener's churn pressure beats "
        "the remaining hook.\n"
        "- Negative craving delta is a warning. If you still continue, judgement_bridge must "
        "name the exact stronger counterweight.\n"
        "- Pay requires a concrete paid promise, not just a good episode.\n"
        "- If will_continue is false, drop_beat must be one beat_id from the beat map.\n"
        "- If will_continue is true, drop_beat must be null.\n\n"
        "Return the final reaction JSON plus judgement_notes. Keep all reasons concise, "
        "grounded, and specific."
    )


def judgement_payload(
    *,
    persona: Persona,
    state: PersonaState,
    episode: Episode,
    episode_intelligence: dict[str, Any] | None,
    raw_reaction: dict[str, Any],
) -> dict[str, Any]:
    return {
        "persona": persona.__dict__,
        "listener_state_before_episode": state.__dict__,
        "episode": {
            "episode_no": episode.episode_no,
            "title": episode.title,
            "beat_map": format_beat_map(episode),
        },
        "behavioral_calibration": behavioral_calibration(persona, state, episode, episode_intelligence),
        "episode_intelligence": compact_episode_intelligence(episode_intelligence),
        "raw_persona_reaction": raw_reaction,
        "judge_task": (
            "Finalize will_continue, would_pay, drop_beat, craving, prediction, emotional_state, "
            "felt_emotion, emotion_shift, judgement_bridge, and decision_factors. Prefer a "
            "clear correction over a polite continuation when the raw reaction is inconsistent."
        ),
    }


def judgement_meta(result: dict[str, Any], raw: dict[str, Any], agent_name: str) -> dict[str, Any]:
    changed_decision = bool(result.get("changed_decision")) or any(
        result.get(key) != raw.get(key)
        for key in ["will_continue", "would_pay", "drop_beat", "craving_mid", "craving_end"]
    )
    changed_reasoning = bool(result.get("changed_reasoning")) or any(
        result.get(key) != raw.get(key)
        for key in ["continue_reason", "pay_reason", "emotional_state", "judgement_bridge"]
    )
    return {
        "agent": agent_name,
        "changed_decision": changed_decision,
        "changed_reasoning": changed_reasoning,
        "notes": str(result.get("judgement_notes", "")),
    }


def _extract_output_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                return content["text"]
    raise RuntimeError(f"Could not find model output text in response: {json.dumps(data)[:500]}")


def _is_model_availability_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "model" in lowered
        and any(term in lowered for term in ["not found", "does not exist", "not exist", "unsupported"])
    ) or "invalid model" in lowered
