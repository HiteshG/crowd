from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
WEBAPP_DIR = ROOT / "webapp"
UPLOAD_DIR = WEBAPP_DIR / "uploads"
RUNS_DIR = ROOT / "runs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

app = FastAPI(title="Crowd — Audience Simulator")


class RunConfig(BaseModel):
    script_text: str = Field(..., min_length=32)
    filename: str = "script.md"
    personas: int = Field(25, ge=1, le=500)
    seed: int = 7
    engine: str = "heuristic"                # heuristic | llm
    persona_mode: str = "seed"               # seed | llm
    report_mode: str = "deterministic"       # deterministic | llm
    judgement_mode: str = "auto"             # auto | llm | off
    episode_intel: str = "auto"              # auto | llm | heuristic | off
    episode_mode: str = "headings"           # headings | separator
    guardrail_mode: str = "advisory"         # advisory | override | off


_running: dict[str, subprocess.Popen] = {}


@app.get("/")
async def home():
    return FileResponse(WEBAPP_DIR / "index.html")


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/api/runs")
async def start_run(cfg: RunConfig):
    run_id = f"web-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "_", cfg.filename or "script.md")[:80] or "script.md"
    script_path = UPLOAD_DIR / f"{run_id}__{safe_filename}"
    script_path.write_text(cfg.script_text, encoding="utf-8")

    cmd = [
        sys.executable,
        "-u",
        "-m",
        "audience_simulator",
        "run",
        str(script_path),
        "--personas", str(cfg.personas),
        "--seed", str(cfg.seed),
        "--engine", cfg.engine,
        "--persona-mode", cfg.persona_mode,
        "--report-mode", cfg.report_mode,
        "--judgement-mode", cfg.judgement_mode,
        "--episode-intel", cfg.episode_intel,
        "--episode-mode", cfg.episode_mode,
        "--guardrail-mode", cfg.guardrail_mode,
        "--out", str(RUNS_DIR),
        "--run-id", run_id,
    ]

    log_path = RUNS_DIR / f"{run_id}.stderr.log"
    log_handle = log_path.open("wb")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=log_handle,
            cwd=ROOT,
            env=os.environ.copy(),
        )
    except FileNotFoundError as exc:
        log_handle.close()
        raise HTTPException(status_code=500, detail=f"Could not launch simulator: {exc}") from exc
    _running[run_id] = proc

    return {"run_id": run_id, "config": cfg.model_dump()}


async def _tail_progress(run_id: str) -> AsyncIterator[str]:
    progress_path = RUNS_DIR / run_id / "progress.jsonl"
    verdict_path = RUNS_DIR / run_id / "verdict.json"
    stderr_log = RUNS_DIR / f"{run_id}.stderr.log"

    last_size = 0
    finished = False
    started_at = time.time()

    # Small opening event so the client knows the stream is live.
    yield f"event: hello\ndata: {json.dumps({'run_id': run_id})}\n\n"

    while not finished:
        proc = _running.get(run_id)
        proc_alive = proc is None or proc.poll() is None

        if progress_path.exists():
            data = progress_path.read_bytes()
            if len(data) > last_size:
                chunk = data[last_size:].decode("utf-8", "ignore")
                last_size = len(data)
                for line in chunk.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    yield f"data: {line}\n\n"
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if payload.get("event") == "run_finished":
                        finished = True
                        break

        if finished:
            break

        if not proc_alive:
            # Process died without a run_finished event — surface stderr.
            tail = ""
            if stderr_log.exists():
                try:
                    raw = stderr_log.read_text(encoding="utf-8", errors="replace")
                    tail = raw[-2000:]
                except OSError:
                    tail = ""
            yield "event: failure\ndata: " + json.dumps({"stderr_tail": tail}) + "\n\n"
            return

        if time.time() - started_at > 3600:
            yield "event: failure\ndata: " + json.dumps({"message": "timed out waiting for progress"}) + "\n\n"
            return

        await asyncio.sleep(0.35)

    # Give the runner a beat to finish writing verdict.json.
    for _ in range(40):
        if verdict_path.exists():
            break
        await asyncio.sleep(0.15)

    yield "event: done\ndata: " + json.dumps({"has_verdict": verdict_path.exists()}) + "\n\n"


@app.get("/api/runs/{run_id}/events")
async def stream_events(run_id: str):
    _validate_run_id(run_id)
    return StreamingResponse(
        _tail_progress(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/runs/{run_id}/status")
async def get_status(run_id: str):
    _validate_run_id(run_id)
    run_dir = RUNS_DIR / run_id
    progress = run_dir / "progress.jsonl"
    verdict = run_dir / "verdict.json"
    proc = _running.get(run_id)
    alive = proc is not None and proc.poll() is None
    events = 0
    if progress.exists():
        events = sum(1 for _ in progress.open("r", encoding="utf-8") if _.strip())
    return {
        "run_id": run_id,
        "alive": alive,
        "events": events,
        "has_verdict": verdict.exists(),
    }


@app.get("/api/runs/{run_id}/summary")
async def get_summary(run_id: str):
    _validate_run_id(run_id)
    run_dir = RUNS_DIR / run_id
    verdict_path = run_dir / "verdict.json"
    metrics_path = run_dir / "metrics.json"
    if not verdict_path.exists():
        raise HTTPException(status_code=202, detail="Run not finished")
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else []
    insights = verdict.get("insights") or {}
    episode_intelligence = insights.get("episode_intelligence") or {}
    return JSONResponse({
        "run_id": run_id,
        "verdict": {
            "recommendation": verdict.get("recommendation"),
            "confidence": verdict.get("confidence"),
            "final_retention_from_start": verdict.get("final_retention_from_start"),
            "mean_continue_rate": verdict.get("mean_continue_rate"),
            "mean_craving_delta": verdict.get("mean_craving_delta"),
            "mean_prediction_entropy": verdict.get("mean_prediction_entropy"),
            "weakest_episode": verdict.get("weakest_episode"),
            "paywall_candidate": verdict.get("paywall_candidate"),
            "cohort": verdict.get("cohort"),
            "population_size": verdict.get("population_size"),
            "episode_count": verdict.get("episode_count"),
            "calibration_warning": verdict.get("calibration_warning"),
        },
        "metrics": metrics,
        "headline": insights.get("headline"),
        "retention_shape": insights.get("retention_shape"),
        "episode_intelligence_titles": {
            str(k): {"title": v.get("title"), "beat_source": v.get("beat_source")}
            for k, v in episode_intelligence.items()
        } if isinstance(episode_intelligence, dict) else {},
    })


@app.get("/api/runs/{run_id}/report")
async def get_report(run_id: str):
    _validate_run_id(run_id)
    report_path = RUNS_DIR / run_id / "report.md"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not available")
    return FileResponse(report_path, media_type="text/markdown", filename=f"{run_id}-report.md")


def _validate_run_id(run_id: str) -> None:
    if not RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id")


def main() -> None:
    import uvicorn

    host = os.environ.get("CROWD_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("CROWD_WEB_PORT", "8000"))
    uvicorn.run("webapp.server:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
