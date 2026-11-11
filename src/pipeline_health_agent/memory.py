"""SQLite incident memory: past incidents retrieved as 'seen this before' context."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from pipeline_health_agent.paths import INCIDENTS_DB, ensure_data_dir


@dataclass(frozen=True)
class Incident:
    id: int
    pipeline: str
    diagnosis: str
    action: str
    decision: str
    result: str
    created_at: str

    def as_dict(self) -> dict[str, str | int]:
        return {
            "id": self.id,
            "pipeline": self.pipeline,
            "diagnosis": self.diagnosis,
            "action": self.action,
            "decision": self.decision,
            "result": self.result,
            "created_at": self.created_at,
        }


class IncidentStore:
    def __init__(self, db_path: str | None = None) -> None:
        ensure_data_dir()
        self.db_path = str(db_path or INCIDENTS_DB)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                action TEXT NOT NULL,
                decision TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def save(
        self,
        *,
        pipeline: str,
        diagnosis: str,
        action: str,
        decision: str,
        result: str,
    ) -> Incident:
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur = self._conn.execute(
            """
            INSERT INTO incidents (pipeline, diagnosis, action, decision, result, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (pipeline, diagnosis, action, decision, result, created_at),
        )
        self._conn.commit()
        return Incident(
            id=int(cur.lastrowid),
            pipeline=pipeline,
            diagnosis=diagnosis,
            action=action,
            decision=decision,
            result=result,
            created_at=created_at,
        )

    def lookup(self, pipeline: str, limit: int = 5) -> list[Incident]:
        rows = self._conn.execute(
            """
            SELECT id, pipeline, diagnosis, action, decision, result, created_at
            FROM incidents
            WHERE pipeline = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (pipeline, limit),
        ).fetchall()
        return [self._row(row) for row in rows]

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row(row: sqlite3.Row) -> Incident:
        return Incident(
            id=int(row["id"]),
            pipeline=str(row["pipeline"]),
            diagnosis=str(row["diagnosis"]),
            action=str(row["action"]),
            decision=str(row["decision"]),
            result=str(row["result"]),
            created_at=str(row["created_at"]),
        )
