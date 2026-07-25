from __future__ import annotations

import math
import re

from .models import Beat, Episode, Persona
from .utils import clamp, word_count


KEYWORDS: dict[str, list[str]] = {
    "ambition": [
        "career",
        "office",
        "startup",
        "founder",
        "promotion",
        "interview",
        "pitch",
        "investor",
        "client",
        "campus",
        "mba",
        "product",
        "manager",
        "deal",
        "contract",
        "presentation",
        "deadline",
        "equity",
        "board",
        "press",
    ],
    "competence": [
        "solved",
        "outperformed",
        "cracked",
        "built",
        "coded",
        "strategy",
        "planned",
        "negotiated",
        "proved",
        "earned",
        "evidence",
        "audit",
        "data",
        "numbers",
        "design",
        "led",
        "won",
        "fixed",
        "logs",
        "commit",
        "lawyer",
        "warrant",
        "destroy",
        "blocked",
        "tracked",
        "searched",
    ],
    "urban_modern": [
        "bangalore",
        "mumbai",
        "delhi",
        "gurgaon",
        "pune",
        "hyderabad",
        "metro",
        "app",
        "coffee",
        "co-working",
        "coworking",
        "office",
        "startup",
        "apartment",
        "gym",
        "cab",
        "dashboard",
    ],
    "romance": [
        "love",
        "crush",
        "date",
        "kiss",
        "chemistry",
        "boyfriend",
        "girlfriend",
        "fiance",
        "fiancee",
        "wedding",
        "confession",
        "almost touched",
        "held her hand",
        "held his hand",
        "standing too close",
    ],
    "family": [
        "mother",
        "father",
        "parents",
        "family",
        "household",
        "uncle",
        "aunt",
        "cousin",
        "marriage",
        "shaadi",
        "rishta",
        "in-laws",
        "tradition",
        "home",
        "ma",
        "daughter",
        "brother",
    ],
    "humiliation": [
        "humiliated",
        "insulted",
        "mocked",
        "fired",
        "rejected",
        "laughed",
        "viral",
        "betrayed",
        "cheated",
        "slapped",
        "publicly",
        "shamed",
        "quota hire",
    ],
    "vindication": [
        "applause",
        "promoted",
        "accepted",
        "won",
        "revealed",
        "truth",
        "evidence",
        "public",
        "boardroom",
        "courtroom",
        "exposed",
        "apologized",
        "respect",
        "cleared",
        "proved",
    ],
    "status": [
        "status",
        "reputation",
        "rank",
        "elite",
        "vip",
        "heir",
        "rich",
        "wealth",
        "promotion",
        "followers",
        "viral",
        "founder",
        "ceo",
        "power",
        "equity",
        "board",
        "ownership",
    ],
    "agency": [
        "decided",
        "chose",
        "refused",
        "confronted",
        "negotiated",
        "planned",
        "promised",
        "walked out",
        "challenged",
        "signed",
        "sent",
        "pack",
        "destroy",
        "block",
        "stop them",
        "get the largest knife",
        "told him",
        "told her",
        "replies",
        "demands",
        "reveals",
    ],
    "passive": [
        "waited",
        "cried",
        "obeyed",
        "begged",
        "silent",
        "helpless",
        "rescued by",
        "could do nothing",
        "endured",
        "accepted quietly",
        "stays quiet",
    ],
    "regressive": [
        "obey your husband",
        "family honour",
        "family honor",
        "a girl's place",
        "leave your job",
        "quit your job",
        "good daughter-in-law",
        "sanskaar",
        "izzat",
        "permission to work",
    ],
    "cliffhanger": [
        "suddenly",
        "just then",
        "phone rang",
        "message arrived",
        "door opened",
        "secret",
        "unknown number",
        "blood",
        "body",
        "dead",
        "knife",
        "wail",
        "scream",
        "police",
        "inspector",
        "warrant",
        "search warrant",
        "sim card",
        "gps",
        "tracked",
        "digging",
        "compost pit",
        "found him",
        "found her",
        "muffled buzzing",
        "knock",
        "knocks",
        "open the door",
        "to be continued",
        "what she saw",
        "what he saw",
        "before she could answer",
        "before he could answer",
        "calendar invite",
        "forwarded a photo",
        "headline",
    ],
    "hinglish": [
        "yaar",
        "arre",
        "bhai",
        "didi",
        "shaadi",
        "rishta",
        "jugaad",
        "scene",
        "faltu",
        "paisa",
        "boss",
        "matlab",
    ],
    "filler": [
        "recap",
        "remembered again",
        "thought again",
        "for a long time",
        "nothing happened",
        "silence stretched",
        "same argument",
        "as before",
    ],
    "exposition": [
        "explained",
        "history",
        "backstory",
        "years ago",
        "the system was",
        "the rules were",
        "as everyone knew",
        "lecture",
    ],
}


def term_hits(text: str, terms: list[str]) -> int:
    lower = text.lower()
    hits = 0
    for term in terms:
        lowered = term.lower()
        if " " in lowered:
            hits += lower.count(lowered)
        else:
            hits += len(re.findall(rf"\b{re.escape(lowered)}\b", lower))
    return hits


def term_score(text: str, terms: list[str], scale: float = 5.0) -> float:
    hits = term_hits(text, terms)
    words = max(1, word_count(text))
    length_adjustment = clamp(math.sqrt(words) / 28.0, 0.55, 1.4)
    return clamp(hits / (scale * length_adjustment), 0.0, 1.0)


def episode_signals(episode: Episode) -> dict[str, float]:
    text = episode.text
    scores = {name: term_score(text, terms) for name, terms in KEYWORDS.items()}
    last_beat = episode.beats[-1] if episode.beats else None
    last_text = last_beat.text if last_beat else episode.text
    scores["ending_cliffhanger"] = term_score(last_text, KEYWORDS["cliffhanger"], scale=2.0)
    scores["ending_status_reveal"] = max(
        term_score(last_text, KEYWORDS["status"], scale=2.2),
        term_score(last_text, ["revealed", "truth", "heir", "promotion", "equity"], scale=2.0),
    )
    scores["ending_romance_pressure"] = term_score(last_text, KEYWORDS["romance"], scale=2.2)
    scores["public_vindication"] = max(
        scores["vindication"],
        term_score(text, ["boardroom", "public", "viral", "press", "all-hands"], scale=3.5),
    )
    scores["agency_gap"] = clamp(scores["passive"] - scores["agency"] * 0.65, 0.0, 1.0)
    scores["family_only"] = clamp(
        scores["family"] - max(scores["ambition"], scores["competence"], scores["urban_modern"]) * 0.55,
        0.0,
        1.0,
    )
    event_density = (
        scores["ambition"]
        + scores["competence"]
        + scores["romance"]
        + scores["humiliation"]
        + scores["vindication"]
        + scores["status"]
        + scores["agency"]
        + scores["cliffhanger"]
    ) / 4.5
    scores["event_density"] = clamp(event_density, 0.0, 1.0)
    if (
        last_beat
        and last_beat.generator == "llm"
        and last_beat.audience_decision_risk in {"weak_gate", "tonal_break"}
        and last_beat.craving_effect in {"holds", "lowers"}
    ):
        scores["ending_cliffhanger"] = min(scores["ending_cliffhanger"], 0.08)
    scores["resolved_no_hook"] = 1.0 if scores["ending_cliffhanger"] < 0.10 and scores["event_density"] > 0.45 else 0.0
    if (
        last_beat
        and last_beat.generator == "llm"
        and last_beat.audience_decision_risk in {"weak_gate", "tonal_break"}
        and last_beat.craving_effect in {"holds", "lowers"}
    ):
        scores["resolved_no_hook"] = max(scores["resolved_no_hook"], 0.75)
    scores["exposition_load"] = clamp(
        scores["exposition"] + (0.25 if word_count(text) > 1800 and event_density < 0.30 else 0.0),
        0.0,
        1.0,
    )
    return {key: round(value, 4) for key, value in scores.items()}


def beat_risk(beat: Beat, persona: Persona) -> float:
    scores = {name: term_score(beat.text, terms, scale=2.0) for name, terms in KEYWORDS.items()}
    family_crowd = clamp(scores["family"] - max(scores["ambition"], scores["competence"]) * 0.5, 0.0, 1.0)
    local_event = (
        scores["ambition"]
        + scores["competence"]
        + scores["humiliation"]
        + scores["vindication"]
        + scores["status"]
        + scores["agency"]
        + scores["cliffhanger"]
    )
    no_event = 0.30 if word_count(beat.text) > 70 and local_event < 0.40 else 0.0
    risk = (
        0.28 * scores["filler"]
        + 0.24 * scores["passive"]
        + 0.20 * scores["regressive"]
        + 0.18 * scores["exposition"]
        + 0.18 * family_crowd
        + no_event
    )
    if persona.region_id in {"household_catharsis_devotees", "slow_burn_comfort_seekers"}:
        risk -= 0.14 * family_crowd
    if persona.anti_stereotype == "ambition_required":
        risk += 0.18 * scores["passive"]
    if persona.anti_stereotype != "family_bridge":
        risk += 0.10 * family_crowd
    return clamp(risk, 0.0, 1.0)


def strongest_drop_beat(episode: Episode, persona: Persona) -> tuple[str | None, float]:
    if not episode.beats:
        return None, 0.0
    ranked = sorted(
        ((beat.beat_id, beat_risk(beat, persona)) for beat in episode.beats),
        key=lambda item: item[1],
        reverse=True,
    )
    return ranked[0]
