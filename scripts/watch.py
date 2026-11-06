"""Live, read-only progress view of the running CAPE-Pins experiment (for a VS Code terminal).

    watch.cmd            # refresh every 5 s, Ctrl+C to quit
    watch.cmd --once     # print one snapshot

Shows the v2 / v2.1 pipeline steps, the active run's progress bar, failures, the task that is running
now, the last finished measurements and whether the timing worker process is alive (its CPU time
grows). Only reads files (run.sqlite is opened read-only); it never touches the experiment.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    import psutil
except ImportError:
    psutil = None

if os.name == "nt":
    os.system("")  # enable ANSI escape codes in the Windows console
G, Y, R, B, DIM, RST = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[2m", "\033[0m"


def ago(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    s = int((datetime.now(timezone.utc) - t).total_seconds())
    return f"{s} s oldin" if s < 120 else f"{s // 60} min oldin"


def steps_line(path: Path, title: str) -> str:
    if not path.exists():
        return f"{title}: {DIM}boshlanmagan{RST}"
    st = json.loads(path.read_text(encoding="utf-8")).get("steps", {})
    col = {"DONE": G, "RUNNING": Y, "FAILED": R, "BLOCKED": R}
    parts = [f"{col.get(v.get('status'), '')}{k}:{v.get('status')}{RST}" for k, v in st.items()]
    return f"{B}{title}{RST}  " + "  ".join(parts)


def running_step_tail(state: Path, logs: Path, n: int = 3) -> list[str]:
    """Last lines of the log of a RUNNING pipeline step (steps that are not run_all runs, e.g. attribution)."""
    if not state.exists():
        return []
    out = []
    for k, v in json.loads(state.read_text(encoding="utf-8")).get("steps", {}).items():
        log = logs / f"{k}.log"
        if v.get("status") != "RUNNING" or not log.exists():
            continue
        lines = [ln.rstrip() for ln in log.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        out.append(f"{Y}{k} logi{RST} ({ago(v.get('started_at'))} boshlangan):")
        out += [f"  {DIM}{ln[:150]}{RST}" for ln in lines[-n:]]
    return out


def active_run() -> Path | None:
    p = ROOT / "results" / "LATEST_RUN.txt"
    if not p.exists():
        return None
    rd = Path(p.read_text(encoding="utf-8").strip())
    return rd if rd.is_absolute() else ROOT / rd


def bar(done: int, total: int, width: int = 40) -> str:
    frac = done / total if total else 0
    n = int(round(frac * width))
    return f"[{G}{'#' * n}{RST}{'.' * (width - n)}] {done}/{total} ({100 * frac:.1f}%)"


def worker_alive() -> str:
    if psutil is None:
        return "psutil yo'q"
    best = None
    for p in psutil.process_iter(["name", "cpu_times", "memory_info"]):
        try:
            if "python" not in (p.info["name"] or "").lower():
                continue
            aff = p.cpu_affinity()
            cpu = p.info["cpu_times"].user + p.info["cpu_times"].system
            if len(aff) == 1 and (best is None or cpu > best[1]):
                best = (p.pid, cpu, aff[0], p.info["memory_info"].rss)
        except (psutil.Error, OSError):
            continue
    if not best:
        return f"{Y}bitta yadroga bog'langan worker topilmadi (qadam almashayotgan bo'lishi mumkin){RST}"
    return (f"{G}ishlayapti{RST}: PID {best[0]}, CPU {best[2]} ga bog'langan, CPU vaqti {best[1]:.0f} s, "
            f"xotira {best[3] >> 20} MiB")


def snapshot() -> str:
    out = [f"{B}CAPE-Pins jonli holat{RST}  {datetime.now().strftime('%H:%M:%S')}", "",
           steps_line(ROOT / "analysis" / "v2_state.json", "v2  "),
           steps_line(ROOT / "analysis" / "v21_state.json", "v2.1")]
    out += running_step_tail(ROOT / "analysis" / "v2_state.json", ROOT / "analysis" / "v2_logs")
    out += running_step_tail(ROOT / "analysis" / "v21_state.json", ROOT / "analysis" / "v21_logs")
    out.append("")
    rd = active_run()
    if rd is None or not (rd / "15_reports" / "progress.json").exists():
        out.append("faol run yo'q")
        return "\n".join(out)
    pr = json.loads((rd / "15_reports" / "progress.json").read_text(encoding="utf-8"))
    status = json.loads((rd / "run_manifest.json").read_text(encoding="utf-8")).get("status") \
        if (rd / "run_manifest.json").exists() else "?"
    out.append(f"{B}Run{RST}: {rd.name}  (holat: {status}, bosqich: {pr.get('stage')})")
    out.append(bar(pr.get("tasks_done", 0), pr.get("tasks_total", 0)))
    fails = pr.get("failures", 0)
    out.append(f"xato: {(R if fails else G)}{fails}{RST}   holatlar: {pr.get('task_counts')}   "
               f"oxirgi o'lchov: {ago(pr.get('last_commit'))}")
    out.append("worker: " + worker_alive())
    db = rd / "05_raw_metrics" / "run.sqlite"
    if db.exists():
        try:
            c = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=2)
            run = c.execute("select kind, sample_id, method_id, wrapper, repeat, updated_at from tasks "
                            "where status='RUNNING'").fetchall()
            for k, s, m, w, rep, upd in run:
                out.append(f"{Y}hozir{RST}: {m}{'' if w in (None, 'none') else '+' + w} | {s} | {k} #{rep} "
                           f"(boshlangan {ago(upd)})")
            last = c.execute("select method_id, wrapper, sample_id, encode_ns, total_bytes, status, committed_at "
                             "from measurements order by committed_at desc limit 8").fetchall()
            c.close()
            out += ["", f"{B}oxirgi o'lchovlar{RST}"]
            for m, w, s, en, tb, stt, at in last:
                enc = f"{en / 1e6:9.1f} ms" if en else "   memory  "
                col = G if stt == "OK" else R
                out.append(f"  {col}{stt:4}{RST} {enc}  {str(tb or ''):>10} B  {m}{'' if w in (None, 'none') else '+' + w}"
                           f"  {DIM}{s}  {ago(at)}{RST}")
        except sqlite3.Error as exc:
            out.append(f"{DIM}sqlite band ({exc}); keyingi yangilanishda qayta o'qiladi{RST}")
    out += ["", f"{DIM}Batafsil: {rd / '15_reports' / 'LIVE_REPORT_UZ.md'}  |  Ctrl+C - chiqish{RST}"]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--every", type=float, default=5.0)
    args = ap.parse_args(argv)
    if args.once:
        print(snapshot())
        return 0
    try:
        while True:
            text = snapshot()
            sys.stdout.write("\033[2J\033[H" + text + "\n")
            sys.stdout.flush()
            time.sleep(args.every)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
