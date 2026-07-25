from __future__ import annotations

import dataclasses
import hashlib
import json
import urllib.error
import urllib.request
from typing import Any

from .env import openai_api_key, openai_model_candidates
from .models import Persona


PERSONA_ENRICHMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "persona_id": {"type": "string"},
                    "bio": {"type": "string"},
                    "persona": {"type": "string"},
                    "interested_topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 6,
                    },
                },
                "required": ["persona_id", "bio", "persona", "interested_topics"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def enrich_personas_with_llm(
    personas: list[Persona],
    *,
    model: str = "gpt-5.6-luna",
    seed: int = 7,
    batch_size: int = 10,
    timeout_seconds: int = 90,
    reasoning_effort: str = "medium",
) -> list[Persona]:
    """Use an LLM to rewrite persona prose while preserving numeric skeletons."""
    if not personas:
        return []
    if reasoning_effort not in {"minimal", "low", "medium", "high"}:
        raise ValueError(f"Unknown reasoning effort '{reasoning_effort}'")
    api_key = openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required when using --persona-mode llm")

    active_model = model
    enriched_by_id: dict[str, dict[str, Any]] = {}
    for batch_index, start in enumerate(range(0, len(personas), batch_size)):
        batch = personas[start : start + batch_size]
        result, active_model = _call_persona_model(
            api_key=api_key,
            model=active_model,
            batch=batch,
            seed=_request_seed(seed, batch_index, batch),
            timeout_seconds=timeout_seconds,
            reasoning_effort=reasoning_effort,
        )
        for item in result["items"]:
            enriched_by_id[str(item["persona_id"])] = item

    enriched: list[Persona] = []
    missing: list[str] = []
    for persona in personas:
        item = enriched_by_id.get(persona.persona_id)
        if item is None:
            missing.append(persona.persona_id)
            continue
        enriched.append(
            dataclasses.replace(
                persona,
                bio=_clean_line(str(item["bio"]), max_chars=180),
                persona=_clean_line(str(item["persona"]), max_chars=520),
                interested_topics=_clean_topics(item["interested_topics"], persona.interested_topics),
            )
        )
    if missing:
        raise RuntimeError(f"LLM persona enrichment missed persona ids: {missing[:5]}")
    return enriched


def _call_persona_model(
    *,
    api_key: str,
    model: str,
    batch: list[Persona],
    seed: int,
    timeout_seconds: int,
    reasoning_effort: str,
) -> tuple[dict[str, Any], str]:
    last_model_error: RuntimeError | None = None
    for candidate_model in openai_model_candidates(model):
        try:
            return (
                _call_persona_model_once(
                    api_key=api_key,
                    model=candidate_model,
                    batch=batch,
                    seed=seed,
                    timeout_seconds=timeout_seconds,
                    reasoning_effort=reasoning_effort,
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


def _call_persona_model_once(
    *,
    api_key: str,
    model: str,
    batch: list[Persona],
    seed: int,
    timeout_seconds: int,
    reasoning_effort: str,
) -> dict[str, Any]:
    request_payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You generate realistic, auditable Indian English/Hinglish audio-fiction "
                    "listener personas for a Pocket-FM-style audience simulator. Rewrite only "
                    "bio, persona, and interested_topics. Preserve persona_id. Do not change or "
                    "contradict the structured skeleton. Keep every bio one sentence and every "
                    "persona one compact paragraph. Avoid caricature, census stereotypes, and "
                    "generic marketing language."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(_persona_prompt_payload(batch), ensure_ascii=False),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "persona_enrichment",
                "schema": PERSONA_ENRICHMENT_SCHEMA,
                "strict": True,
            }
        },
        "reasoning": {"effort": reasoning_effort},
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
        raise RuntimeError(f"Model returned non-JSON persona output: {text[:500]}") from exc
    _validate_persona_enrichment(result, batch)
    return result


def _persona_prompt_payload(batch: list[Persona]) -> dict[str, Any]:
    return {
        "task": (
            "For each skeleton, return persona_id, bio, persona, interested_topics. Make the "
            "listener feel specific to Indian English audio-fiction usage: commute, chores, "
            "student breaks, late-night listening, city tier, language register, privacy, "
            "payment habit, discovery path, and story cravings. Do not modify numeric values."
        ),
        "style_rules": [
            "bio: one sentence, under 22 words, no hashtags.",
            "persona: one paragraph, under 75 words, names the listener and explains why they stay or churn.",
            "interested_topics: 3 to 6 short strings useful for story targeting.",
            "Use light Hinglish only when the skeleton language/register supports it.",
        ],
        "skeletons": [_skeleton(persona) for persona in batch],
    }


def _skeleton(persona: Persona) -> dict[str, Any]:
    return {
        "persona_id": persona.persona_id,
        "realname": persona.realname,
        "age": persona.age,
        "gender": persona.gender,
        "city": persona.city,
        "city_tier": persona.city_tier,
        "profession": persona.profession,
        "mbti": persona.mbti,
        "cohort_label": persona.cohort_label,
        "region_label": persona.region_label,
        "listening_context": persona.listening_context,
        "language_preference": persona.language_preference,
        "language_register": persona.language_register,
        "avg_daily_minutes": persona.avg_daily_minutes,
        "session_minutes": persona.session_minutes,
        "session_pattern": persona.session_pattern,
        "coin_spend_tier": persona.coin_spend_tier,
        "discovery_channel": persona.discovery_channel,
        "listening_privacy": persona.listening_privacy,
        "interruption_load": persona.interruption_load,
        "primary_drivers": persona.primary_drivers,
        "drivers": persona.drivers,
        "top_genres": _top_genres(persona.genre_affinity),
        "narrative_patience": persona.narrative_patience,
        "churn_sensitivity": persona.churn_sensitivity,
        "pay_threshold": persona.pay_threshold,
        "anti_stereotype": persona.anti_stereotype,
        "base_bio": persona.bio,
        "base_persona": persona.persona,
        "base_interested_topics": persona.interested_topics,
    }


def _top_genres(genre_affinity: dict[str, float], limit: int = 4) -> list[str]:
    return [
        genre
        for genre, _score in sorted(
            genre_affinity.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]
    ]


def _validate_persona_enrichment(result: dict[str, Any], batch: list[Persona]) -> None:
    if not isinstance(result, dict) or not isinstance(result.get("items"), list):
        raise RuntimeError("Model output must contain an items array")
    expected_ids = {persona.persona_id for persona in batch}
    seen_ids: set[str] = set()
    for item in result["items"]:
        if not isinstance(item, dict):
            raise RuntimeError("Each persona enrichment item must be an object")
        persona_id = str(item.get("persona_id", ""))
        if persona_id not in expected_ids:
            raise RuntimeError(f"Unexpected persona_id in LLM persona output: {persona_id}")
        seen_ids.add(persona_id)
        if not str(item.get("bio", "")).strip():
            raise RuntimeError(f"Missing bio for {persona_id}")
        if not str(item.get("persona", "")).strip():
            raise RuntimeError(f"Missing persona for {persona_id}")
        topics = item.get("interested_topics")
        if not isinstance(topics, list) or not all(isinstance(topic, str) for topic in topics):
            raise RuntimeError(f"Invalid interested_topics for {persona_id}")
    missing = expected_ids - seen_ids
    if missing:
        raise RuntimeError(f"LLM persona enrichment omitted ids: {sorted(missing)[:5]}")


def _clean_line(value: str, *, max_chars: int) -> str:
    cleaned = " ".join(value.replace("\n", " ").split())
    return cleaned[:max_chars].rstrip()


def _clean_topics(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    topics: list[str] = []
    seen: set[str] = set()
    for raw_topic in value:
        topic = " ".join(str(raw_topic).split())[:60].strip()
        key = topic.lower()
        if topic and key not in seen:
            seen.add(key)
            topics.append(topic)
    return topics[:6] or fallback


def _extract_output_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                return content["text"]
    raise RuntimeError(f"Could not find model output text in response: {json.dumps(data)[:500]}")


def _request_seed(seed: int, batch_index: int, batch: list[Persona]) -> int:
    ids = ",".join(persona.persona_id for persona in batch)
    digest = hashlib.sha256(f"{seed}:{batch_index}:{ids}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % 2_000_000_000


def _is_model_availability_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "model" in lowered
        and any(term in lowered for term in ["not found", "does not exist", "not exist", "unsupported"])
    ) or "invalid model" in lowered
