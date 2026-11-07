"""Post-hoc diagnostic (not part of the gate): split the measured LP time into sparse-matrix assembly and the HiGHS
solve, on the same instances as the run (one window per useful run + singletons = the converged LP)."""
import json, sys, time
from pathlib import Path
import numpy as np
ROOT = Path("D:/CAPE_PINS"); sys.path.insert(0, str(ROOT))
from cape import _cape_native as cn, resources
from cape.canonical import crackle_view
from cape.cg import build_instance, window_rows, ColumnPool
from scipy.optimize import linprog
from scipy.sparse import csc_matrix, hstack, identity
resources.pin_current_process(resources.timing_cpu().get("cpu"))
EQ = {"markov_model_order": 0, "format_policy": "same_as_stock", "selector": "cape", "depth_policy": "fixed_depth_width",
      "certificate": "off", "impl_mask": 6719, "parallel": 1, "return_cc": True, "collect_records": True}
man = {r["sample_id"]: r for r in map(json.loads, (ROOT / "data/manifests/q1b_dev.jsonl").read_text().splitlines()) if r}
out = {}
for sid in sys.argv[2:]:
    vol = np.load(ROOT / man[sid]["path"])
    _, d = cn.encode(crackle_view(vol), EQ)
    inst = build_instance(vol, np.asarray(d["cc_volume"]), d["bgcolor"], int(d["regime_h"]),
                          int(d["w_I"]) + int(d["regime_w_D"]), int(d["w_C"]))
    pool = ColumnPool()
    for r in range(inst["starts"].shape[0]):
        pool.add(window_rows(inst, r, 0))
    n, m, c, s = inst["n_lp"], len(pool.cols), inst["c"], inst["s"]
    t0 = time.perf_counter()
    ind = np.concatenate(pool.cols); ptr = np.concatenate(([0], np.cumsum([x.shape[0] for x in pool.cols])))
    A = hstack([csc_matrix((np.ones(ind.shape[0]), ind, ptr), shape=(n, m)), identity(n, format="csc")]).tocsr()
    cost = np.concatenate((np.full(m, float(c)), np.full(n, float(s))))
    t_asm = time.perf_counter() - t0
    t0 = time.perf_counter()
    res = linprog(cost, A_ub=-A, b_ub=-np.ones(n), bounds=(0, None), method="highs", options={"presolve": True})
    t_solve = time.perf_counter() - t0
    out[sid] = {"assembly_s": t_asm, "linprog_s": t_solve, "status": int(res.status), "rows": n, "cols": m}
    print(sid, out[sid], flush=True)
Path(sys.argv[1]).write_text(json.dumps({"note": "post-hoc diagnostic, not part of the gate; pinned P-core, nothing else running", "samples": out}, indent=1))
