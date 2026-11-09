"""j0126 cluster sensitivity for the manuscript's principal comparisons (CAPE vs corrected pins_opt and vs
pins_fast): the registered analysis uses 33 clusters (one per volume); two pairs of volumes overlap spatially, so we
repeat the paired cluster bootstrap with the overlapping pairs merged (31 clusters). Uses the project's own
bootstrap (scripts/v3_common.paired) on the final run database, read-only. Writes evidence/cluster_sensitivity.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ["CAPE_REPO"]) if os.environ.get("CAPE_REPO") else next(
    q for q in Path(__file__).resolve().parents if (q / "cape").is_dir() and (q / "maqola uchun").is_dir())
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.v3_common import load_cells, paired  # noqa: E402
from tools.q1_analysis import _bbox_clusters, macroblock_cluster  # noqa: E402

MS = Path(__file__).resolve().parents[1]
an = json.loads((ROOT / "maqola uchun" / "supplementary" / "analysis.json").read_text(encoding="utf-8"))
cells = load_cells(an["datasets"]["j0126"]["run_dir"])
man = ROOT / "data" / "manifests" / "q1_external_j0126.jsonl"
bb = {r["sample_id"]: r["bbox_xyz"] for r in map(json.loads, man.read_text(encoding="utf-8").splitlines()) if r}


def overlap(a, b):
    v = 1
    for (a0, a1), (b0, b1) in zip(a, b):
        v *= max(0, min(a1, b1) - max(a0, b0))
    return v


cmap = _bbox_clusters(bb, lambda a, b: overlap(a, b) > 0)
out = {}
for base in ["crackle_pins_opt_corrected_m0", "crackle_pins_fast_m0"]:
    for name, cl in [("registered_33", macroblock_cluster),
                     ("overlap_merged", lambda c: cmap.get(c["sample_id"], c["sample_id"]))]:
        p = paired(cells, "cape_q1_fast_m0", base, cluster=cl, n_boot=10_000)
        out[f"{base}:{name}"] = {k: p.get(k) for k in ("n", "n_clusters", "S_T", "S_T_ci", "R_M", "R_M_ci",
                                                        "G_B_pct", "G_B_ci")}
(MS / "evidence" / "cluster_sensitivity.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
for k, v in out.items():
    print(k, v["n_clusters"], round(v["S_T"], 4), [round(x, 3) for x in v["S_T_ci"]], v["G_B_pct"], v["G_B_ci"])

