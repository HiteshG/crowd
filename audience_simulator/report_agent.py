from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .cohorts import INDIA_ENGLISH_COHORT_CARD
from .env import openai_api_key, openai_model_candidates
from .utils import pct


DETERMINISTIC_REPORT_AGENT_NAME = "deterministic_report_writer_v1"
LLM_REPORT_AGENT_NAME = "openai_report_writer_v1"

REPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "markdown": {"type": "string"},
    },
    "required": ["markdown"],
    "additionalProperties": False,
}


def report_agent_name(report_mode: str) -> str:
    if report_mode == "llm":
        return LLM_REPORT_AGENT_NAME
    return DETERMINISTIC_REPORT_AGENT_NAME


def build_report_agent(
    report_mode: str,
    *,
    model: str | None = None,
    seed: int = 7,
    reasoning_effort: str = "medium",
) -> "DeterministicReportWritingAgent | OpenAIReportWritingAgent":
    if report_mode == "llm":
        return OpenAIReportWritingAgent(
            model=model or "gpt-5.6-luna",
            seed=seed,
            reasoning_effort=reasoning_effort,
        )
    if report_mode == "deterministic":
        return DeterministicReportWritingAgent()
    raise ValueError(f"Unknown report mode '{report_mode}'")


class DeterministicReportWritingAgent:
    """Writes a decision-focused report from structured simulator outputs."""

    agent_name = DETERMINISTIC_REPORT_AGENT_NAME

    def render(self, run_record: dict[str, Any], verdict: dict[str, Any]) -> str:
        metrics = verdict["episode_metrics"]
        insights = verdict.get("insights", {})
        story_title = _story_title(run_record)
        n_cohorts = len({seed["id"] for seed in INDIA_ENGLISH_COHORT_CARD["listener_seed_mix"]})
        lines = [
            f"# {story_title} - Audience Simulation Report",
            "",
            (
                f"Run `{verdict['run_id']}` | seed `{run_record.get('seed')}` | "
                f"panel `{verdict['cohort']}` ({verdict['population_size']} personas, "
                f"{n_cohorts} occasion cohorts x 6 need-regions) | engine `{run_record.get('engine_kind')}`"
            ),
            "> Uncalibrated simulator output. Rankings, drop points, and directional diagnosis only; absolute levels await backtest against real retention.",
            "",
            "## 1. Verdict Card",
            "",
            f"- Recommendation: `{verdict['recommendation']}`",
            f"- Confidence: `{verdict['confidence']}`",
            f"- Retention index @ ep {verdict['episode_count']}: **{verdict['final_retention_from_start'] * 100:.1f}** (ep1 = 100)",
            f"- Mean continue: **{pct(verdict['mean_continue_rate']).strip()}**",
            f"- Mean craving delta: **{verdict['mean_craving_delta']:.2f}**",
            f"- Strongest region: {_strongest_region(insights)}",
            f"- One-line thesis: {insights.get('headline', 'No thesis available.')}",
        ]
        self._append_weak_points(lines, verdict)
        self._append_region_curves(lines, insights)
        self._append_episode_table(lines, insights, metrics)
        self._append_drop_beat_inspector(lines, insights)
        self._append_llm_heuristic_bridge(lines, insights)
        self._append_paywall_map(lines, verdict, insights)
        self._append_expectation_scorecard(lines, insights)
        self._append_panel_voice(lines, insights)
        self._append_editorial_actions(lines, insights)
        self._append_audit(lines, run_record, verdict, insights)
        return "\n".join(lines) + "\n"

    def _append_weak_points(self, lines: list[str], verdict: dict[str, Any]) -> None:
        weakest = verdict.get("weakest_episode")
        paywall = verdict.get("paywall_candidate")
        if weakest:
            lines.append(
                f"- Weakest episode: episode {weakest['episode_no']} "
                f"({weakest['title']}), {pct(weakest['continue_rate']).strip()} continue."
            )
            if weakest.get("top_drop_beat"):
                lines.append(f"- First beat to inspect: `{weakest['top_drop_beat']}`.")
        if paywall:
            lines.append(
                f"- Best paywall candidate: episode {paywall['episode_no']} "
                f"({paywall['title']}), {pct(paywall['pay_rate']).strip()} simulated pay."
            )

    def _append_region_curves(self, lines: list[str], insights: dict[str, Any]) -> None:
        lines.extend(
            [
                "",
                "## 2. Retention by Need-Region",
                "",
                "| Region | Start | ep1 | ep2 | ep3 | ep4 | ep5 | ep6 | ep7 | ep8 | Departure signature |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for row in insights.get("region_retention_curves", []):
            points = row.get("points", [])
            point_values = [f"{point['retained_index']:.1f}" for point in points[:8]]
            while len(point_values) < 8:
                point_values.append("-")
            lines.append(
                "| "
                f"{row['region']} | "
                f"{row['start_count']} | "
                + " | ".join(point_values)
                + f" | {row['departure_signature']} |"
            )
        microsegments = insights.get("microsegment_retention") or []
        if microsegments:
            lines.extend(
                [
                    "",
                    "### Microsegments",
                    "",
                    "| Microsegment | Start | Final | Retention idx |",
                    "|---|---:|---:|---:|",
                ]
            )
            for row in microsegments[:10]:
                lines.append(
                    f"| {row['microsegment']} | {row['start_count']} | "
                    f"{row['final_count']} | {row['retention_index']:.1f} |"
                )

    def _append_episode_table(
        self,
        lines: list[str],
        insights: dict[str, Any],
        metrics: list[dict[str, Any]],
    ) -> None:
        lines.extend(
            [
                "",
                "## 3. Episode Table",
                "",
                "| Ep | Title | Continue tier | Retained idx | Active | Lost | Top drop beat | Regions leaving | Pay pressure |",
                "|---:|---|---|---:|---:|---:|---|---|---|",
            ]
        )
        table = insights.get("episode_table") or []
        if not table:
            table = [
                {
                    "episode_no": row["episode_no"],
                    "title": row["episode_title"],
                    "continue_tier": "unknown",
                    "retained_index": row["retention_from_start"] * 100,
                    "active": row["active_before"],
                    "lost": row["drop_count"],
                    "top_drop_beat": row["top_drop_beat"],
                    "regions_leaving": [],
                    "pay_pressure": "none",
                }
                for row in metrics
            ]
        for row in table:
            regions = ", ".join(
                f"{item['region']} ({item['count']})" for item in row.get("regions_leaving", [])
            )
            lines.append(
                "| "
                f"{row['episode_no']} | "
                f"{row['title']} | "
                f"{row['continue_tier']} | "
                f"{row['retained_index']:.1f} | "
                f"{row['active']} | "
                f"{row['lost']} | "
                f"{row['top_drop_beat'] or '-'} |"
                f" {regions or '-'} | "
                f"{row['pay_pressure']} |"
            )

    def _append_drop_beat_inspector(self, lines: list[str], insights: dict[str, Any]) -> None:
        lines.extend(["", "## 4. Drop-Beat Inspector", ""])
        rows = insights.get("drop_beat_inspector") or []
        if not rows:
            lines.append("- No flagged drop beats.")
            return
        for row in rows[:6]:
            line_note = ""
            if row.get("line_start") is not None and row.get("line_end") is not None:
                line_note = f", lines {row['line_start']}-{row['line_end']}"
            label_note = f" - {row['label']}" if row.get("label") else ""
            lines.extend(
                [
                    f"### `{row['beat_id']}`{label_note} - Ep {row['episode_no']}, {row['continue_tier']} continue{line_note}",
                    "",
                    f"> {row['quote']}",
                    "",
                ]
            )
            who_left = ", ".join(
                f"{item['region']} ({item['count']})" for item in row.get("who_left", [])
            )
            why = "; ".join(f"{item['count']} agents: {item['text']}" for item in row.get("why", []))
            context = ", ".join(
                f"{item['signal']}={item['value']}" for item in row.get("story_side_context", [])
            )
            lines.append(f"- Who left: {who_left or '-'}")
            if row.get("beat_risk") and row.get("beat_risk") != "none":
                lines.append(f"- Beat risk: {row['beat_risk']} - {row.get('beat_risk_reason') or '-'}")
            lines.append(f"- Why: {why or '-'}")
            lines.append(f"- Story-side context: {context or '-'}")

    def _append_llm_heuristic_bridge(self, lines: list[str], insights: dict[str, Any]) -> None:
        bridge = insights.get("llm_heuristic_bridge") or {}
        if not bridge:
            return
        summary = bridge.get("summary", {})
        lines.extend(
            [
                "",
                "## 4b. LLM / Heuristic Bridge",
                "",
                f"- LLM actual drops: {summary.get('llm_actual_drops', 0)}",
                f"- Advisory structural drop flags: {summary.get('advisory_drop_flags', 0)}",
                f"- Agreed drops: {summary.get('agreed_drops', 0)}",
                f"- Advisory-only warnings: {summary.get('advisory_only', 0)}",
                f"- LLM-only drops: {summary.get('llm_only', 0)}",
                f"- Applied overrides: {summary.get('applied_overrides', 0)}",
                f"- Read: {summary.get('interpretation', '')}",
                "",
                "| Ep | Active | LLM drops | Advisory flags | Agreed | Advisory-only | LLM-only | Read |",
                "|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for row in bridge.get("by_episode", []):
            lines.append(
                f"| {row['episode_no']} | {row['active']} | {row['llm_drops']} | "
                f"{row['advisory_drop_flags']} | {row['agreed_drops']} | "
                f"{row['advisory_only']} | {row['llm_only']} | {row['read']} |"
            )

    def _append_paywall_map(self, lines: list[str], verdict: dict[str, Any], insights: dict[str, Any]) -> None:
        lines.extend(
            [
                "",
                "## 5. Paywall Map",
                "",
                "| Ep | Ending type | Gate class | Regions with pay-psychology match | Verdict |",
                "|---:|---|---|---|---|",
            ]
        )
        for row in insights.get("paywall_map", []):
            regions = ", ".join(
                f"{item['region']} ({item['paid']}/{item['active']} paid)"
                for item in row.get("matched_regions", [])
            )
            lines.append(
                f"| {row['episode_no']} | {row['ending_type']} | {row['gate_class']} | "
                f"{regions or '-'} | {row['verdict']} |"
            )
        paywall = verdict.get("paywall_candidate")
        if paywall:
            lines.append("")
            lines.append(
                f"Best gate this run: **episode {paywall['episode_no']}** "
                f"({paywall['title']}), {pct(paywall['pay_rate']).strip()} simulated pay."
            )

    def _append_expectation_scorecard(self, lines: list[str], insights: dict[str, Any]) -> None:
        lines.extend(
            [
                "",
                "## 6. Expectation Scorecard",
                "",
                "| Pre-registered check | Result | Note |",
                "|---|---|---|",
            ]
        )
        symbol = {"fired": "PASS", "missed": "MISS", "partial": "PARTIAL"}
        for row in insights.get("expectation_scorecard", []):
            lines.append(f"| {row['check']} | {symbol.get(row['result'], row['result'])} | {row['note']} |")

    def _append_panel_voice(self, lines: list[str], insights: dict[str, Any]) -> None:
        voice = insights.get("weighted_agent_voice") or {}
        lines.extend(["", "## 7. Panel Voice", ""])
        self._append_weighted_theme(lines, "Why Droppers Left", voice.get("drop_reasons", []))
        self._append_weighted_theme(lines, "Why Stayers Stayed", voice.get("continue_reasons", []))
        self._append_weighted_theme(lines, "Emotion To Judgement", voice.get("judgement_bridges", []))
        self._append_weighted_theme(lines, "Felt Emotions", voice.get("felt_emotions", []))
        self._append_weighted_theme(lines, "Expected Next Beats", voice.get("next_predictions", []))
        self._append_weighted_theme(lines, "Paywall Objections", voice.get("pay_objections", []))

    def _append_weighted_theme(self, lines: list[str], label: str, rows: list[dict[str, Any]]) -> None:
        lines.append(f"**{label}**")
        if not rows:
            lines.append("- No data.")
            return
        for row in rows[:4]:
            lines.append(
                f"- {pct(row['market_mass_share']).strip()} market mass "
                f"({row['agent_episodes']} agent-episodes): {row['text']}"
            )

    def _append_editorial_actions(self, lines: list[str], insights: dict[str, Any]) -> None:
        lines.extend(["", "## 8. Editorial Actions", ""])
        actions = insights.get("editorial_actions") or []
        if not actions:
            lines.append("- No editorial actions generated.")
            return
        for index, action in enumerate(actions, start=1):
            lines.append(f"{index}. {action}")

    def _append_audit(
        self,
        lines: list[str],
        run_record: dict[str, Any],
        verdict: dict[str, Any],
        insights: dict[str, Any],
    ) -> None:
        reaction_calls = sum(row.get("active_before", 0) for row in verdict.get("episode_metrics", []))
        lines.extend(["", "## 9. Methods Footer", ""])
        lines.append(f"- Panel: `{verdict['cohort']}`")
        lines.append(f"- Population: {verdict['population_size']} synthetic listeners")
        lines.append(f"- Episodes: {verdict['episode_count']}")
        lines.append(f"- Engine: `{run_record.get('engine_kind')}` / `{run_record.get('engine')}`")
        lines.append(f"- Persona mode: `{run_record.get('persona_mode', 'seed')}`")
        if run_record.get("reaction_model"):
            lines.append(f"- Reaction model: `{run_record['reaction_model']}`")
        if run_record.get("reaction_reasoning_effort"):
            lines.append(f"- Reaction reasoning effort: `{run_record['reaction_reasoning_effort']}`")
        if run_record.get("persona_model"):
            lines.append(f"- Persona model: `{run_record['persona_model']}`")
        if run_record.get("persona_reasoning_effort"):
            lines.append(f"- Persona reasoning effort: `{run_record['persona_reasoning_effort']}`")
        if run_record.get("report_model"):
            lines.append(f"- Report model: `{run_record['report_model']}`")
        if run_record.get("report_reasoning_effort"):
            lines.append(f"- Report reasoning effort: `{run_record['report_reasoning_effort']}`")
        lines.append(f"- Report writer: `{run_record.get('report_agent', self.agent_name)}`")
        lines.append(f"- Beat generator: `{run_record.get('beat_generator', 'parser')}`")
        if run_record.get("beat_model"):
            lines.append(f"- Beat model: `{run_record['beat_model']}`")
        if run_record.get("beat_reasoning_effort"):
            lines.append(f"- Beat reasoning effort: `{run_record['beat_reasoning_effort']}`")
        lines.append(f"- Judgement mode: `{run_record.get('judgement_mode', 'off')}`")
        if run_record.get("judgement_model"):
            lines.append(f"- Judgement model: `{run_record['judgement_model']}`")
        if run_record.get("judgement_reasoning_effort"):
            lines.append(f"- Judgement reasoning effort: `{run_record['judgement_reasoning_effort']}`")
        lines.append(f"- Episode Intelligence: `{run_record.get('episode_intel_mode', 'heuristic')}`")
        lines.append(f"- Guardrail mode: `{run_record.get('guardrail_mode', 'advisory')}`")
        lines.append(f"- Seed: `{run_record.get('seed')}`")
        lines.append(f"- Episode mode: `{run_record.get('episode_mode')}`")
        lines.append(f"- Story version: `{run_record.get('story_version')}`")
        lines.append(f"- Persona-episodes evaluated: {reaction_calls}")
        lines.append(f"- Panel model: {INDIA_ENGLISH_COHORT_CARD['model']}")
        lines.append(f"- Market: {INDIA_ENGLISH_COHORT_CARD['market']}")
        lines.append(f"- Caveat: {verdict.get('calibration_warning', '')}")
        for gap in insights.get("model_gaps", []):
            lines.append(f"- Model gap: {gap}")

    def _append_theme(self, lines: list[str], label: str, rows: list[dict[str, Any]]) -> None:
        lines.append(f"### {label}")
        if not rows:
            lines.append("- No data.")
            return
        for row in rows[:5]:
            lines.append(f"- {row['count']} agents: {row['text']}")


class OpenAIReportWritingAgent:
    """LLM report writer that turns structured simulator outputs into a concise report."""

    agent_name = LLM_REPORT_AGENT_NAME

    def __init__(
        self,
        *,
        model: str = "gpt-5.6-luna",
        seed: int = 7,
        timeout_seconds: int = 120,
        reasoning_effort: str = "medium",
    ) -> None:
        if reasoning_effort not in {"minimal", "low", "medium", "high"}:
            raise ValueError(f"Unknown reasoning effort '{reasoning_effort}'")
        self.model = model
        self.seed = seed
        self.timeout_seconds = timeout_seconds
        self.reasoning_effort = reasoning_effort

    def render(self, run_record: dict[str, Any], verdict: dict[str, Any]) -> str:
        api_key = openai_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when using --report-mode llm")

        last_model_error: RuntimeError | None = None
        for candidate_model in openai_model_candidates(self.model):
            try:
                markdown = self._render_once(api_key, candidate_model, run_record, verdict)
                self.model = candidate_model
                return markdown
            except RuntimeError as exc:
                if not _is_model_availability_error(str(exc)):
                    raise
                last_model_error = exc
        if last_model_error:
            raise last_model_error
        raise RuntimeError("No OpenAI model candidates configured")

    def _render_once(
        self,
        api_key: str,
        model: str,
        run_record: dict[str, Any],
        verdict: dict[str, Any],
    ) -> str:
        request_payload = {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are the report-writing agent for an audience simulation harness. "
                        "Write a concise markdown decision report for story editors. Use only "
                        "the structured data provided. Do not invent facts, real-world audience "
                        "numbers, or unsupported causes. No motivational language, no fluff, "
                        "no generic advice. Prioritize what broke retention, which segments "
                        "reacted, what agents said, and what to rewrite next."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        _report_prompt_payload(run_record, verdict),
                        ensure_ascii=False,
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "audience_report",
                    "schema": REPORT_SCHEMA,
                    "strict": True,
                }
            },
            "reasoning": {"effort": self.reasoning_effort},
            "store": False,
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
            raise RuntimeError(f"Model returned non-JSON report output: {text[:500]}") from exc
        markdown = str(result.get("markdown", "")).strip()
        if not markdown:
            raise RuntimeError("Model returned an empty report")
        return _ensure_report_footer(markdown, run_record, verdict)


def _report_prompt_payload(run_record: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    insights = verdict.get("insights", {})
    return {
        "instructions": {
            "required_sections": [
                "1. Verdict Card",
                "2. Retention by Need-Region",
                "3. Episode Table",
                "4. Drop-Beat Inspector",
                "5. Paywall Map",
                "6. Expectation Scorecard",
                "7. Panel Voice",
                "8. Editorial Actions",
                "9. Methods Footer",
            ],
            "style": [
                "Markdown only.",
                "Use short bullets and one metrics table.",
                "Do not include an intro paragraph.",
                "Do not explain what an audience simulator is.",
                "Tie every claim to a provided metric, segment read, or agent opinion bucket.",
                "Use felt_emotions, emotion_shifts, and judgement_bridges when explaining pass/drop behavior.",
                "Use retained index values for report prose; raw absolutes can remain in tables.",
                "Do not mention absent Kaveri entities like career, office, professional rival, or status momentum unless present in the provided text.",
                "Keep the report under 1,400 words.",
            ],
        },
        "run": {
            "run_id": verdict.get("run_id"),
            "story_path": run_record.get("story_path"),
            "cohort": verdict.get("cohort"),
            "population_size": verdict.get("population_size"),
            "episode_count": verdict.get("episode_count"),
            "engine": run_record.get("engine"),
            "engine_kind": run_record.get("engine_kind"),
            "persona_mode": run_record.get("persona_mode"),
            "reaction_model": run_record.get("reaction_model"),
            "reaction_reasoning_effort": run_record.get("reaction_reasoning_effort"),
            "persona_model": run_record.get("persona_model"),
            "persona_reasoning_effort": run_record.get("persona_reasoning_effort"),
            "report_model": run_record.get("report_model"),
            "report_reasoning_effort": run_record.get("report_reasoning_effort"),
            "beat_generator": run_record.get("beat_generator"),
            "beat_model": run_record.get("beat_model"),
            "beat_reasoning_effort": run_record.get("beat_reasoning_effort"),
            "judgement_mode": run_record.get("judgement_mode"),
            "judgement_model": run_record.get("judgement_model"),
            "judgement_reasoning_effort": run_record.get("judgement_reasoning_effort"),
            "episode_intel_mode": run_record.get("episode_intel_mode"),
            "guardrail_mode": run_record.get("guardrail_mode"),
            "seed": run_record.get("seed"),
        },
        "verdict": {
            "recommendation": verdict.get("recommendation"),
            "confidence": verdict.get("confidence"),
            "final_retention_from_start": verdict.get("final_retention_from_start"),
            "mean_continue_rate": verdict.get("mean_continue_rate"),
            "mean_craving_delta": verdict.get("mean_craving_delta"),
            "mean_prediction_entropy": verdict.get("mean_prediction_entropy"),
            "weakest_episode": verdict.get("weakest_episode"),
            "paywall_candidate": verdict.get("paywall_candidate"),
            "calibration_warning": verdict.get("calibration_warning"),
        },
        "episode_metrics": verdict.get("episode_metrics", []),
        "insights": {
            "headline": insights.get("headline"),
            "retention_shape": insights.get("retention_shape", []),
            "region_retention_curves": insights.get("region_retention_curves", []),
            "microsegment_retention": insights.get("microsegment_retention", []),
            "episode_intelligence": _compact_episode_intelligence_map(insights.get("episode_intelligence", {})),
            "episode_table": insights.get("episode_table", []),
            "drop_beat_inspector": insights.get("drop_beat_inspector", []),
            "llm_heuristic_bridge": insights.get("llm_heuristic_bridge", {}),
            "segment_sensitivity": insights.get("segment_sensitivity", []),
            "survivor_skew": insights.get("survivor_skew", {}),
            "paywall_diagnostics": insights.get("paywall_diagnostics", []),
            "paywall_map": insights.get("paywall_map", []),
            "expectation_scorecard": insights.get("expectation_scorecard", []),
            "episode_insights": _compact_episode_insights(insights.get("episode_insights", [])),
            "agent_opinion_themes": insights.get("agent_opinion_themes", {}),
            "weighted_agent_voice": insights.get("weighted_agent_voice", {}),
            "editorial_actions": insights.get("editorial_actions", []),
            "model_gaps": insights.get("model_gaps", []),
        },
    }


def _compact_episode_insights(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted = []
    for row in rows:
        compacted.append(
            {
                "episode_no": row.get("episode_no"),
                "title": row.get("title"),
                "active_before": row.get("active_before"),
                "continue_rate": row.get("continue_rate"),
                "retention_from_start": row.get("retention_from_start"),
                "drop_count": row.get("drop_count"),
                "pay_rate": row.get("pay_rate"),
                "avg_craving_delta": row.get("avg_craving_delta"),
                "top_drop_beat": row.get("top_drop_beat"),
                "top_drop_beat_excerpt": row.get("top_drop_beat_excerpt"),
                "top_drop_beat_label": row.get("top_drop_beat_label"),
                "top_drop_beat_lines": row.get("top_drop_beat_lines"),
                "drop_reasons": row.get("drop_reasons", []),
                "continue_reasons": row.get("continue_reasons", []),
                "felt_emotions": row.get("felt_emotions", []),
                "emotion_shifts": row.get("emotion_shifts", []),
                "judgement_bridges": row.get("judgement_bridges", []),
                "pay_objections": row.get("pay_objections", []),
                "signal_diagnosis": row.get("signal_diagnosis", []),
                "read": row.get("read"),
            }
        )
    return compacted


def _compact_episode_intelligence_map(items: dict[str, Any] | dict[int, Any]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for _, item in sorted(items.items(), key=lambda pair: int(pair[0])):
        beat_rows = item.get("beat_table", [])
        risk_beats = sorted(
            (
                row
                for row in beat_rows
                if row.get("churn_risk") != "none" or row.get("removable")
            ),
            key=lambda row: float(row.get("risk_score", 0.0)),
            reverse=True,
        )[:4]
        compacted.append(
            {
                "episode_no": item.get("episode_no"),
                "title": item.get("title"),
                "beat_source": item.get("beat_source"),
                "narrative_anatomy": item.get("narrative_anatomy"),
                "ending": item.get("ending"),
                "top_cohort_fit": item.get("cohort_fit_rankings", [])[:3],
                "weakest_cohort_fit": item.get("cohort_fit_rankings", [])[-2:],
                "risk_beats": [
                    {
                        "beat_id": row.get("beat_id"),
                        "label": row.get("label"),
                        "line_start": row.get("line_start"),
                        "line_end": row.get("line_end"),
                        "generator": row.get("generator"),
                        "purpose": row.get("purpose"),
                        "heuristic_purpose": row.get("heuristic_purpose"),
                        "churn_risk": row.get("churn_risk"),
                        "risk_score": row.get("risk_score"),
                        "note": row.get("note"),
                        "llm_audience_decision_risk": row.get("llm_audience_decision_risk"),
                        "llm_risk_reason": row.get("llm_risk_reason"),
                        "llm_evidence_quote": row.get("llm_evidence_quote"),
                        "craving_effect": row.get("craving_effect"),
                        "quote": row.get("quote"),
                    }
                    for row in risk_beats
                ],
                "drop_science": item.get("drop_science"),
            }
        )
    return compacted


def _ensure_report_footer(markdown: str, run_record: dict[str, Any], verdict: dict[str, Any]) -> str:
    text = markdown.strip()
    if not text.startswith("# "):
        text = f"# {_story_title(run_record)} - Audience Simulation Report\n\n" + text
    audit_lines = [
        f"- Run: `{verdict.get('run_id')}`",
        f"- Reaction model: `{run_record.get('reaction_model')}`",
        f"- Reaction reasoning effort: `{run_record.get('reaction_reasoning_effort')}`",
        f"- Persona model: `{run_record.get('persona_model')}`",
        f"- Persona reasoning effort: `{run_record.get('persona_reasoning_effort')}`",
        f"- Report model: `{run_record.get('report_model')}`",
        f"- Report reasoning effort: `{run_record.get('report_reasoning_effort')}`",
        f"- Beat generator: `{run_record.get('beat_generator')}`",
        f"- Beat model: `{run_record.get('beat_model')}`",
        f"- Beat reasoning effort: `{run_record.get('beat_reasoning_effort')}`",
        f"- Judgement mode: `{run_record.get('judgement_mode')}`",
        f"- Judgement model: `{run_record.get('judgement_model')}`",
        f"- Judgement reasoning effort: `{run_record.get('judgement_reasoning_effort')}`",
        f"- Episode Intelligence: `{run_record.get('episode_intel_mode')}`",
        f"- Guardrail mode: `{run_record.get('guardrail_mode')}`",
    ]
    if "## 9. Methods Footer" not in text and "## Audit" not in text:
        text += (
            "\n\n## 9. Methods Footer\n\n"
            f"- Report writer: `{LLM_REPORT_AGENT_NAME}`\n"
            f"- Cohort: {verdict.get('cohort')}\n"
            f"- Population: {verdict.get('population_size')} synthetic listeners\n"
            f"- Caveat: {verdict.get('calibration_warning', '')}\n"
        )
    if "Reaction model:" not in text:
        text += "\n\nAudit metadata:\n\n" + "\n".join(audit_lines)
    return text + "\n"


def _extract_output_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                return content["text"]
    raise RuntimeError(f"Could not find model output text in response: {json.dumps(data)[:500]}")


def _request_seed(seed: int, run_id: str) -> int:
    digest = hashlib.sha256(f"{seed}:report:{run_id}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % 2_000_000_000


def _story_title(run_record: dict[str, Any]) -> str:
    story_path = str(run_record.get("story_path") or "story")
    return Path(story_path).stem.replace("_", " ").replace("-", " ").title()


def _strongest_region(insights: dict[str, Any]) -> str:
    curves = insights.get("region_retention_curves") or []
    if not curves:
        return "unavailable"
    ranked = sorted(
        curves,
        key=lambda row: (
            row.get("points", [{}])[-1].get("retained_index", 0.0) if row.get("points") else 0.0,
            row.get("start_count", 0),
        ),
        reverse=True,
    )
    strongest = ranked[0]
    final = strongest.get("points", [{}])[-1].get("retained_index", 0.0) if strongest.get("points") else 0.0
    return f"{strongest.get('region', 'unknown')} ({final:.1f})"


def _is_model_availability_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "model" in lowered
        and any(term in lowered for term in ["not found", "does not exist", "not exist", "unsupported"])
    ) or "invalid model" in lowered
