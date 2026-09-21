"""SQLite storage for code files, versions, and run history."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, workspace_dir: Path):
        workspace_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = workspace_dir / "monty.db"
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()
        self._import_existing_files(workspace_dir)

    def _migrate(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                name TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS file_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL REFERENCES files(name) ON DELETE CASCADE,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_versions_file ON file_versions(file_name, created_at DESC);
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                code TEXT NOT NULL,
                inputs TEXT NOT NULL DEFAULT '{}',
                output TEXT,
                success INTEGER NOT NULL,
                error TEXT,
                duration_ms INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER REFERENCES runs(id),
                file_name TEXT,
                function_name TEXT NOT NULL,
                args TEXT NOT NULL DEFAULT '[]',
                blob BLOB NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                resumed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_status ON snapshots(status, created_at DESC);
            CREATE TABLE IF NOT EXISTS function_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER REFERENCES runs(id),
                function_name TEXT NOT NULL,
                args TEXT NOT NULL DEFAULT '[]',
                result TEXT,
                logs TEXT NOT NULL DEFAULT '[]',
                duration_ms INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_function_logs_run ON function_logs(run_id);

            CREATE TABLE IF NOT EXISTS formulas (
                name TEXT PRIMARY KEY,
                expr TEXT NOT NULL,
                vars TEXT NOT NULL DEFAULT '[]',
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS formula_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                formula_name TEXT NOT NULL REFERENCES formulas(name) ON DELETE CASCADE,
                expr TEXT NOT NULL,
                vars TEXT NOT NULL DEFAULT '[]',
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_formula_versions ON formula_versions(formula_name, created_at DESC);
            CREATE TABLE IF NOT EXISTS formula_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER REFERENCES runs(id),
                formula_name TEXT NOT NULL,
                operation TEXT NOT NULL,
                args TEXT NOT NULL DEFAULT '{}',
                result TEXT,
                error TEXT,
                duration_ms INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_formula_logs_run ON formula_logs(run_id);
            CREATE INDEX IF NOT EXISTS idx_formula_logs_name ON formula_logs(formula_name, created_at DESC);
        """)

    def _import_existing_files(self, workspace_dir: Path):
        for py_file in sorted(workspace_dir.glob("*.py")):
            name = py_file.name
            if not self.get_file(name):
                content = py_file.read_text()
                now = _now()
                self._conn.execute(
                    "INSERT INTO files (name, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (name, content, now, now),
                )
        self._conn.commit()

    def list_files(self) -> list[str]:
        rows = self._conn.execute("SELECT name FROM files ORDER BY name").fetchall()
        return [r["name"] for r in rows]

    def get_file(self, name: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM files WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None

    def save_file(self, name: str, content: str) -> dict:
        now = _now()
        existing = self.get_file(name)
        if existing:
            # Save version before overwrite
            self._conn.execute(
                "INSERT INTO file_versions (file_name, content, created_at) VALUES (?, ?, ?)",
                (name, existing["content"], existing["updated_at"]),
            )
            self._conn.execute(
                "UPDATE files SET content = ?, updated_at = ? WHERE name = ?",
                (content, now, name),
            )
        else:
            self._conn.execute(
                "INSERT INTO files (name, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (name, content, now, now),
            )
        self._conn.commit()
        return {"name": name, "updated_at": now}

    def delete_file(self, name: str) -> bool:
        cur = self._conn.execute("DELETE FROM files WHERE name = ?", (name,))
        self._conn.commit()
        return cur.rowcount > 0

    def file_versions(self, name: str, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, content, created_at FROM file_versions WHERE file_name = ? ORDER BY created_at DESC LIMIT ?",
            (name, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_version(self, version_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT fv.*, f.name FROM file_versions fv JOIN files f ON f.name = fv.file_name WHERE fv.id = ?",
            (version_id,),
        ).fetchone()
        return dict(row) if row else None

    def log_run(self, *, file_name: str | None, code: str, inputs: dict[str, Any],
                output: Any, success: bool, error: str | None, duration_ms: int | None = None) -> int:
        now = _now()
        cur = self._conn.execute(
            "INSERT INTO runs (file_name, code, inputs, output, success, error, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (file_name, code, json.dumps(inputs, default=str), json.dumps(output, default=str),
             int(success), error, duration_ms, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_runs(self, limit: int = 50, file_name: str | None = None) -> list[dict]:
        if file_name:
            rows = self._conn.execute(
                "SELECT id, file_name, success, error, duration_ms, created_at FROM runs WHERE file_name = ? ORDER BY created_at DESC LIMIT ?",
                (file_name, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, file_name, success, error, duration_ms, created_at FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_run(self, run_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def save_snapshot(self, *, function_name: str, args: list, blob: bytes,
                      file_name: str | None = None, run_id: int | None = None) -> int:
        now = _now()
        cur = self._conn.execute(
            "INSERT INTO snapshots (run_id, file_name, function_name, args, blob, status, created_at) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (run_id, file_name, function_name, json.dumps(args, default=str), blob, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_snapshot(self, snapshot_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        return dict(row) if row else None

    def list_snapshots(self, status: str | None = "pending", limit: int = 50) -> list[dict]:
        if status:
            rows = self._conn.execute(
                "SELECT id, run_id, file_name, function_name, args, status, created_at, resumed_at FROM snapshots WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, run_id, file_name, function_name, args, status, created_at, resumed_at FROM snapshots ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def save_function_logs(self, run_id: int | None, logs: list[dict]) -> None:
        now = _now()
        for entry in logs:
            self._conn.execute(
                "INSERT INTO function_logs (run_id, function_name, args, result, logs, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, entry["function"], json.dumps(entry.get("args", []), default=str),
                 json.dumps(entry.get("result"), default=str),
                 json.dumps(entry.get("logs", []), default=str),
                 entry.get("duration_ms"), now),
            )
        self._conn.commit()

    def list_function_logs(self, run_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM function_logs WHERE run_id = ? ORDER BY id", (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def resolve_snapshot(self, snapshot_id: int, status: str = "resumed") -> bool:
        now = _now()
        cur = self._conn.execute(
            "UPDATE snapshots SET status = ?, resumed_at = ? WHERE id = ? AND status = 'pending'",
            (status, now, snapshot_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    # --- Formulas ---

    def list_formulas(self) -> list[dict]:
        rows = self._conn.execute("SELECT name, expr, vars, description, created_at, updated_at FROM formulas ORDER BY name").fetchall()
        return [{**dict(r), "vars": json.loads(r["vars"])} for r in rows]

    def get_formula(self, name: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM formulas WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["vars"] = json.loads(d["vars"])
        return d

    def save_formula(self, name: str, expr: str, vars: list[str], description: str = "") -> dict:
        now = _now()
        existing = self.get_formula(name)
        if existing:
            self._conn.execute(
                "INSERT INTO formula_versions (formula_name, expr, vars, description, created_at) VALUES (?, ?, ?, ?, ?)",
                (name, existing["expr"], json.dumps(existing["vars"]), existing["description"], existing["updated_at"]),
            )
            self._conn.execute(
                "UPDATE formulas SET expr = ?, vars = ?, description = ?, updated_at = ? WHERE name = ?",
                (expr, json.dumps(vars), description, now, name),
            )
        else:
            self._conn.execute(
                "INSERT INTO formulas (name, expr, vars, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, expr, json.dumps(vars), description, now, now),
            )
        self._conn.commit()
        return {"name": name, "updated_at": now}

    def delete_formula(self, name: str) -> bool:
        cur = self._conn.execute("DELETE FROM formulas WHERE name = ?", (name,))
        self._conn.commit()
        return cur.rowcount > 0

    def formula_versions(self, name: str, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, expr, vars, description, created_at FROM formula_versions WHERE formula_name = ? ORDER BY created_at DESC LIMIT ?",
            (name, limit),
        ).fetchall()
        return [{**dict(r), "vars": json.loads(r["vars"])} for r in rows]

    def log_formula_op(self, *, run_id: int | None, formula_name: str, operation: str,
                       args: dict[str, Any], result: Any = None, error: str | None = None,
                       duration_ms: int | None = None) -> int:
        now = _now()
        cur = self._conn.execute(
            "INSERT INTO formula_logs (run_id, formula_name, operation, args, result, error, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, formula_name, operation, json.dumps(args, default=str),
             json.dumps(result, default=str) if result is not None else None,
             error, duration_ms, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_formula_logs(self, formula_name: str | None = None, run_id: int | None = None, limit: int = 50) -> list[dict]:
        if run_id is not None:
            rows = self._conn.execute(
                "SELECT * FROM formula_logs WHERE run_id = ? ORDER BY id", (run_id,),
            ).fetchall()
        elif formula_name:
            rows = self._conn.execute(
                "SELECT * FROM formula_logs WHERE formula_name = ? ORDER BY created_at DESC LIMIT ?",
                (formula_name, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM formula_logs ORDER BY created_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self._conn.close()
