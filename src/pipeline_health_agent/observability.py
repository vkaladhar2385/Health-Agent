"""Local tracing: steps, tool calls, tokens, estimated cost, latency + HTML dashboard."""

from __future__ import annotations

import html
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from pipeline_health_agent.paths import DATA_DIR, ensure_data_dir

TRACE_DB = DATA_DIR / "traces.sqlite"
DASHBOARD_HTML = DATA_DIR / "dashboard.html"

# Rough public list prices (USD per 1M tokens). Good enough for demos.
PRICE_PER_MTOK = {
    "claude-sonnet-5": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.5, "output": 10.0},
}

_current_run: ContextVar[str | None] = ContextVar("pha_run_id", default=None)
_current_step: ContextVar[str | None] = ContextVar("pha_step", default=None)


@dataclass
class RunSummary:
    run_id: str
    pipeline: str
    fault: str
    model: str
    started_at: str
    ended_at: str | None
    latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    status: str


class TraceStore:
    def __init__(self, db_path: str | None = None) -> None:
        ensure_data_dir()
        self.db_path = str(db_path or TRACE_DB)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                pipeline TEXT NOT NULL,
                fault TEXT NOT NULL,
                model TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                latency_ms REAL DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS spans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                step TEXT NOT NULL,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0,
                detail TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            """
        )
        self._conn.commit()

    def start_run(self, *, pipeline: str, fault: str, model: str, run_id: str | None = None) -> str:
        rid = run_id or str(uuid.uuid4())
        now = _utcnow()
        self._conn.execute(
            """
            INSERT INTO runs (run_id, pipeline, fault, model, started_at, status)
            VALUES (?, ?, ?, ?, ?, 'running')
            """,
            (rid, pipeline, fault, model, now),
        )
        self._conn.commit()
        _current_run.set(rid)
        return rid

    def end_run(self, run_id: str, status: str = "completed") -> None:
        started = self._conn.execute(
            "SELECT started_at, input_tokens, output_tokens, estimated_cost_usd FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if not started:
            return
        ended = _utcnow()
        latency = _elapsed_ms(started["started_at"], ended)
        self._conn.execute(
            """
            UPDATE runs
            SET ended_at = ?, latency_ms = ?, status = ?
            WHERE run_id = ?
            """,
            (ended, latency, status, run_id),
        )
        self._conn.commit()

    def add_span(
        self,
        *,
        kind: str,
        name: str,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        detail: dict[str, Any] | None = None,
        run_id: str | None = None,
        step: str | None = None,
        model: str | None = None,
    ) -> None:
        rid = run_id or _current_run.get()
        if not rid:
            return
        cost = estimate_cost(model or "", input_tokens, output_tokens)
        self._conn.execute(
            """
            INSERT INTO spans (
                run_id, step, kind, name, started_at, latency_ms,
                input_tokens, output_tokens, estimated_cost_usd, detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid,
                step or _current_step.get() or "",
                kind,
                name,
                _utcnow(),
                latency_ms,
                input_tokens,
                output_tokens,
                cost,
                json.dumps(detail or {}),
            ),
        )
        self._conn.execute(
            """
            UPDATE runs
            SET input_tokens = input_tokens + ?,
                output_tokens = output_tokens + ?,
                estimated_cost_usd = estimated_cost_usd + ?
            WHERE run_id = ?
            """,
            (input_tokens, output_tokens, cost, rid),
        )
        self._conn.commit()

    def recent_runs(self, limit: int = 20) -> list[RunSummary]:
        rows = self._conn.execute(
            """
            SELECT run_id, pipeline, fault, model, started_at, ended_at, latency_ms,
                   input_tokens, output_tokens, estimated_cost_usd, status
            FROM runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            RunSummary(
                run_id=str(r["run_id"]),
                pipeline=str(r["pipeline"]),
                fault=str(r["fault"]),
                model=str(r["model"]),
                started_at=str(r["started_at"]),
                ended_at=str(r["ended_at"]) if r["ended_at"] else None,
                latency_ms=float(r["latency_ms"] or 0),
                input_tokens=int(r["input_tokens"] or 0),
                output_tokens=int(r["output_tokens"] or 0),
                estimated_cost_usd=float(r["estimated_cost_usd"] or 0),
                status=str(r["status"]),
            )
            for r in rows
        ]

    def spans_for(self, run_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT step, kind, name, latency_ms, input_tokens, output_tokens,
                   estimated_cost_usd, detail, started_at
            FROM spans WHERE run_id = ? ORDER BY id
            """,
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()


_STORE: TraceStore | None = None


def get_trace_store() -> TraceStore:
    global _STORE
    if _STORE is None:
        _STORE = TraceStore()
    return _STORE


def set_step(step: str) -> None:
    _current_step.set(step)


def current_run_id() -> str | None:
    return _current_run.get()


@contextmanager
def timed_span(kind: str, name: str, **detail: Any) -> Iterator[dict[str, Any]]:
    meta: dict[str, Any] = {"input_tokens": 0, "output_tokens": 0, "model": detail.get("model")}
    started = time.perf_counter()
    try:
        yield meta
    finally:
        latency = (time.perf_counter() - started) * 1000
        get_trace_store().add_span(
            kind=kind,
            name=name,
            latency_ms=latency,
            input_tokens=int(meta.get("input_tokens") or 0),
            output_tokens=int(meta.get("output_tokens") or 0),
            detail={k: v for k, v in detail.items() if k != "model"},
            model=str(meta.get("model") or detail.get("model") or ""),
        )


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = PRICE_PER_MTOK.get(model) or {"input": 3.0, "output": 15.0}
    return (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices["output"]


def write_dashboard(path: str | None = None) -> str:
    store = get_trace_store()
    runs = store.recent_runs(30)
    out = path or str(DASHBOARD_HTML)
    rows = []
    for run in runs:
        rows.append(
            "<tr>"
            f"<td>{html.escape(run.started_at)}</td>"
            f"<td><code>{html.escape(run.run_id[:8])}</code></td>"
            f"<td>{html.escape(run.pipeline)}</td>"
            f"<td>{html.escape(run.fault)}</td>"
            f"<td>{html.escape(run.model)}</td>"
            f"<td>{run.latency_ms:,.0f}</td>"
            f"<td>{run.input_tokens + run.output_tokens}</td>"
            f"<td>${run.estimated_cost_usd:.4f}</td>"
            f"<td>{html.escape(run.status)}</td>"
            "</tr>"
        )
    total_cost = sum(r.estimated_cost_usd for r in runs)
    avg_latency = (sum(r.latency_ms for r in runs) / len(runs)) if runs else 0.0
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Pipeline Health Agent — Run Dashboard</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 2rem; background: #f7f4ef; color: #1c1917; }}
    h1 {{ font-size: 1.6rem; margin-bottom: 0.25rem; }}
    .sub {{ color: #57534e; margin-bottom: 1.5rem; }}
    .cards {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; }}
    .card {{ background: white; border: 1px solid #d6d3d1; padding: 1rem 1.25rem; min-width: 10rem; }}
    .card b {{ display: block; font-size: 1.3rem; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ border: 1px solid #d6d3d1; padding: 0.45rem 0.6rem; text-align: left; font-size: 0.92rem; }}
    th {{ background: #e7e5e4; }}
    code {{ font-size: 0.85rem; }}
  </style>
</head>
<body>
  <h1>Pipeline Health Agent — observability</h1>
  <p class="sub">Local trace store (no Docker). Cost is estimated from token usage.</p>
  <div class="cards">
    <div class="card"><span>Runs</span><b>{len(runs)}</b></div>
    <div class="card"><span>Avg latency</span><b>{avg_latency:,.0f} ms</b></div>
    <div class="card"><span>Est. total cost</span><b>${total_cost:.4f}</b></div>
  </div>
  <table>
    <thead>
      <tr>
        <th>Started</th><th>Run</th><th>Pipeline</th><th>Fault</th><th>Model</th>
        <th>Latency (ms)</th><th>Tokens</th><th>Est. cost</th><th>Status</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows) if rows else '<tr><td colspan="9">No runs yet. Run <code>uv run pha diagnose --pipeline egress --decision approve</code>.</td></tr>'}
    </tbody>
  </table>
</body>
</html>
"""
    Path(out).write_text(page, encoding="utf-8")
    return out


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _elapsed_ms(started_at: str, ended_at: str) -> float:
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
    try:
        start = datetime.strptime(started_at, fmt)
        end = datetime.strptime(ended_at, fmt)
        return (end - start).total_seconds() * 1000
    except ValueError:
        return 0.0
