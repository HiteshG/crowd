from __future__ import annotations

import os
from pathlib import Path


DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_OPENAI_FALLBACK_MODEL = ""
DEFAULT_OPENAI_REASONING_EFFORT = "medium"


def load_dotenv(path: Path | str = ".env") -> None:
    """Load simple KEY=VALUE pairs without adding a runtime dependency."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _unquote(value.strip())
    normalize_openai_env()


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def default_openai_model() -> str:
    return os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)


def default_reasoning_effort() -> str:
    return os.environ.get("OPENAI_REASONING_EFFORT", DEFAULT_OPENAI_REASONING_EFFORT)


def default_max_workers() -> int:
    value = os.environ.get("AUDIENCE_SIM_MAX_WORKERS", "8")
    try:
        return max(1, int(value))
    except ValueError:
        return 8


def openai_api_key() -> str | None:
    normalize_openai_env()
    return os.environ.get("OPENAI_API_KEY")


def normalize_openai_env() -> None:
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("OPEN_AI_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["OPEN_AI_KEY"]


def openai_model_candidates(model: str | None = None) -> list[str]:
    primary = model or default_openai_model()
    fallback_raw = os.environ.get("OPENAI_MODEL_FALLBACKS", DEFAULT_OPENAI_FALLBACK_MODEL)
    candidates = [primary]
    for item in fallback_raw.split(","):
        candidate = item.strip()
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates
