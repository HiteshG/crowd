from __future__ import annotations

import json
import math
import random
import re
from typing import Any


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def pct(value: float) -> str:
    return f"{value * 100:5.1f}%"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def weighted_choice(rng: random.Random, items: list[tuple[Any, float]]) -> Any:
    total = sum(weight for _, weight in items)
    point = rng.random() * total
    cursor = 0.0
    for item, weight in items:
        cursor += weight
        if point <= cursor:
            return item
    return items[-1][0]


def bounded_gauss(
    rng: random.Random,
    mean: float,
    stdev: float,
    low: float,
    high: float,
) -> float:
    return clamp(rng.gauss(mean, stdev), low, high)


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def entropy(values: list[str]) -> float:
    if not values:
        return 0.0
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    total = len(values)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())

