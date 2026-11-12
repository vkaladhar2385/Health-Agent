"""Audit log: who approved or rejected which write action, and when."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from pipeline_health_agent.paths import DATA_DIR, ensure_data_dir

AUDIT_DB = DATA_DIR / "audit.sqlite"


@dataclass(frozen=True)
class AuditEntry:
    id: int
    thread_id: str
    actor: str
    pipeline: str
    action: str
    decision: str
    reason: str
    created_at: str

    def as_dict(self) -> dict[str, str | int]:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "actor": self.actor,
            "pipeline": self.pipeline,
            "action": self.action,
            "decision": self.decision,
            "reason": self.reason,
            "created_at": self.created_at,
        }


class AuditLog:
    def __init__(self, db_path: str | None = None) -> None:
        ensure_data_dir()
        self.db_path = str(db_path or AUDIT_DB)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                pipeline TEXT NOT NULL,
                action TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def record(
        self,
        *,
        thread_id: str,
        pipeline: str,
        action: str,
        decision: str,
        reason: str = "",
        actor: str | None = None,
    ) -> AuditEntry:
        who = actor or current_actor()
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur = self._conn.execute(
            """
            INSERT INTO approvals (thread_id, actor, pipeline, action, decision, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (thread_id, who, pipeline, action, decision, reason, created_at),
        )
        self._conn.commit()
        return AuditEntry(
            id=int(cur.lastrowid),
            thread_id=thread_id,
            actor=who,
            pipeline=pipeline,
            action=action,
            decision=decision,
            reason=reason,
            created_at=created_at,
        )

    def recent(self, limit: int = 20) -> list[AuditEntry]:
        rows = self._conn.execute(
            """
            SELECT id, thread_id, actor, pipeline, action, decision, reason, created_at
            FROM approvals
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            AuditEntry(
                id=int(r["id"]),
                thread_id=str(r["thread_id"]),
                actor=str(r["actor"]),
                pipeline=str(r["pipeline"]),
                action=str(r["action"]),
                decision=str(r["decision"]),
                reason=str(r["reason"]),
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()


def current_actor() -> str:
    return (
        os.environ.get("PHA_ACTOR", "").strip()
        or os.environ.get("USERNAME", "").strip()
        or os.environ.get("USER", "").strip()
        or "unknown"
    )
