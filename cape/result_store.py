"""Canonical run storage (spec section 36): 05_raw_metrics/run.sqlite through the stdlib
sqlite3 module. The controller is the only writer; a measurement and its task status are
committed in one transaction (synchronous=FULL, rollback journal on a local disk).
measurements.jsonl / results.csv are exports regenerated from this database."""

from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import os
import sqlite3
from pathlib import Path

MEASUREMENT_FIELDS = [
    "run_id", "task_id", "sample_id", "method_id", "method_version", "config_hash", "source_hash", "input_hash",
    "panel", "split", "repeat", "seed", "threads", "status", "reason", "original_dtype", "canonical_shape",
    "input_bytes", "payload_bytes", "metadata_bytes", "total_bytes", "label_bytes", "encode_ns", "decode_ns",
    "conversion_ns", "verify_ns", "peak_rss_bytes", "rss_measurement_mode", "lossless", "candidate_count_before",
    "candidate_count_after", "incidence_count", "component_count", "max_component_cc", "exact_cc_fraction",
    "ub_bytes", "lb_bytes", "certificate_scope", "certificate_valid", "bitstream_sha256", "bitstream_path",
    "stdout_log", "stderr_log",
]
EXTRA_FIELDS = [
    "wrapper", "family_id", "source_id", "macroblock_id", "is_synthetic", "label_format_actual", "encode_iterations",
    "encode_batch_ns", "decode_iterations", "decode_batch_ns", "timing_cpu", "dtype_adapter", "worker_pid",
    "committed_at", "extra_json",
]
ALL_FIELDS = MEASUREMENT_FIELDS + EXTRA_FIELDS

MEASUREMENT_STATUS = ("OK", "FAILED_LOSSLESS", "FAILED_BUILD", "UNAVAILABLE", "UNSUPPORTED_DTYPE", "OOM", "TIMEOUT",
                      "BLOCKED_DATA", "NOT_APPLICABLE", "INTERRUPTED")
TASK_STATUS = ("PENDING", "RUNNING", "COMMITTED", "FAILED", "SKIPPED")


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds")


def replace_with_retry(tmp: Path, dest: Path, attempts: int = 60, delay_s: float = 0.1) -> None:
    """os.replace that tolerates Windows sharing violations: while another process (an editor,
    a monitoring script) has the destination open for reading, the rename fails with
    PermissionError. The previous complete file stays in place until the rename succeeds."""
    import time

    for i in range(attempts):
        try:
            os.replace(tmp, dest)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(delay_s)


def atomic_write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    replace_with_retry(tmp, p)


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    replace_with_retry(tmp, p)


class ResultStore:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), isolation_level=None, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self._create()

    # ------------------------------------------------------------------ schema
    def _create(self) -> None:
        cols = ", ".join(f"{f} {'INTEGER' if f in _INT_FIELDS else 'REAL' if f in _REAL_FIELDS else 'TEXT'}"
                         for f in ALL_FIELDS if f != "task_id")
        self.db.executescript(f"""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS stages (name TEXT PRIMARY KEY, status TEXT NOT NULL, started_at TEXT,
                finished_at TEXT, inputs_hash TEXT, outputs_json TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, kind TEXT NOT NULL, sample_id TEXT NOT NULL,
                method_id TEXT NOT NULL, wrapper TEXT NOT NULL, panel TEXT NOT NULL, repeat INTEGER NOT NULL,
                split TEXT NOT NULL, ordinal INTEGER NOT NULL, resume_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, reason TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS measurements (measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL UNIQUE REFERENCES tasks(task_id), {cols});
            CREATE TABLE IF NOT EXISTS artifacts (artifact_id TEXT PRIMARY KEY, path TEXT NOT NULL, bytes INTEGER,
                sha256 TEXT, generator TEXT, source_measurements TEXT, created_at TEXT, status TEXT);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                level TEXT NOT NULL, message TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS tasks_status ON tasks(status, ordinal);
        """)

    def close(self) -> None:
        self.db.close()

    # -------------------------------------------------------------------- meta
    def set_meta(self, key: str, value) -> None:
        self.db.execute("INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, json.dumps(value)))

    def get_meta(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    # ------------------------------------------------------------------ stages
    def stage_start(self, name: str, inputs_hash: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO stages(name, status, started_at, inputs_hash) VALUES(?, 'RUNNING', ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET status='RUNNING', started_at=excluded.started_at, "
            "inputs_hash=excluded.inputs_hash, finished_at=NULL",
            (name, now_iso(), inputs_hash))

    def stage_finish(self, name: str, status: str, outputs=None, detail: str | None = None) -> None:
        self.db.execute("UPDATE stages SET status=?, finished_at=?, outputs_json=?, detail=? WHERE name=?",
                        (status, now_iso(), json.dumps(outputs) if outputs is not None else None, detail, name))

    def reset_stages_after(self, name: str, order: list[str]) -> None:
        """Starting a stage invalidates the recorded outcome of every later stage."""
        if name not in order:
            return
        later = order[order.index(name) + 1:]
        if later:
            self.db.execute(f"UPDATE stages SET status='PENDING', started_at=NULL, finished_at=NULL, detail=NULL "
                            f"WHERE name IN ({','.join('?' * len(later))})", later)

    def stages(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM stages ORDER BY started_at")]

    def stage_status(self, name: str) -> str | None:
        row = self.db.execute("SELECT status FROM stages WHERE name=?", (name,)).fetchone()
        return row["status"] if row else None

    # ------------------------------------------------------------------- tasks
    def add_tasks(self, tasks: list[dict]) -> int:
        before = self.db.total_changes
        self.db.execute("BEGIN")
        try:
            self.db.executemany(
                "INSERT OR IGNORE INTO tasks(task_id, kind, sample_id, method_id, wrapper, panel, repeat, split, "
                "ordinal, resume_key, status, updated_at) VALUES(:task_id, :kind, :sample_id, :method_id, :wrapper, "
                ":panel, :repeat, :split, :ordinal, :resume_key, 'PENDING', :updated_at)",
                [dict(t, updated_at=now_iso()) for t in tasks])
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return self.db.total_changes - before

    def tasks(self, status: str | None = None) -> list[dict]:
        if status:
            rows = self.db.execute("SELECT * FROM tasks WHERE status=? ORDER BY ordinal", (status,))
        else:
            rows = self.db.execute("SELECT * FROM tasks ORDER BY ordinal")
        return [dict(r) for r in rows]

    def task_counts(self) -> dict:
        return {r["status"]: r["n"] for r in self.db.execute("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status")}

    def set_task(self, task_id: str, status: str, reason: str | None = None, attempt: bool = False) -> None:
        assert status in TASK_STATUS
        self.db.execute(f"UPDATE tasks SET status=?, reason=?, updated_at=?{', attempts=attempts+1' if attempt else ''} "
                        "WHERE task_id=?", (status, reason, now_iso(), task_id))

    def reset_running(self) -> int:
        cur = self.db.execute("UPDATE tasks SET status='PENDING', reason='recovered after interruption', updated_at=? "
                              "WHERE status='RUNNING'", (now_iso(),))
        return cur.rowcount

    # ------------------------------------------------------------ measurements
    def commit_measurement(self, row: dict, task_status: str) -> int:
        """Atomically store one measurement and finish its task (COMMITTED or FAILED)."""
        if row.get("status") not in MEASUREMENT_STATUS:
            raise ValueError(f"invalid measurement status {row.get('status')!r}")
        if task_status not in ("COMMITTED", "FAILED", "SKIPPED"):
            raise ValueError(f"invalid final task status {task_status!r}")
        row = dict(row, committed_at=now_iso())
        fields = [f for f in ALL_FIELDS if f in row]
        values = [_to_sql(row[f]) for f in fields]
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.db.execute("SELECT measurement_id FROM measurements WHERE task_id=?",
                                       (row["task_id"],)).fetchone()
            if existing:
                raise ValueError(f"task {row['task_id']} already has a committed measurement (no duplicates)")
            cur = self.db.execute(f"INSERT INTO measurements({', '.join(fields)}) VALUES({', '.join('?' * len(fields))})",
                                  values)
            self.db.execute("UPDATE tasks SET status=?, reason=?, updated_at=? WHERE task_id=?",
                            (task_status, row.get("reason"), now_iso(), row["task_id"]))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return int(cur.lastrowid)

    def measurements(self, where: str = "", params: tuple = ()) -> list[dict]:
        sql = "SELECT * FROM measurements" + (f" WHERE {where}" if where else "") + " ORDER BY measurement_id"
        out = []
        for r in self.db.execute(sql, params):
            d = dict(r)
            d["lossless"] = None if d["lossless"] is None else bool(d["lossless"])
            d["certificate_valid"] = None if d["certificate_valid"] is None else bool(d["certificate_valid"])
            d["is_synthetic"] = None if d["is_synthetic"] is None else bool(d["is_synthetic"])
            out.append(d)
        return out

    def count_measurements(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0])

    # ----------------------------------------------------------- events/artifacts
    def event(self, level: str, message: str) -> None:
        self.db.execute("INSERT INTO events(at, level, message) VALUES(?, ?, ?)", (now_iso(), level, message))

    def events(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM events ORDER BY id")]

    def record_artifact(self, artifact_id: str, path: str, nbytes: int, sha256: str, generator: str,
                        source_measurements: list[int], status: str) -> None:
        self.db.execute(
            "INSERT INTO artifacts VALUES(?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(artifact_id) DO UPDATE SET "
            "path=excluded.path, bytes=excluded.bytes, sha256=excluded.sha256, generator=excluded.generator, "
            "source_measurements=excluded.source_measurements, created_at=excluded.created_at, status=excluded.status",
            (artifact_id, path, nbytes, sha256, generator, json.dumps(source_measurements), now_iso(), status))

    def artifacts(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM artifacts ORDER BY artifact_id")]

    # ----------------------------------------------------------------- exports
    def export_jsonl(self, path: str | Path) -> int:
        rows = self.measurements()
        atomic_write_text(path, "".join(json.dumps({k: r.get(k) for k in ["measurement_id"] + ALL_FIELDS},
                                                   sort_keys=False) + "\n" for r in rows))
        return len(rows)

    def export_csv(self, path: str | Path, rows: list[dict] | None = None) -> int:
        rows = self.measurements() if rows is None else rows
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["measurement_id"] + ALL_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in ["measurement_id"] + ALL_FIELDS})
        atomic_write_text(path, buf.getvalue())
        return len(rows)

    def backup(self, path: str | Path) -> None:
        """Consistent snapshot (sqlite backup API) for release packaging."""
        dest = sqlite3.connect(str(path))
        with dest:
            self.db.backup(dest)
        dest.close()


_INT_FIELDS = {"repeat", "seed", "threads", "input_bytes", "payload_bytes", "metadata_bytes", "total_bytes",
               "label_bytes", "encode_ns", "decode_ns", "conversion_ns", "verify_ns", "peak_rss_bytes", "lossless",
               "candidate_count_before", "candidate_count_after", "incidence_count", "component_count",
               "max_component_cc", "ub_bytes", "lb_bytes", "certificate_valid", "is_synthetic", "encode_iterations",
               "encode_batch_ns", "decode_iterations", "decode_batch_ns", "timing_cpu", "worker_pid"}
_REAL_FIELDS = {"exact_cc_fraction"}


def _to_sql(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    return v
