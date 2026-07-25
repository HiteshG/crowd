from __future__ import annotations

import dataclasses
import hashlib
import json
import urllib.error
import urllib.request
from typing import Any, Callable

from .cohorts import INDIA_ENGLISH_COHORT_CARD
from .env import openai_api_key, openai_model_candidates
from .ingest import paragraph_blocks_with_lines
from .models import Beat, Episode


BEAT_MAP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "episode_no": {"type": "integer"},
        "episode_title": {"type": "string"},
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "purpose": {
                        "type": "string",
                        "enum": ["reveal", "escalate", "reverse", "complicate", "payoff", "none"],
                    },
                    "start_line": {"type": "integer", "minimum": 1},
                    "end_line": {"type": "integer", "minimum": 1},
                    "speaker_focus": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 4,
                    },
                    "story_function": {"type": "string"},
                    "audience_decision_risk": {
                        "type": "string",
                        "enum": [
                            "none",
                            "boredom",
                            "confusion",
                            "payoff_delay",
                            "weak_gate",
                            "tonal_break",
                            "dealbreaker",
                        ],
                    },
                    "risk_reason": {"type": "string"},
                    "evidence_quote": {"type": "string"},
                    "emotional_intensity": {"type": "integer", "minimum": 1, "maximum": 10},
                    "suspense": {"type": "integer", "minimum": 1, "maximum": 10},
                    "craving_effect": {
                        "type": "string",
                        "enum": ["raises", "holds", "lowers"],
                    },
                },
                "required": [
                    "label",
                    "purpose",
                    "start_line",
                    "end_line",
                    "speaker_focus",
                    "story_function",
                    "audience_decision_risk",
                    "risk_reason",
                    "evidence_quote",
                    "emotional_intensity",
                    "suspense",
                    "craving_effect",
                ],
                "additionalProperties": False,
            },
            "minItems": 2,
        },
    },
    "required": ["episode_no", "episode_title", "beats"],
    "additionalProperties": False,
}


ProgressCallback = Callable[[str, dict[str, Any]], None]


def generate_llm_episode_beats(
    episodes: list[Episode],
    *,
    model: str = "gpt-5.6-luna",
    seed: int = 7,
    reasoning_effort: str = "medium",
    timeout_seconds: int = 120,
    progress: ProgressCallback | None = None,
) -> list[Episode]:
    """Use an LLM to create the canonical beat map for each episode.

    The local parser still supplies episode boundaries and a rough candidate
    map, but the returned Episode objects replace parser beats with LLM-selected
    story-decision units.
    """
    if reasoning_effort not in {"minimal", "low", "medium", "high"}:
        raise ValueError(f"Unknown reasoning effort '{reasoning_effort}'")
    if not episodes:
        return []
    api_key = openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required when using LLM beat generation")

    active_model = model
    rebuilt: list[Episode] = []
    for index, episode in enumerate(episodes):
        if progress:
            progress(
                "llm_beat_episode_started",
                {"episode_no": episode.episode_no, "title": episode.title},
            )
        result, active_model = _call_beat_model(
            api_key=api_key,
            model=active_model,
            episode=episode,
            seed=_request_seed(seed, index, episode),
            reasoning_effort=reasoning_effort,
            timeout_seconds=timeout_seconds,
        )
        rebuilt_episode = dataclasses.replace(
            episode,
            beats=_beats_from_model_result(episode, result),
        )
        rebuilt.append(rebuilt_episode)
        if progress:
            progress(
                "llm_beat_episode_finished",
                {
                    "episode_no": episode.episode_no,
                    "title": episode.title,
                    "beats": len(rebuilt_episode.beats),
                    "model": active_model,
                },
            )
    return rebuilt


def _call_beat_model(
    *,
    api_key: str,
    model: str,
    episode: Episode,
    seed: int,
    reasoning_effort: str,
    timeout_seconds: int,
) -> tuple[dict[str, Any], str]:
    last_model_error: RuntimeError | None = None
    for candidate_model in openai_model_candidates(model):
        try:
            return (
                _call_beat_model_once(
                    api_key=api_key,
                    model=candidate_model,
                    episode=episode,
                    seed=seed,
                    reasoning_effort=reasoning_effort,
                    timeout_seconds=timeout_seconds,
                ),
                candidate_model,
            )
        except RuntimeError as exc:
            if not _is_model_availability_error(str(exc)):
                raise
            last_model_error = exc
    if last_model_error:
        raise last_model_error
    raise RuntimeError("No OpenAI model candidates configured")


def _call_beat_model_once(
    *,
    api_key: str,
    model: str,
    episode: Episode,
    seed: int,
    reasoning_effort: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": _beat_system_prompt()},
            {
                "role": "user",
                "content": json.dumps(_beat_prompt_payload(episode, seed), ensure_ascii=False),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "episode_beat_map",
                "schema": BEAT_MAP_SCHEMA,
                "strict": True,
            }
        },
        "reasoning": {"effort": reasoning_effort},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
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
        raise RuntimeError(f"Model returned non-JSON beat map output: {text[:500]}") from exc
    _validate_raw_beat_result(episode, result)
    return result


def _beat_system_prompt() -> str:
    cohort_card = json.dumps(INDIA_ENGLISH_COHORT_CARD, ensure_ascii=False, indent=2)
    return (
        "You are Story Intelligence Module B for serialized audio fiction.\n"
        "Your job is to segment one episode into auditable story beats before audience "
        "simulation. A beat is a contiguous script moment where listener decision state "
        "could change: a setup, reveal, escalation, reversal, complication, payoff, "
        "emotional turn, or a passage with no real story movement.\n\n"
        "Segmentation rules:\n"
        "- Use the numbered source lines exactly. Each beat must be a contiguous line range.\n"
        "- Beat ranges must be in story order and should not overlap.\n"
        "- Do not split every sentence. Merge speaker cue, parenthetical, SFX, and dialogue "
        "when they form one listener-perceived action.\n"
        "- Do split a long passage when the listener's reason to continue changes inside it.\n"
        "- Prefer 6 to 18 beats for a normal episode; go outside that range only when the "
        "script length genuinely demands it.\n"
        "- The heuristic candidate blocks in the user payload are scaffolding only. Use them "
        "to see paragraph/script structure, but override them when the story logic demands it.\n"
        "- Mark audience_decision_risk from the episode text only. Do not predict drops from "
        "generic taste; identify the specific story-side risk.\n"
        "- Do not invent characters, facts, emotions, or future episodes absent from the source.\n\n"
        "Purpose enum meanings: reveal = new consequential information; escalate = danger, "
        "stakes, humiliation, desire, or pressure increases; reverse = audience understanding "
        "or power position flips; complicate = more load/conditions without full payoff; "
        "payoff = a promise is answered or agency lands; none = filler/transition/no clear move.\n\n"
        f"Audience context:\n{cohort_card}\n\n"
        "Return only JSON matching the schema."
    )


def _beat_prompt_payload(episode: Episode, seed: int) -> dict[str, Any]:
    return {
        "task": "Create the canonical beat map for this episode before persona simulation.",
        "run_seed": seed,
        "episode_no": episode.episode_no,
        "episode_title": episode.title,
        "numbered_script": _numbered_script(episode.text),
        "heuristic_candidate_blocks": _heuristic_candidates(episode.text),
        "audit_requirements": [
            "Every evidence_quote must appear inside its line range.",
            "Risk reason must cite story mechanics, not vague quality language.",
            "If risk is none, risk_reason should explain why this beat still moves the listener forward.",
            "Use India/English audio-listener context only for risk interpretation, never for inventing plot.",
        ],
    }


def _numbered_script(text: str) -> str:
    return "\n".join(
        f"{line_no:03d}: {line}"
        for line_no, line in enumerate(text.splitlines(), start=1)
    )


def _heuristic_candidates(text: str) -> list[dict[str, Any]]:
    rows = []
    for index, (block, line_start, line_end) in enumerate(paragraph_blocks_with_lines(text), start=1):
        excerpt = " ".join(block.split())
        rows.append(
            {
                "candidate_id": f"c{index:02d}",
                "line_start": line_start,
                "line_end": line_end,
                "excerpt": excerpt[:320],
            }
        )
    return rows


def _validate_raw_beat_result(episode: Episode, result: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        raise RuntimeError("Beat map output must be a JSON object")
    if int(result.get("episode_no", -1)) != episode.episode_no:
        raise RuntimeError(
            f"Beat map episode_no mismatch: expected {episode.episode_no}, got {result.get('episode_no')}"
        )
    beats = result.get("beats")
    if not isinstance(beats, list) or not beats:
        raise RuntimeError("Beat map output must contain a non-empty beats array")


def _beats_from_model_result(episode: Episode, result: dict[str, Any]) -> list[Beat]:
    source_lines = episode.text.splitlines()
    line_count = len(source_lines)
    previous_end = 0
    rebuilt: list[Beat] = []
    for item in result["beats"]:
        start_line = int(item["start_line"])
        end_line = int(item["end_line"])
        if start_line < 1 or end_line < start_line or end_line > line_count:
            raise RuntimeError(
                f"Invalid beat range for episode {episode.episode_no}: {start_line}-{end_line}"
            )
        if start_line <= previous_end:
            raise RuntimeError(
                f"Overlapping beat range for episode {episode.episode_no}: {start_line}-{end_line}"
            )
        previous_end = end_line
        beat_text = "\n".join(source_lines[start_line - 1 : end_line]).strip()
        if not beat_text:
            raise RuntimeError(
                f"Empty beat range for episode {episode.episode_no}: {start_line}-{end_line}"
            )
        rebuilt.append(
            Beat(
                beat_id=f"s{episode.episode_no:03d}_b{len(rebuilt) + 1:02d}",
                text=beat_text,
                label=_clean_line(item["label"], max_chars=80),
                purpose=str(item["purpose"]),
                line_start=start_line,
                line_end=end_line,
                speaker_focus=tuple(_clean_speaker(value) for value in item["speaker_focus"] if str(value).strip())[:4],
                audience_decision_risk=str(item["audience_decision_risk"]),
                risk_reason=_clean_line(item["risk_reason"], max_chars=260),
                evidence_quote=_clean_line(item["evidence_quote"], max_chars=220),
                emotional_intensity=int(item["emotional_intensity"]),
                suspense=int(item["suspense"]),
                craving_effect=str(item["craving_effect"]),
                generator="llm",
            )
        )
    if len(rebuilt) < 2:
        raise RuntimeError(f"LLM beat map for episode {episode.episode_no} produced too few beats")
    return rebuilt


def _clean_line(value: Any, *, max_chars: int) -> str:
    cleaned = " ".join(str(value).replace("\n", " ").split())
    return cleaned[:max_chars].rstrip()


def _clean_speaker(value: Any) -> str:
    return _clean_line(value, max_chars=40)


def _extract_output_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                return content["text"]
    raise RuntimeError(f"Could not find model output text in response: {json.dumps(data)[:500]}")


def _request_seed(seed: int, episode_index: int, episode: Episode) -> int:
    value = f"{seed}:{episode_index}:{episode.episode_no}:{episode.title}:{episode.text[:120]}"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % 2_000_000_000


def _is_model_availability_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "model" in lowered
        and any(term in lowered for term in ["not found", "does not exist", "not exist", "unsupported"])
    )
