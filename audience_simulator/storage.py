from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path
from typing import Any

from .models import Persona, Reaction
from .utils import json_dumps


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            created_at INTEGER NOT NULL,
            story_path TEXT NOT NULL,
            story_version TEXT NOT NULL,
            cohort_name TEXT NOT NULL,
            population_size INTEGER NOT NULL,
            seed INTEGER NOT NULL,
            engine TEXT NOT NULL,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS personas (
            run_id TEXT NOT NULL,
            persona_id TEXT NOT NULL,
            profile_json TEXT NOT NULL,
            PRIMARY KEY (run_id, persona_id)
        );

        CREATE TABLE IF NOT EXISTS reactions (
            run_id TEXT NOT NULL,
            persona_id TEXT NOT NULL,
            cohort TEXT NOT NULL,
            episode_no INTEGER NOT NULL,
            will_continue INTEGER NOT NULL,
            continue_reason TEXT NOT NULL,
            would_pay INTEGER NOT NULL,
            pay_reason TEXT NOT NULL,
            drop_beat TEXT,
            craving_mid INTEGER NOT NULL,
            craving_end INTEGER NOT NULL,
            next_prediction TEXT NOT NULL,
            emotional_state TEXT NOT NULL,
            felt_emotion TEXT NOT NULL,
            emotion_shift TEXT NOT NULL,
            judgement_bridge TEXT NOT NULL,
            decision_factors_json TEXT NOT NULL,
            engagement_score REAL NOT NULL,
            pay_pressure REAL NOT NULL,
            signal_json TEXT NOT NULL,
            state_json TEXT NOT NULL,
            judgement_agent TEXT,
            judgement_changed INTEGER NOT NULL DEFAULT 0,
            judgement_notes TEXT,
            raw_reaction_json TEXT,
            PRIMARY KEY (run_id, persona_id, episode_no)
        );

        CREATE TABLE IF NOT EXISTS episode_metrics (
            run_id TEXT NOT NULL,
            episode_no INTEGER NOT NULL,
            episode_title TEXT NOT NULL,
            active_before INTEGER NOT NULL,
            continue_count INTEGER NOT NULL,
            drop_count INTEGER NOT NULL,
            pay_count INTEGER NOT NULL,
            retention_from_start REAL NOT NULL,
            continue_rate REAL NOT NULL,
            pay_rate REAL NOT NULL,
            avg_craving_delta REAL NOT NULL,
            prediction_entropy REAL NOT NULL,
            top_drop_beat TEXT,
            top_prediction_buckets_json TEXT NOT NULL,
            top_drop_beats_json TEXT NOT NULL,
            PRIMARY KEY (run_id, episode_no)
        );
        """
    )


def write_sqlite(
    db_path: Path,
    run_record: dict[str, Any],
    personas: list[Persona],
    reactions: list[Reaction],
    metrics: list[dict[str, Any]],
) -> None:
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    conn.execute(
        """
        INSERT OR REPLACE INTO runs (
            run_id, created_at, story_path, story_version, cohort_name,
            population_size, seed, engine, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_record["run_id"],
            run_record["created_at"],
            run_record["story_path"],
            run_record["story_version"],
            run_record["cohort_name"],
            run_record["population_size"],
            run_record["seed"],
            run_record["engine"],
            run_record.get("notes", ""),
        ),
    )
    conn.executemany(
        "INSERT OR REPLACE INTO personas (run_id, persona_id, profile_json) VALUES (?, ?, ?)",
        [
            (run_record["run_id"], persona.persona_id, json_dumps(dataclasses.asdict(persona)))
            for persona in personas
        ],
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO reactions (
            run_id, persona_id, cohort, episode_no, will_continue,
            continue_reason, would_pay, pay_reason, drop_beat, craving_mid,
            craving_end, next_prediction, emotional_state,
            felt_emotion, emotion_shift, judgement_bridge, decision_factors_json,
            engagement_score, pay_pressure, signal_json, state_json,
            judgement_agent, judgement_changed, judgement_notes, raw_reaction_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                reaction.run_id,
                reaction.persona_id,
                reaction.cohort,
                reaction.episode_no,
                int(reaction.will_continue),
                reaction.continue_reason,
                int(reaction.would_pay),
                reaction.pay_reason,
                reaction.drop_beat,
                reaction.craving_mid,
                reaction.craving_end,
                reaction.next_prediction,
                reaction.emotional_state,
                reaction.felt_emotion,
                reaction.emotion_shift,
                reaction.judgement_bridge,
                json_dumps(reaction.decision_factors),
                reaction.engagement_score,
                reaction.pay_pressure,
                json_dumps(reaction.signal_json),
                json_dumps(reaction.state_json),
                reaction.judgement_agent,
                int(reaction.judgement_changed),
                reaction.judgement_notes,
                json_dumps(reaction.raw_reaction_json or {}),
            )
            for reaction in reactions
        ],
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO episode_metrics (
            run_id, episode_no, episode_title, active_before, continue_count,
            drop_count, pay_count, retention_from_start, continue_rate, pay_rate,
            avg_craving_delta, prediction_entropy, top_drop_beat,
            top_prediction_buckets_json, top_drop_beats_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["run_id"],
                row["episode_no"],
                row["episode_title"],
                row["active_before"],
                row["continue_count"],
                row["drop_count"],
                row["pay_count"],
                row["retention_from_start"],
                row["continue_rate"],
                row["pay_rate"],
                row["avg_craving_delta"],
                row["prediction_entropy"],
                row["top_drop_beat"],
                json_dumps(row["top_prediction_buckets"]),
                json_dumps(row["top_drop_beats"]),
            )
            for row in metrics
        ],
    )
    conn.commit()
    conn.close()
