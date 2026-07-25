from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from .models import Persona, PersonaState
from .utils import bounded_gauss, clamp, weighted_choice


INDIA_ENGLISH_COHORT_NAME = "India/English Pocket-FM Listener Panel"

MBTI_TYPES = [
    "ISTJ",
    "ISFJ",
    "INFJ",
    "INTJ",
    "ISTP",
    "ISFP",
    "INFP",
    "INTP",
    "ESTP",
    "ESFP",
    "ENFP",
    "ENTP",
    "ESTJ",
    "ESFJ",
    "ENFJ",
    "ENTJ",
]

MBTI_WEIGHTS = [
    0.12625,
    0.11625,
    0.02125,
    0.03125,
    0.05125,
    0.07125,
    0.04625,
    0.04125,
    0.04625,
    0.06625,
    0.07125,
    0.03625,
    0.10125,
    0.11125,
    0.03125,
    0.03125,
]


@dataclass(frozen=True)
class ListenerSeed:
    seed_id: str
    label: str
    weight: float
    context: str
    session_pattern: str
    age: tuple[float, float, int, int]
    gender_mix: list[tuple[str, float]]
    city_tier_mix: list[tuple[int, float]]
    profession_mix: list[tuple[str, float]]
    avg_daily_minutes: tuple[float, float, int, int]
    session_minutes: tuple[float, float, int, int]
    gap_hours: tuple[float, float, int, int]
    payment_mix: list[tuple[str, float]]
    churn: tuple[float, float, float, float]
    completion: tuple[float, float, float, float]
    tenure_months: tuple[float, float, int, int]
    playback_speed_mix: list[tuple[float, float]]
    privacy: str
    interruption_load: str
    discovery_mix: list[tuple[str, float]]
    region_mix: list[tuple[str, float]]
    genre_base: dict[str, float]


@dataclass(frozen=True)
class NeedRegion:
    region_id: str
    label: str
    drivers: dict[str, str]
    patience: tuple[float, float, float, float]
    commitment_mix: list[tuple[int, float]]
    exploration: tuple[float, float, float, float]
    pay_shift: float
    genre_boost: dict[str, float]
    anti_stereotype: str
    need_summary: str
    topics: list[str]


INDIA_ENGLISH_COHORT_CARD: dict[str, Any] = {
    "name": INDIA_ENGLISH_COHORT_NAME,
    "market": "India, English/Hinglish, Pocket-FM-style serialized audio fiction",
    "model": "Auditable seed mix: listening occasion x story need-region x MBTI voice layer",
    "source_basis": [
        "Pocket FM India 2025 public insights: youth-heavy, long daily listening, multitasking, social discovery, micro-payments.",
        "Pocket FM app surface: romance, drama, fantasy/sci-fi, horror and thriller are core binge genres.",
        "Local pocket repo pattern: sample listener occasion separately from story need-region.",
    ],
    "drivers": [
        "identity",
        "wish_fulfillment",
        "escapism",
        "justice_seeking",
        "comfort",
        "power_fantasy",
        "belonging",
    ],
    "retention_hooks": [
        "early emotional injury with a clear revenge or justice promise",
        "competence wins and public vindication",
        "romance pressure with secrets, status gaps, or forced proximity",
        "high-frequency cliffhangers and unanswered identity/status reveals",
        "clear English/Hinglish voice that does not feel translated",
    ],
    "drop_triggers": [
        "slow setup without a promise of payoff",
        "too many names, timelines, or lore rules for multitasking listeners",
        "passive protagonist after the hook",
        "paywall after a resolved ending",
        "expensive coin ask before character attachment is strong",
    ],
    "pay_triggers": [
        "gate before revenge, confession, rescue, or status reveal",
        "gate after a public humiliation or betrayal",
        "gate when the listener already trusts the story to pay off promises",
    ],
}


CITIES_BY_TIER = {
    1: [
        "Bengaluru",
        "Mumbai",
        "Delhi NCR",
        "Hyderabad",
        "Pune",
        "Chennai",
        "Gurugram",
        "Noida",
        "Kolkata",
    ],
    2: [
        "Ahmedabad",
        "Jaipur",
        "Chandigarh",
        "Indore",
        "Kochi",
        "Coimbatore",
        "Bhubaneswar",
        "Vizag",
        "Mysuru",
        "Lucknow",
    ],
}

FIRST_NAMES = [
    "Aarav",
    "Aditi",
    "Akash",
    "Ananya",
    "Arjun",
    "Avni",
    "Diya",
    "Ishaan",
    "Kabir",
    "Kavya",
    "Meera",
    "Naina",
    "Neha",
    "Rhea",
    "Rohan",
    "Sanya",
    "Tara",
    "Ved",
    "Zoya",
]

FIRST_NAMES_BY_GENDER = {
    "female": [
        "Aditi",
        "Ananya",
        "Avni",
        "Diya",
        "Kavya",
        "Meera",
        "Naina",
        "Neha",
        "Rhea",
        "Sanya",
        "Tara",
        "Zoya",
    ],
    "male": [
        "Aarav",
        "Akash",
        "Arjun",
        "Ishaan",
        "Kabir",
        "Rohan",
        "Ved",
    ],
    "nonbinary": FIRST_NAMES,
}

LAST_NAMES = [
    "Bose",
    "Chopra",
    "Iyer",
    "Kapoor",
    "Khanna",
    "Mehta",
    "Menon",
    "Nair",
    "Rao",
    "Roy",
    "Shah",
    "Singh",
    "Verma",
]

LANGUAGE_MIX = [
    (["English", "Hinglish"], 0.50),
    (["English", "Hindi", "Hinglish"], 0.23),
    (["English", "Tamil"], 0.07),
    (["English", "Telugu"], 0.07),
    (["English", "Malayalam"], 0.05),
    (["English", "Bengali"], 0.04),
    (["English", "Kannada"], 0.04),
]

REGISTER_MIX = [
    ("urban English", 0.38),
    ("Hinglish", 0.32),
    ("polished English", 0.18),
    ("pulp-English", 0.12),
]

PAY_THRESHOLD_BY_TIER = {
    "free": 0.72,
    "light": 0.60,
    "occasional": 0.50,
    "regular": 0.38,
    "heavy": 0.28,
}

DRIVER_VALUE = {
    "low": 0.28,
    "medium": 0.52,
    "high": 0.74,
    "very_high": 0.88,
}

ENGINE_DRIVER_KEYS = [
    "identity",
    "wish_fulfillment",
    "escapism",
    "justice_seeking",
    "comfort",
]

GENRE_NAMES = {
    "modern_romance": "modern romance",
    "office_drama": "office drama",
    "revenge": "revenge thriller",
    "system_progression": "power progression",
    "family_drama": "family drama",
    "dark_romance": "dark romance",
    "urban_fantasy": "urban fantasy",
    "crime_mystery": "crime mystery",
    "horror": "horror",
    "fantasy_sci_fi": "fantasy and sci-fi",
}


LISTENER_SEEDS = [
    ListenerSeed(
        seed_id="metro_commuter_english",
        label="Metro commuter, cab or metro rail",
        weight=0.17,
        context="commute",
        session_pattern="binge",
        age=(29, 5, 20, 44),
        gender_mix=[("female", 0.48), ("male", 0.50), ("nonbinary", 0.02)],
        city_tier_mix=[(1, 0.86), (2, 0.14)],
        profession_mix=[
            ("software engineer", 0.20),
            ("marketing manager", 0.16),
            ("data analyst", 0.15),
            ("consultant", 0.14),
            ("banking associate", 0.12),
            ("product designer", 0.10),
            ("sales executive", 0.08),
            ("founder", 0.05),
        ],
        avg_daily_minutes=(100, 34, 25, 260),
        session_minutes=(52, 16, 15, 120),
        gap_hours=(12, 5, 3, 36),
        payment_mix=[("free", 0.32), ("light", 0.22), ("occasional", 0.25), ("regular", 0.16), ("heavy", 0.05)],
        churn=(0.62, 0.13, 0.30, 0.90),
        completion=(0.58, 0.17, 0.18, 0.92),
        tenure_months=(8, 7, 1, 42),
        playback_speed_mix=[(1.0, 0.39), (1.25, 0.35), (1.5, 0.23), (2.0, 0.03)],
        privacy="private_headphones",
        interruption_load="medium",
        discovery_mix=[("social_short_clip", 0.43), ("in_app_recommendation", 0.29), ("friend", 0.16), ("browsing", 0.12)],
        region_mix=[
            ("tier1_aspirational_escapists", 0.28),
            ("slow_burn_comfort_seekers", 0.21),
            ("justice_payoff_bingers", 0.18),
            ("high_churn_thrill_chasers", 0.14),
            ("status_progression_loyalists", 0.12),
            ("household_catharsis_devotees", 0.07),
        ],
        genre_base={
            "modern_romance": 0.68,
            "office_drama": 0.62,
            "revenge": 0.50,
            "system_progression": 0.44,
            "family_drama": 0.34,
            "dark_romance": 0.56,
            "urban_fantasy": 0.42,
            "crime_mystery": 0.58,
            "horror": 0.34,
            "fantasy_sci_fi": 0.42,
        },
    ),
    ListenerSeed(
        seed_id="student_english_binger",
        label="English-medium student, binge between classes",
        weight=0.17,
        context="study break",
        session_pattern="binge",
        age=(21, 3, 18, 27),
        gender_mix=[("female", 0.50), ("male", 0.48), ("nonbinary", 0.02)],
        city_tier_mix=[(1, 0.45), (2, 0.55)],
        profession_mix=[
            ("college student", 0.36),
            ("MBA student", 0.18),
            ("engineering student", 0.18),
            ("law student", 0.10),
            ("media student", 0.09),
            ("exam aspirant", 0.09),
        ],
        avg_daily_minutes=(92, 42, 20, 300),
        session_minutes=(38, 18, 10, 120),
        gap_hours=(10, 6, 2, 48),
        payment_mix=[("free", 0.52), ("light", 0.24), ("occasional", 0.16), ("regular", 0.07), ("heavy", 0.01)],
        churn=(0.70, 0.14, 0.34, 0.96),
        completion=(0.46, 0.18, 0.08, 0.86),
        tenure_months=(5, 5, 1, 30),
        playback_speed_mix=[(1.0, 0.34), (1.25, 0.37), (1.5, 0.25), (2.0, 0.04)],
        privacy="earbuds_shared_spaces",
        interruption_load="high",
        discovery_mix=[("social_short_clip", 0.55), ("friend", 0.18), ("in_app_recommendation", 0.17), ("browsing", 0.10)],
        region_mix=[
            ("high_churn_thrill_chasers", 0.25),
            ("slow_burn_comfort_seekers", 0.22),
            ("status_progression_loyalists", 0.20),
            ("tier1_aspirational_escapists", 0.17),
            ("justice_payoff_bingers", 0.11),
            ("household_catharsis_devotees", 0.05),
        ],
        genre_base={
            "modern_romance": 0.62,
            "office_drama": 0.42,
            "revenge": 0.54,
            "system_progression": 0.58,
            "family_drama": 0.32,
            "dark_romance": 0.58,
            "urban_fantasy": 0.58,
            "crime_mystery": 0.48,
            "horror": 0.44,
            "fantasy_sci_fi": 0.58,
        },
    ),
    ListenerSeed(
        seed_id="wfh_chores_multitasker",
        label="WFH or chores multitasker",
        weight=0.13,
        context="chores or low-focus work",
        session_pattern="drip",
        age=(31, 6, 22, 48),
        gender_mix=[("female", 0.58), ("male", 0.40), ("nonbinary", 0.02)],
        city_tier_mix=[(1, 0.55), (2, 0.45)],
        profession_mix=[
            ("remote support specialist", 0.15),
            ("content marketer", 0.13),
            ("operations associate", 0.13),
            ("teacher", 0.12),
            ("designer", 0.10),
            ("HR manager", 0.10),
            ("small business owner", 0.10),
            ("creator economy freelancer", 0.09),
            ("homemaker", 0.08),
        ],
        avg_daily_minutes=(78, 36, 15, 240),
        session_minutes=(30, 15, 8, 110),
        gap_hours=(22, 9, 4, 72),
        payment_mix=[("free", 0.40), ("light", 0.25), ("occasional", 0.21), ("regular", 0.11), ("heavy", 0.03)],
        churn=(0.68, 0.13, 0.35, 0.94),
        completion=(0.50, 0.17, 0.10, 0.88),
        tenure_months=(8, 7, 1, 44),
        playback_speed_mix=[(1.0, 0.50), (1.25, 0.30), (1.5, 0.18), (2.0, 0.02)],
        privacy="speaker_or_one_earbud",
        interruption_load="high",
        discovery_mix=[("in_app_recommendation", 0.36), ("social_short_clip", 0.34), ("friend", 0.17), ("browsing", 0.13)],
        region_mix=[
            ("slow_burn_comfort_seekers", 0.32),
            ("tier1_aspirational_escapists", 0.21),
            ("household_catharsis_devotees", 0.16),
            ("justice_payoff_bingers", 0.14),
            ("high_churn_thrill_chasers", 0.11),
            ("status_progression_loyalists", 0.06),
        ],
        genre_base={
            "modern_romance": 0.64,
            "office_drama": 0.48,
            "revenge": 0.42,
            "system_progression": 0.38,
            "family_drama": 0.50,
            "dark_romance": 0.48,
            "urban_fantasy": 0.38,
            "crime_mystery": 0.46,
            "horror": 0.30,
            "fantasy_sci_fi": 0.36,
        },
    ),
    ListenerSeed(
        seed_id="night_romance_binger",
        label="Late-night private binger",
        weight=0.14,
        context="late-night unwind",
        session_pattern="binge",
        age=(28, 5, 19, 42),
        gender_mix=[("female", 0.62), ("male", 0.36), ("nonbinary", 0.02)],
        city_tier_mix=[(1, 0.45), (2, 0.55)],
        profession_mix=[
            ("customer success manager", 0.14),
            ("nurse", 0.11),
            ("teacher", 0.11),
            ("copywriter", 0.10),
            ("college student", 0.10),
            ("sales executive", 0.10),
            ("software tester", 0.10),
            ("entrepreneur", 0.09),
            ("designer", 0.08),
            ("banking associate", 0.07),
        ],
        avg_daily_minutes=(118, 46, 30, 320),
        session_minutes=(62, 22, 15, 170),
        gap_hours=(18, 8, 4, 72),
        payment_mix=[("free", 0.31), ("light", 0.23), ("occasional", 0.25), ("regular", 0.16), ("heavy", 0.05)],
        churn=(0.58, 0.15, 0.24, 0.90),
        completion=(0.64, 0.16, 0.20, 0.95),
        tenure_months=(10, 9, 1, 52),
        playback_speed_mix=[(1.0, 0.52), (1.25, 0.29), (1.5, 0.17), (2.0, 0.02)],
        privacy="private_headphones",
        interruption_load="low",
        discovery_mix=[("social_short_clip", 0.48), ("in_app_recommendation", 0.28), ("browsing", 0.15), ("friend", 0.09)],
        region_mix=[
            ("slow_burn_comfort_seekers", 0.28),
            ("high_churn_thrill_chasers", 0.23),
            ("tier1_aspirational_escapists", 0.18),
            ("justice_payoff_bingers", 0.13),
            ("status_progression_loyalists", 0.10),
            ("household_catharsis_devotees", 0.08),
        ],
        genre_base={
            "modern_romance": 0.78,
            "office_drama": 0.46,
            "revenge": 0.52,
            "system_progression": 0.42,
            "family_drama": 0.42,
            "dark_romance": 0.72,
            "urban_fantasy": 0.50,
            "crime_mystery": 0.44,
            "horror": 0.36,
            "fantasy_sci_fi": 0.48,
        },
    ),
    ListenerSeed(
        seed_id="self_employed_workday",
        label="Self-employed workday listener",
        weight=0.12,
        context="shop, deliveries, or business admin",
        session_pattern="drip",
        age=(32, 7, 22, 50),
        gender_mix=[("female", 0.40), ("male", 0.58), ("nonbinary", 0.02)],
        city_tier_mix=[(1, 0.30), (2, 0.70)],
        profession_mix=[
            ("small business owner", 0.24),
            ("D2C seller", 0.14),
            ("real estate broker", 0.12),
            ("delivery fleet coordinator", 0.11),
            ("beauty salon owner", 0.10),
            ("retail manager", 0.10),
            ("insurance advisor", 0.10),
            ("creator economy freelancer", 0.09),
        ],
        avg_daily_minutes=(94, 40, 20, 280),
        session_minutes=(34, 18, 8, 125),
        gap_hours=(14, 8, 3, 72),
        payment_mix=[("free", 0.38), ("light", 0.23), ("occasional", 0.22), ("regular", 0.13), ("heavy", 0.04)],
        churn=(0.64, 0.14, 0.30, 0.92),
        completion=(0.55, 0.18, 0.12, 0.90),
        tenure_months=(7, 7, 1, 44),
        playback_speed_mix=[(1.0, 0.46), (1.25, 0.31), (1.5, 0.20), (2.0, 0.03)],
        privacy="phone_speaker_or_earbuds",
        interruption_load="high",
        discovery_mix=[("social_short_clip", 0.46), ("friend", 0.20), ("in_app_recommendation", 0.22), ("browsing", 0.12)],
        region_mix=[
            ("justice_payoff_bingers", 0.26),
            ("status_progression_loyalists", 0.22),
            ("high_churn_thrill_chasers", 0.18),
            ("tier1_aspirational_escapists", 0.15),
            ("slow_burn_comfort_seekers", 0.12),
            ("household_catharsis_devotees", 0.07),
        ],
        genre_base={
            "modern_romance": 0.50,
            "office_drama": 0.52,
            "revenge": 0.66,
            "system_progression": 0.58,
            "family_drama": 0.38,
            "dark_romance": 0.44,
            "urban_fantasy": 0.42,
            "crime_mystery": 0.60,
            "horror": 0.34,
            "fantasy_sci_fi": 0.42,
        },
    ),
    ListenerSeed(
        seed_id="office_break_listener",
        label="Salaried office break listener",
        weight=0.10,
        context="work breaks",
        session_pattern="drip",
        age=(30, 5, 22, 44),
        gender_mix=[("female", 0.46), ("male", 0.52), ("nonbinary", 0.02)],
        city_tier_mix=[(1, 0.75), (2, 0.25)],
        profession_mix=[
            ("financial analyst", 0.17),
            ("project manager", 0.16),
            ("HR associate", 0.13),
            ("software developer", 0.13),
            ("inside sales manager", 0.12),
            ("lawyer", 0.10),
            ("operations manager", 0.10),
            ("account executive", 0.09),
        ],
        avg_daily_minutes=(64, 26, 12, 170),
        session_minutes=(22, 10, 6, 70),
        gap_hours=(18, 8, 4, 72),
        payment_mix=[("free", 0.34), ("light", 0.23), ("occasional", 0.25), ("regular", 0.14), ("heavy", 0.04)],
        churn=(0.66, 0.13, 0.32, 0.92),
        completion=(0.50, 0.16, 0.12, 0.88),
        tenure_months=(8, 7, 1, 44),
        playback_speed_mix=[(1.0, 0.36), (1.25, 0.38), (1.5, 0.23), (2.0, 0.03)],
        privacy="private_headphones",
        interruption_load="medium",
        discovery_mix=[("in_app_recommendation", 0.38), ("social_short_clip", 0.34), ("browsing", 0.16), ("friend", 0.12)],
        region_mix=[
            ("tier1_aspirational_escapists", 0.30),
            ("justice_payoff_bingers", 0.20),
            ("status_progression_loyalists", 0.16),
            ("slow_burn_comfort_seekers", 0.15),
            ("high_churn_thrill_chasers", 0.13),
            ("household_catharsis_devotees", 0.06),
        ],
        genre_base={
            "modern_romance": 0.58,
            "office_drama": 0.68,
            "revenge": 0.54,
            "system_progression": 0.50,
            "family_drama": 0.30,
            "dark_romance": 0.48,
            "urban_fantasy": 0.38,
            "crime_mystery": 0.58,
            "horror": 0.30,
            "fantasy_sci_fi": 0.36,
        },
    ),
    ListenerSeed(
        seed_id="household_evening_listener",
        label="Evening household listener",
        weight=0.07,
        context="cooking, family downtime, or bedtime",
        session_pattern="drip",
        age=(38, 8, 26, 58),
        gender_mix=[("female", 0.66), ("male", 0.33), ("nonbinary", 0.01)],
        city_tier_mix=[(1, 0.35), (2, 0.65)],
        profession_mix=[
            ("homemaker", 0.28),
            ("teacher", 0.17),
            ("boutique owner", 0.12),
            ("school administrator", 0.10),
            ("banking associate", 0.10),
            ("small business owner", 0.10),
            ("nurse", 0.08),
            ("consultant", 0.05),
        ],
        avg_daily_minutes=(72, 30, 15, 210),
        session_minutes=(30, 14, 8, 100),
        gap_hours=(24, 10, 4, 96),
        payment_mix=[("free", 0.44), ("light", 0.25), ("occasional", 0.19), ("regular", 0.10), ("heavy", 0.02)],
        churn=(0.58, 0.14, 0.25, 0.88),
        completion=(0.62, 0.16, 0.18, 0.94),
        tenure_months=(12, 10, 1, 60),
        playback_speed_mix=[(1.0, 0.63), (1.25, 0.24), (1.5, 0.11), (2.0, 0.02)],
        privacy="shared_home_audio",
        interruption_load="medium",
        discovery_mix=[("friend", 0.28), ("in_app_recommendation", 0.32), ("social_short_clip", 0.26), ("browsing", 0.14)],
        region_mix=[
            ("household_catharsis_devotees", 0.34),
            ("slow_burn_comfort_seekers", 0.27),
            ("justice_payoff_bingers", 0.18),
            ("tier1_aspirational_escapists", 0.09),
            ("status_progression_loyalists", 0.08),
            ("high_churn_thrill_chasers", 0.04),
        ],
        genre_base={
            "modern_romance": 0.58,
            "office_drama": 0.34,
            "revenge": 0.46,
            "system_progression": 0.32,
            "family_drama": 0.68,
            "dark_romance": 0.34,
            "urban_fantasy": 0.28,
            "crime_mystery": 0.42,
            "horror": 0.28,
            "fantasy_sci_fi": 0.28,
        },
    ),
    ListenerSeed(
        seed_id="fitness_walk_listener",
        label="Workout or evening walk listener",
        weight=0.05,
        context="gym, run, or evening walk",
        session_pattern="binge",
        age=(27, 5, 18, 40),
        gender_mix=[("female", 0.42), ("male", 0.56), ("nonbinary", 0.02)],
        city_tier_mix=[(1, 0.70), (2, 0.30)],
        profession_mix=[
            ("fitness trainer", 0.14),
            ("software engineer", 0.13),
            ("sales executive", 0.12),
            ("college student", 0.12),
            ("founder", 0.10),
            ("consultant", 0.10),
            ("retail manager", 0.09),
            ("operations associate", 0.09),
            ("content creator", 0.06),
            ("banking associate", 0.05),
        ],
        avg_daily_minutes=(74, 28, 18, 180),
        session_minutes=(42, 12, 15, 90),
        gap_hours=(16, 7, 4, 48),
        payment_mix=[("free", 0.36), ("light", 0.24), ("occasional", 0.22), ("regular", 0.14), ("heavy", 0.04)],
        churn=(0.73, 0.12, 0.40, 0.96),
        completion=(0.42, 0.16, 0.08, 0.82),
        tenure_months=(6, 6, 1, 36),
        playback_speed_mix=[(1.0, 0.25), (1.25, 0.38), (1.5, 0.32), (2.0, 0.05)],
        privacy="private_headphones",
        interruption_load="medium",
        discovery_mix=[("social_short_clip", 0.50), ("in_app_recommendation", 0.25), ("browsing", 0.15), ("friend", 0.10)],
        region_mix=[
            ("high_churn_thrill_chasers", 0.36),
            ("justice_payoff_bingers", 0.25),
            ("status_progression_loyalists", 0.18),
            ("tier1_aspirational_escapists", 0.12),
            ("slow_burn_comfort_seekers", 0.06),
            ("household_catharsis_devotees", 0.03),
        ],
        genre_base={
            "modern_romance": 0.44,
            "office_drama": 0.42,
            "revenge": 0.66,
            "system_progression": 0.58,
            "family_drama": 0.24,
            "dark_romance": 0.42,
            "urban_fantasy": 0.52,
            "crime_mystery": 0.62,
            "horror": 0.42,
            "fantasy_sci_fi": 0.50,
        },
    ),
    ListenerSeed(
        seed_id="lapsed_returner",
        label="Lapsed returner testing a new show",
        weight=0.03,
        context="trying a recommended comeback series",
        session_pattern="trial",
        age=(30, 6, 20, 46),
        gender_mix=[("female", 0.48), ("male", 0.50), ("nonbinary", 0.02)],
        city_tier_mix=[(1, 0.50), (2, 0.50)],
        profession_mix=[
            ("software developer", 0.14),
            ("small business owner", 0.14),
            ("college student", 0.12),
            ("marketing manager", 0.12),
            ("teacher", 0.11),
            ("sales executive", 0.10),
            ("consultant", 0.09),
            ("homemaker", 0.09),
            ("designer", 0.09),
        ],
        avg_daily_minutes=(44, 22, 8, 120),
        session_minutes=(18, 9, 5, 55),
        gap_hours=(36, 18, 8, 120),
        payment_mix=[("free", 0.58), ("light", 0.23), ("occasional", 0.13), ("regular", 0.05), ("heavy", 0.01)],
        churn=(0.82, 0.10, 0.55, 0.98),
        completion=(0.28, 0.13, 0.04, 0.68),
        tenure_months=(14, 10, 2, 60),
        playback_speed_mix=[(1.0, 0.45), (1.25, 0.32), (1.5, 0.20), (2.0, 0.03)],
        privacy="private_headphones",
        interruption_load="medium",
        discovery_mix=[("social_short_clip", 0.42), ("friend", 0.22), ("in_app_recommendation", 0.22), ("browsing", 0.14)],
        region_mix=[
            ("high_churn_thrill_chasers", 0.30),
            ("slow_burn_comfort_seekers", 0.21),
            ("tier1_aspirational_escapists", 0.18),
            ("justice_payoff_bingers", 0.15),
            ("status_progression_loyalists", 0.10),
            ("household_catharsis_devotees", 0.06),
        ],
        genre_base={
            "modern_romance": 0.52,
            "office_drama": 0.44,
            "revenge": 0.54,
            "system_progression": 0.46,
            "family_drama": 0.34,
            "dark_romance": 0.48,
            "urban_fantasy": 0.42,
            "crime_mystery": 0.54,
            "horror": 0.34,
            "fantasy_sci_fi": 0.42,
        },
    ),
    ListenerSeed(
        seed_id="longhaul_offline_traveller",
        label="Long-haul traveller with offline downloads",
        weight=0.02,
        context="intercity train, bus, or flight",
        session_pattern="binge",
        age=(33, 8, 21, 54),
        gender_mix=[("female", 0.44), ("male", 0.54), ("nonbinary", 0.02)],
        city_tier_mix=[(1, 0.35), (2, 0.65)],
        profession_mix=[
            ("sales manager", 0.20),
            ("consultant", 0.16),
            ("founder", 0.13),
            ("government exam aspirant", 0.12),
            ("regional business owner", 0.11),
            ("teacher", 0.10),
            ("operations manager", 0.10),
            ("software engineer", 0.08),
        ],
        avg_daily_minutes=(132, 50, 35, 330),
        session_minutes=(88, 35, 25, 220),
        gap_hours=(30, 16, 6, 120),
        payment_mix=[("free", 0.30), ("light", 0.20), ("occasional", 0.24), ("regular", 0.19), ("heavy", 0.07)],
        churn=(0.55, 0.14, 0.20, 0.86),
        completion=(0.68, 0.16, 0.25, 0.96),
        tenure_months=(11, 9, 1, 60),
        playback_speed_mix=[(1.0, 0.44), (1.25, 0.33), (1.5, 0.20), (2.0, 0.03)],
        privacy="offline_downloads",
        interruption_load="low",
        discovery_mix=[("in_app_recommendation", 0.35), ("browsing", 0.26), ("social_short_clip", 0.25), ("friend", 0.14)],
        region_mix=[
            ("status_progression_loyalists", 0.30),
            ("justice_payoff_bingers", 0.24),
            ("tier1_aspirational_escapists", 0.17),
            ("high_churn_thrill_chasers", 0.14),
            ("slow_burn_comfort_seekers", 0.10),
            ("household_catharsis_devotees", 0.05),
        ],
        genre_base={
            "modern_romance": 0.50,
            "office_drama": 0.48,
            "revenge": 0.62,
            "system_progression": 0.62,
            "family_drama": 0.34,
            "dark_romance": 0.42,
            "urban_fantasy": 0.50,
            "crime_mystery": 0.62,
            "horror": 0.38,
            "fantasy_sci_fi": 0.50,
        },
    ),
]


NEED_REGIONS = {
    "justice_payoff_bingers": NeedRegion(
        region_id="justice_payoff_bingers",
        label="Justice-payoff binger",
        drivers={"justice_seeking": "very_high", "catharsis": "high", "escapism": "medium"},
        patience=(0.48, 0.13, 0.18, 0.78),
        commitment_mix=[(60, 0.15), (100, 0.36), (180, 0.32), (300, 0.17)],
        exploration=(0.58, 0.15, 0.18, 0.90),
        pay_shift=-0.04,
        genre_boost={"revenge": 0.16, "crime_mystery": 0.10, "family_drama": 0.06},
        anti_stereotype="family_bridge",
        need_summary="needs humiliation to convert into visible revenge, rescue, or public proof",
        topics=["revenge arcs", "betrayal", "public vindication"],
    ),
    "status_progression_loyalists": NeedRegion(
        region_id="status_progression_loyalists",
        label="Status-progression loyalist",
        drivers={"power_fantasy": "very_high", "wish_fulfillment": "high", "identity": "medium"},
        patience=(0.64, 0.12, 0.32, 0.90),
        commitment_mix=[(100, 0.18), (180, 0.32), (300, 0.32), (600, 0.18)],
        exploration=(0.50, 0.14, 0.15, 0.84),
        pay_shift=-0.06,
        genre_boost={"system_progression": 0.18, "office_drama": 0.10, "fantasy_sci_fi": 0.08},
        anti_stereotype="weekend_epic_switcher",
        need_summary="stays for upgrades, hidden status, rank movement, and long payoff ladders",
        topics=["power progression", "status reveals", "underdog rise"],
    ),
    "household_catharsis_devotees": NeedRegion(
        region_id="household_catharsis_devotees",
        label="Household catharsis devotee",
        drivers={"catharsis": "very_high", "belonging": "high", "comfort": "medium"},
        patience=(0.62, 0.14, 0.28, 0.90),
        commitment_mix=[(60, 0.16), (100, 0.30), (180, 0.36), (300, 0.18)],
        exploration=(0.38, 0.14, 0.08, 0.76),
        pay_shift=0.02,
        genre_boost={"family_drama": 0.18, "modern_romance": 0.08, "revenge": 0.07},
        anti_stereotype="family_bridge",
        need_summary="wants family pressure, moral repair, emotional release, and relationship consequences",
        topics=["family secrets", "emotional repair", "domestic power shifts"],
    ),
    "slow_burn_comfort_seekers": NeedRegion(
        region_id="slow_burn_comfort_seekers",
        label="Slow-burn comfort seeker",
        drivers={"comfort": "very_high", "belonging": "high", "wish_fulfillment": "medium"},
        patience=(0.72, 0.10, 0.42, 0.95),
        commitment_mix=[(100, 0.18), (180, 0.34), (300, 0.30), (600, 0.18)],
        exploration=(0.35, 0.13, 0.06, 0.74),
        pay_shift=0.03,
        genre_boost={"modern_romance": 0.12, "dark_romance": 0.08, "family_drama": 0.08},
        anti_stereotype="comfort_after_work",
        need_summary="uses the story as steady emotional company and forgives slower chapters if the bond deepens",
        topics=["slow-burn romance", "comfort listening", "relationship healing"],
    ),
    "tier1_aspirational_escapists": NeedRegion(
        region_id="tier1_aspirational_escapists",
        label="Aspirational escapist",
        drivers={"identity": "very_high", "wish_fulfillment": "high", "escapism": "high"},
        patience=(0.58, 0.13, 0.24, 0.86),
        commitment_mix=[(60, 0.18), (100, 0.38), (180, 0.30), (300, 0.14)],
        exploration=(0.54, 0.16, 0.15, 0.88),
        pay_shift=-0.03,
        genre_boost={"office_drama": 0.16, "modern_romance": 0.10, "dark_romance": 0.08},
        anti_stereotype="ambition_required",
        need_summary="wants modern aspiration, competence, agency, and romance that does not erase ambition",
        topics=["career wins", "billionaire romance", "urban aspiration"],
    ),
    "high_churn_thrill_chasers": NeedRegion(
        region_id="high_churn_thrill_chasers",
        label="High-churn thrill chaser",
        drivers={"escapism": "very_high", "justice_seeking": "high", "power_fantasy": "medium"},
        patience=(0.42, 0.12, 0.14, 0.72),
        commitment_mix=[(30, 0.16), (60, 0.34), (100, 0.30), (180, 0.20)],
        exploration=(0.72, 0.14, 0.28, 0.96),
        pay_shift=0.05,
        genre_boost={"crime_mystery": 0.14, "horror": 0.12, "urban_fantasy": 0.10, "revenge": 0.08},
        anti_stereotype="paywall_skeptic",
        need_summary="samples aggressively and only stays when danger, twist, or forbidden desire arrives fast",
        topics=["cliffhangers", "crime mystery", "supernatural danger"],
    ),
}

INDIA_ENGLISH_COHORT_CARD["listener_seed_mix"] = [
    {
        "id": item.seed_id,
        "label": item.label,
        "weight": item.weight,
        "context": item.context,
        "session_pattern": item.session_pattern,
    }
    for item in LISTENER_SEEDS
]
INDIA_ENGLISH_COHORT_CARD["need_regions"] = [
    {
        "id": item.region_id,
        "label": item.label,
        "drivers": item.drivers,
        "need_summary": item.need_summary,
    }
    for item in NEED_REGIONS.values()
]
INDIA_ENGLISH_COHORT_CARD["mbti"] = {
    "scope": "Voice and decision-style only; it does not alter numeric retention fields.",
    "types": dict(zip(MBTI_TYPES, MBTI_WEIGHTS)),
}


def generate_india_english_population(size: int, seed: int) -> list[Persona]:
    rng = random.Random(seed)
    assignments = _build_assignments(size, rng)
    mbti_values = _allocated_values(
        size,
        list(zip(MBTI_TYPES, MBTI_WEIGHTS)),
        rng,
    )

    population: list[Persona] = []
    used_names: set[str] = set()
    for idx, ((listener_seed, need_region), mbti) in enumerate(zip(assignments, mbti_values), start=1):
        city_tier = weighted_choice(rng, listener_seed.city_tier_mix)
        city = rng.choice(CITIES_BY_TIER[city_tier])
        profession = weighted_choice(rng, listener_seed.profession_mix)
        gender = weighted_choice(rng, listener_seed.gender_mix)
        realname = _unique_name(rng, used_names, gender)
        age = _rounded_gauss(rng, listener_seed.age)
        avg_daily_minutes = _rounded_gauss(rng, listener_seed.avg_daily_minutes)
        session_minutes = _rounded_gauss(rng, listener_seed.session_minutes)
        gap_hours = _rounded_gauss(rng, listener_seed.gap_hours)
        tenure_months = _rounded_gauss(rng, listener_seed.tenure_months)
        coin_spend_tier = weighted_choice(rng, listener_seed.payment_mix)
        language_register = weighted_choice(rng, REGISTER_MIX)
        language_preference = list(weighted_choice(rng, LANGUAGE_MIX))
        genre_affinity = _genre_affinity(rng, listener_seed, need_region)
        drivers = _drivers_with_jitter(rng, need_region.drivers)
        driver_intensity = _driver_intensity(rng, drivers)
        narrative_patience = _bounded_value(rng, need_region.patience)
        churn_sensitivity = _bounded_value(rng, listener_seed.churn)
        pay_threshold = clamp(
            bounded_gauss(rng, PAY_THRESHOLD_BY_TIER[coin_spend_tier], 0.06, 0.15, 0.92)
            + need_region.pay_shift,
            0.10,
            0.95,
        )
        historical_completion = _bounded_value(rng, listener_seed.completion)
        exploration_propensity = _bounded_value(rng, need_region.exploration)
        commitment_tolerance = weighted_choice(rng, need_region.commitment_mix)
        playback_speed = weighted_choice(rng, listener_seed.playback_speed_mix)
        discovery_channel = weighted_choice(rng, listener_seed.discovery_mix)
        binge_speed = int(clamp(round(avg_daily_minutes / 12), 1, 15))
        interested_topics = _interested_topics(genre_affinity, need_region)

        if need_region.anti_stereotype == "ambition_required":
            driver_intensity["identity"] = round(clamp(driver_intensity["identity"] + 0.05, 0.0, 1.0), 3)
            genre_affinity["office_drama"] = round(clamp(genre_affinity["office_drama"] + 0.06, 0.0, 1.0), 3)
        elif need_region.anti_stereotype == "paywall_skeptic":
            pay_threshold = clamp(pay_threshold + 0.06, 0.10, 0.95)
            churn_sensitivity = round(clamp(churn_sensitivity + 0.05, 0.0, 1.0), 3)
        elif need_region.anti_stereotype == "comfort_after_work":
            driver_intensity["comfort"] = round(clamp(driver_intensity["comfort"] + 0.06, 0.0, 1.0), 3)
            narrative_patience = round(clamp(narrative_patience + 0.06, 0.0, 1.0), 3)

        bio = _bio_sentence(
            profession=profession,
            listener_seed=listener_seed,
            need_region=need_region,
            city=city,
        )
        persona_text = _persona_sentence(
            realname=realname,
            age=age,
            city=city,
            profession=profession,
            listener_seed=listener_seed,
            need_region=need_region,
            mbti=mbti,
            playback_speed=playback_speed,
        )

        population.append(
            Persona(
                persona_id=f"in_en_{idx:05d}",
                realname=realname,
                age=age,
                gender=gender,
                country="IN",
                city=city,
                city_tier=city_tier,
                profession=profession,
                cohort_id=listener_seed.seed_id,
                cohort_label=listener_seed.label,
                region_id=need_region.region_id,
                region_label=need_region.label,
                bio=bio,
                persona=persona_text,
                mbti=mbti,
                language_preference=language_preference,
                listening_context=listener_seed.context,
                primary_drivers=list(need_region.drivers.keys())[:3],
                drivers=drivers,
                driver_intensity={key: round(value, 3) for key, value in driver_intensity.items()},
                genre_affinity={key: round(value, 3) for key, value in genre_affinity.items()},
                interested_topics=interested_topics,
                avg_daily_minutes=avg_daily_minutes,
                session_minutes=session_minutes,
                session_pattern=listener_seed.session_pattern,
                gap_hours=gap_hours,
                coin_spend_tier=coin_spend_tier,
                historical_completion=round(historical_completion, 3),
                tenure_months=tenure_months,
                playback_speed=playback_speed,
                listening_privacy=listener_seed.privacy,
                interruption_load=listener_seed.interruption_load,
                discovery_channel=discovery_channel,
                exploration_propensity=round(exploration_propensity, 3),
                narrative_patience=round(narrative_patience, 3),
                churn_sensitivity=round(churn_sensitivity, 3),
                pay_threshold=round(pay_threshold, 3),
                commitment_tolerance=commitment_tolerance,
                binge_speed=binge_speed,
                language_register=language_register,
                anti_stereotype=need_region.anti_stereotype,
            )
        )
    return population


def _build_assignments(
    size: int,
    rng: random.Random,
) -> list[tuple[ListenerSeed, NeedRegion]]:
    assignments: list[tuple[ListenerSeed, NeedRegion]] = []
    seed_counts = _allocated_counts(size, [(item.seed_id, item.weight) for item in LISTENER_SEEDS])
    seeds_by_id = {item.seed_id: item for item in LISTENER_SEEDS}
    for seed_id, count in seed_counts.items():
        listener_seed = seeds_by_id[seed_id]
        region_counts = _allocated_counts(count, listener_seed.region_mix)
        for region_id, region_count in region_counts.items():
            assignments.extend((listener_seed, NEED_REGIONS[region_id]) for _ in range(region_count))
    rng.shuffle(assignments)
    return assignments


def _allocated_values(
    size: int,
    weighted_items: list[tuple[Any, float]],
    rng: random.Random,
) -> list[Any]:
    counts = _allocated_counts(size, weighted_items)
    values: list[Any] = []
    for item, count in counts.items():
        values.extend([item] * count)
    rng.shuffle(values)
    return values


def _allocated_counts(
    size: int,
    weighted_items: list[tuple[Any, float]],
) -> dict[Any, int]:
    total = sum(weight for _, weight in weighted_items)
    exact = [(item, size * weight / total) for item, weight in weighted_items]
    counts = {item: int(math.floor(value)) for item, value in exact}
    remainder = size - sum(counts.values())
    ranked = sorted(exact, key=lambda pair: pair[1] - math.floor(pair[1]), reverse=True)
    for item, _ in ranked[:remainder]:
        counts[item] += 1
    return counts


def _unique_name(rng: random.Random, used_names: set[str], gender: str) -> str:
    first_names = FIRST_NAMES_BY_GENDER.get(gender, FIRST_NAMES)
    for _ in range(100):
        name = f"{rng.choice(first_names)} {rng.choice(LAST_NAMES)}"
        if name not in used_names:
            used_names.add(name)
            return name
    name = f"{rng.choice(first_names)} {rng.choice(LAST_NAMES)} {len(used_names) + 1}"
    used_names.add(name)
    return name


def _rounded_gauss(rng: random.Random, spec: tuple[float, float, int, int]) -> int:
    mean, sd, low, high = spec
    return int(clamp(round(rng.gauss(mean, sd)), low, high))


def _bounded_value(rng: random.Random, spec: tuple[float, float, float, float]) -> float:
    mean, sd, low, high = spec
    return bounded_gauss(rng, mean, sd, low, high)


def _genre_affinity(
    rng: random.Random,
    listener_seed: ListenerSeed,
    need_region: NeedRegion,
) -> dict[str, float]:
    affinity: dict[str, float] = {}
    for genre, base in listener_seed.genre_base.items():
        boosted = base + need_region.genre_boost.get(genre, 0.0)
        affinity[genre] = clamp(rng.gauss(boosted, 0.10), 0.05, 0.98)
    return affinity


def _drivers_with_jitter(rng: random.Random, drivers: dict[str, str]) -> dict[str, str]:
    values = dict(drivers)
    if rng.random() > 0.25:
        return values
    key = rng.choice(list(values))
    order = ["low", "medium", "high", "very_high"]
    current = order.index(values[key])
    step = 1 if rng.random() < 0.5 else -1
    values[key] = order[int(clamp(current + step, 0, len(order) - 1))]
    return values


def _driver_intensity(
    rng: random.Random,
    drivers: dict[str, str],
) -> dict[str, float]:
    values = {
        "identity": 0.36,
        "wish_fulfillment": 0.38,
        "escapism": 0.42,
        "justice_seeking": 0.36,
        "comfort": 0.32,
    }
    for driver, label in drivers.items():
        if driver in ENGINE_DRIVER_KEYS:
            values[driver] = DRIVER_VALUE[label]
        elif driver == "power_fantasy":
            values["wish_fulfillment"] = max(values["wish_fulfillment"], DRIVER_VALUE[label] - 0.05)
        elif driver == "catharsis":
            values["justice_seeking"] = max(values["justice_seeking"], DRIVER_VALUE[label] - 0.05)
        elif driver == "belonging":
            values["comfort"] = max(values["comfort"], DRIVER_VALUE[label] - 0.04)
    return {
        key: clamp(rng.gauss(value, 0.045), 0.05, 0.98)
        for key, value in values.items()
    }


def _interested_topics(
    genre_affinity: dict[str, float],
    need_region: NeedRegion,
) -> list[str]:
    top_genres = [
        GENRE_NAMES[key]
        for key, _ in sorted(genre_affinity.items(), key=lambda item: item[1], reverse=True)[:3]
    ]
    topics = top_genres + need_region.topics
    deduped: list[str] = []
    for topic in topics:
        if topic not in deduped:
            deduped.append(topic)
    return deduped[:5]


def _bio_sentence(
    profession: str,
    listener_seed: ListenerSeed,
    need_region: NeedRegion,
    city: str,
) -> str:
    return (
        f"{profession.title()} in {city}; listens during {listener_seed.context} and follows "
        f"{', '.join(need_region.topics[:2])} in English/Hinglish audio series."
    )


def _persona_sentence(
    realname: str,
    age: int,
    city: str,
    profession: str,
    listener_seed: ListenerSeed,
    need_region: NeedRegion,
    mbti: str,
    playback_speed: float,
) -> str:
    return (
        f"{realname} is a {age}-year-old {profession} in {city} ({mbti}) who listens at "
        f"{playback_speed:g}x during {listener_seed.context}; {need_region.need_summary}."
    )


def init_state(persona: Persona) -> PersonaState:
    return PersonaState(
        persona_id=persona.persona_id,
        episodes_heard=0,
        active=True,
        dropped_at=None,
        story_summary="",
        unresolved_questions=[],
        payoff_trust=0.22,
        agency_trust=0.25,
        coins_spent=0,
    )
