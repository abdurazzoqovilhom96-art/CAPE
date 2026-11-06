"""Tables (spec section 28): .csv, .md and .tex are generated from the same validated records.
Best values are marked only inside one comparable panel/table."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from cape.result_store import atomic_write_text


def _fmt(v, fmt: str | None) -> str:
    if v is None or v == "":
        return "-"
    if fmt and isinstance(v, (int, float)):
        try:
            return format(v, fmt)
        except (ValueError, TypeError):
            return str(v)
    return str(v)


def _tex_escape(s: str) -> str:
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                 ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\^{}")):
        s = s.replace(a, b)
    return s


def write_table(base: Path, rows: list[dict], columns: list[tuple], caption: str,
                best: dict | None = None) -> list[str]:
    """columns: (key, header, format) tuples. best: {key: "min"|"max"} marks the best numeric value."""
    base.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([c[0] for c in columns])
    for r in rows:
        w.writerow(["" if r.get(c[0]) is None else r.get(c[0]) for c in columns])
    atomic_write_text(base.with_suffix(".csv"), buf.getvalue())

    best_val = {}
    for key, mode in (best or {}).items():
        vals = [r.get(key) for r in rows if isinstance(r.get(key), (int, float))]
        if vals:
            best_val[key] = min(vals) if mode == "min" else max(vals)

    md = [f"**{caption}**", "", "| " + " | ".join(c[1] for c in columns) + " |",
          "|" + "|".join("---" for _ in columns) + "|"]
    tex = [r"\begin{table}[t]", r"\centering", r"\small", f"\\caption{{{_tex_escape(caption)}}}",
           r"\begin{tabular}{" + "l" * min(2, len(columns)) + "r" * max(0, len(columns) - 2) + "}", r"\hline",
           " & ".join(_tex_escape(c[1]) for c in columns) + r" \\", r"\hline"]
    for r in rows:
        cells_md, cells_tex = [], []
        for key, _h, fmt in (c if len(c) == 3 else (*c, None) for c in columns):
            s = _fmt(r.get(key), fmt)
            is_best = key in best_val and r.get(key) == best_val[key]
            cells_md.append(f"**{s}**" if is_best else s)
            cells_tex.append(f"\\textbf{{{_tex_escape(s)}}}" if is_best else _tex_escape(s))
        md.append("| " + " | ".join(cells_md) + " |")
        tex.append(" & ".join(cells_tex) + r" \\")
    if not rows:
        md.append("| " + " | ".join("-" for _ in columns) + " |")
        md.append("")
        md.append("_No validated records for this table._")
    tex += [r"\hline", r"\end{tabular}", r"\end{table}"]
    atomic_write_text(base.with_suffix(".md"), "\n".join(md) + "\n")
    atomic_write_text(base.with_suffix(".tex"), "\n".join(tex) + "\n")
    return [str(base.with_suffix(e)) for e in (".csv", ".md", ".tex")]
