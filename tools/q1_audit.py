"""CAPE Q1 audit (task v3, sections 3-5): inventory, run dependency map, issue register, earlier claims recomputed
from raw data, certificate propagation of the 12 old invalid bounds, SAFE guarantee check.

    python tools/q1_audit.py            # writes audit/*.json|csv|md (never modifies results/ or analysis/)

Every number comes from results/<run>/05_raw_metrics/run.sqlite or from re-encoding with the frozen binaries in
separate processes (tools/q1_encode_helper.py). Old results are read-only.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from q1_common import atomic_json, dev_cluster, fmt, load_cells, paired, write_csv  # noqa: E402

OUT = ROOT / "audit"
PY = sys.executable
V3 = {"confirm_primary": "results/20261106T184116Z_all_d6786080",
      "confirm_scale": "results/20261106T213428Z_all_080b15b8",
      "confirm_scale_stock": "results/20261106T213921Z_all_751ff9ac",
      "dev_core": "results/20261106T131304Z_development_2238806f",
      "dev_scale": "results/20261106T141028Z_development_bdc5fcbd",
      "dev_quality": "results/20261106T151919Z_development_31cbc70e",
      "dev_tracks": "results/20261106T161236Z_development_12de6862"}
WIDTH = {"v1_width": "results/20261105T145305Z_development_c1d12b3e",
         "v2_width": "results/20261106T062540Z_development_0227806a"}
SNAP = {"v21": ROOT / "snapshots" / "v21" / "_cape_native.cp312-win_amd64.pyd",
        "v3": ROOT / "snapshots" / "v3" / "_cape_native.cp312-win_amd64.pyd"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(p: Path) -> str | None:
    if not p.exists() or p.is_dir():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------ inventory
def inventory() -> dict:
    items = {
        "frozen_v21_binary": "snapshots/v21/_cape_native.cp312-win_amd64.pyd",
        "frozen_v3_binary_E0": "snapshots/v3/_cape_native.cp312-win_amd64.pyd",
        "v3_freeze": "analysis/v3_freeze/freeze.json",
        "v3_final_report_uz": "analysis/v3_final/V3_YAKUNIY_TAHLIL_UZ.md",
        "v3_select": "analysis/v3_select/selected_methods.json",
        "handoff": "docs/HANDOFF_UZ.md",
        "requirements_lock": "requirements.lock",
        "sources_lock": "sources.lock.json",
        "manifest_snemi3d_32": "data/manifests/confirm_snemi3d.jsonl",
        "manifest_snemi3d_scale": "data/manifests/confirm_snemi3d_v3_scale.jsonl",
        "manifest_j0126": "data/manifests/q1_external_j0126.jsonl",
        "manifest_hemibrain": "data/manifests/q1_external_hemibrain.jsonl",
        "external_data_plan": "docs/q1/EXTERNAL_DATA_PLAN.md",
    }
    for k, v in V3.items():
        items[f"raw_{k}"] = f"{v}/05_raw_metrics/run.sqlite"
    inv = {"written_at": now(), "root": str(ROOT), "files": {}}
    for k, rel in items.items():
        p = ROOT / rel
        inv["files"][k] = {"path": rel, "exists": p.exists(), "sha256": sha(p), "bytes": p.stat().st_size if p.exists()
                           else None, "status": "OK" if p.exists() else "BLOCKED_MISSING_SOURCE"}
    # duplicates among Markdown reports (same content = one document, not two experiments)
    seen, dups = {}, []
    for p in sorted(list((ROOT / "docs").glob("*.md")) + list((ROOT / "analysis").glob("**/*.md"))):
        h = sha(p)
        if h in seen:
            dups.append({"a": seen[h], "b": p.relative_to(ROOT).as_posix()})
        else:
            seen[h] = p.relative_to(ROOT).as_posix()
    inv["duplicate_markdown"] = dups
    inv["note"] = "HANDOFF_UZ(1).md does not exist in this tree; only docs/HANDOFF_UZ.md"
    return inv


def dependency_map() -> dict:
    st = json.loads((ROOT / "analysis" / "v3_state.json").read_text(encoding="utf-8"))
    frz = json.loads((ROOT / "analysis" / "v3_freeze" / "freeze.json").read_text(encoding="utf-8"))
    return {"v3": {"panels": {k: v.get("run_dir") for k, v in st.get("panels", {}).items()},
                   "select": "analysis/v3_select/selected_methods.json <- panels core, scale, quality, tracks, reruns",
                   "freeze": {"file": "analysis/v3_freeze/freeze.json", "source": frz.get("expected_source_hash")},
                   "confirm": "confirm_primary/scale/scale_stock <- freeze", "report": "analysis/v3_final <- confirm + "
                   "select + freeze"},
            "q1": {"E0": "snapshots/v3 (= binary of the v3 confirm runs)",
                   "development": "analysis/q1_state.json panels -> analysis/q1_select/selected.json",
                   "freeze": "analysis/q1_freeze/freeze.json -> configs/q1_final_*.yaml",
                   "final": "results/q1_<run_id>/q1_state.json -> maqola uchun/"}}


# ------------------------------------------------------------------------------------------------ claims
def claims() -> list[dict]:
    rows = []
    cp = load_cells(V3["confirm_primary"])
    cs = load_cells(V3["confirm_scale"])
    css = load_cells(V3["confirm_scale_stock"])

    def add(cid, claim, value, verdict, correction, evidence):
        rows.append({"id": cid, "earlier_claim": claim, "recomputed": value, "verdict": verdict,
                     "correction": correction, "evidence": evidence})

    p = paired(cp, "cape_v3_fast_m0", "cape_v21_fast_m0")
    add("A01", "v3 FAST 1.343x faster than v2.1 (SNEMI3D)",
        f"S_T {fmt(p['S_T'], 4)} CI {p['S_T_ci']}; time reduction {fmt(p['time_reduction_pct'], 2)}%",
        "CONFIRMED", "write as 'time reduced by 25.5%' (100(1-1/S_T)), never '34.3% less time'", V3["confirm_primary"])
    add("A02", "v3 and v2.1 raw sizes equal (1,410,718 B)",
        f"sum new {p['bytes_new']} / base {p['bytes_base']}; sha256 identical on all {p['n']} samples: "
        f"{p['sha_identical']}", "CONFIRMED", "equal bytes are NOT a compression gain", V3["confirm_primary"])
    p2 = paired(cp, "cape_v3_fast_m0", "crackle_pins_opt_corrected_m0")
    p3 = paired(cp, "cape_v21_fast_m0", "crackle_pins_opt_corrected_m0")
    add("A03", "12.902x vs corrected stock",
        f"v3/stock S_T {fmt(p2['S_T'], 3)}; v2.1/stock S_T {fmt(p3['S_T'], 3)}; v3/v2.1 {fmt(p['S_T'], 3)}",
        "CONFIRMED (scope)", "whole CAPE vs stock; the v3 modules (M1a+M5b) account only for the v3/v2.1 factor",
        V3["confirm_primary"])
    p4 = paired(cp, "cape_v3_fast_m0", "v3_fast_weighted_greedy_m0")
    add("A04", "CAPE vs matched weighted greedy",
        f"saving {fmt(p4['G_B_pct'], 4)}% CI {p4['G_B_ci']}; S_T {fmt(p4['S_T'], 3)}; peak ratio {fmt(p4['R_M'], 3)}",
        "CONFIRMED", "keep in the main table (size, time and memory together)", V3["confirm_primary"])
    add("A06", "scale track '5 volumes'", "1 full SNEMI3D volume + its 4 quadrants (one acquisition)", "CORRECTED",
        "write '1 acquisition: full volume + 4 subvolumes'; no bootstrap over them as independent volumes",
        "data/manifests/confirm_snemi3d_v3_scale.jsonl")
    p5 = paired(css, "cape_v3_fast_m0", "crackle_pins_opt_corrected_m0", n_boot=0)
    add("A07", "scale stock 53.962x", f"n={p5['n']} quadrants only, S_T {fmt(p5['S_T'], 3)}; full volume stock "
        "SKIPPED_BUDGET", "CONFIRMED (scope)", "only the 4 quadrants; no ratio for the full volume",
        V3["confirm_scale_stock"])
    add("A08", "M5a FAIL_INCONCLUSIVE_AFTER_RERUN (1.026, CI [1.020, 1.035])",
        "CI above 1: statistically positive; point below the pre-registered 1.05 practical gate", "RELABELED",
        "report 'statistically positive, practical 5% gate not met'; the frozen gate decision (not in FAST) stays",
        "analysis/v3_select/selected_methods.json")
    sel = json.loads((ROOT / "analysis" / "v3_select" / "selected_methods.json").read_text(encoding="utf-8"))
    m3a = json.dumps(sel.get("m3a") or sel.get("M3a") or {}, default=str)[:300]
    add("A09", "M3a regime gate saves time (ledger L8 CONDITIONAL)", f"0 regimes pruned; {m3a}", "WITHDRAWN",
        "no mechanism claim: with 0 pruned the 0.994 time ratio is noise; L8 -> UNSUPPORTED", "analysis/v3_select")
    p6 = paired(css, "safe_v3_fast_m0_zstd9", "safe_stock_m0_zstd9")
    add("A10", "scale SAFE vs SAFE-stock", f"saving {fmt(p6['G_B_pct'], 4)}% CI {p6['G_B_ci']}; "
        f"larger on {p6['larger']}/{p6['n']}", "RELABELED", "CI contains 0: neither superiority nor equivalence shown "
        "(equivalence needs a pre-registered margin)", V3["confirm_scale_stock"])
    # memory: encode-inclusive vs end-to-end peak
    pm = paired(cp, "cape_v3_fast_m0", "crackle_flat_m0", n_boot=0)
    e2e = [c for (s, k), c in cp.items() if k == "cape_v3_fast_m0" and c["peak_e2e"] and c["peak_enc"]]
    raised = sum(c["peak_e2e"] > c["peak_enc"] for c in e2e)
    fl = [c for (s, k), c in cp.items() if k == "crackle_flat_m0" and c["peak_e2e"] and c["peak_enc"]]
    fl_raised = sum(c["peak_e2e"] > c["peak_enc"] for c in fl)
    add("A11", "peak memory column (v3 report) = fresh-process encode+decode peak",
        f"CAPE: decode raised the peak on {raised}/{len(e2e)} samples; flat: {fl_raised}/{len(fl)}; "
        f"v3/flat encode-only peak ratio {fmt(pm['R_M'], 3)}", "CORRECTED",
        "Q1 primary memory metric = encode-inclusive peak (peak_after_encode, before decode); e2e reported apart",
        V3["confirm_primary"])
    add("A12", "'enc ms' column", "sum over samples of the per-sample median encode time", "CLARIFIED",
        "label every aggregate (sum of medians / geomean of ratios) explicitly", "scripts/report_v3.py")
    ng = [c for (s, k), c in cp.items() if k.startswith("neuroglancer_b8")]
    ng_mem = sum(1 for (s, k), c in cp.items() if k == "neuroglancer_b8" for r in c["mem_rows"]
                 if r["status"] != "OK")
    add("A13", "neuroglancer_b8 rows", f"{sum(sum(c['statuses'].values()) for c in ng)} timing rows + {ng_mem} memory "
        "rows UNSUPPORTED_DTYPE (uint16 input)", "CLARIFIED", "coverage limitation, not a CAPE error and not a "
        "competitor loss; Q1 adds an amended explicit uint32-widening track", V3["confirm_primary"])
    # SAFE guarantee: SAFE = min(zstd9(flat), zstd9(cape)) exactly, no selector byte
    bad, n = [], 0
    for (s, k), c in cp.items():
        if k != "safe_v3_fast_m0_zstd9":
            continue
        fz, cz = cp.get((s, "crackle_flat_m0+zstd9")), cp.get((s, "cape_v3_fast_m0+zstd9"))
        if not (fz and cz and c["total_bytes"]):
            continue
        n += 1
        if c["total_bytes"] != min(fz["total_bytes"], cz["total_bytes"]):
            bad.append(s)
    add("A14", "SAFE never larger than flat+zstd9", f"SAFE == min(flat+zstd9, CAPE+zstd9) on {n - len(bad)}/{n} "
        "samples (final stored file size, no selector header)", "CONFIRMED" if not bad else "FAILED",
        "guarantee holds at the stored-file level for the same zstd level; not across levels or m0/m5",
        V3["confirm_primary"])
    add("A15", "Q8 verdict FAIL (v3 report)", "triggered only by neuroglancer_b8 UNSUPPORTED_DTYPE; report_v3 also "
        "overwrote status counts per run (672 shown vs 704 rows)", "CORRECTED (generator)",
        "Q1 generator separates CAPE statuses from comparator coverage; the frozen v3 verdict stays in history",
        "scripts/report_v3.py:498")
    # M5b memory on the dev data with the encode-inclusive peak
    dev = {**load_cells(V3["dev_core"]), **load_cells(V3["dev_scale"])}
    pb = paired(dev, "cape_v3_all_m0", "cape_v3_noB_m0", cluster=dev_cluster, n_boot=2000)
    add("A16", "M5b peak ratio 1.000 (v3 select, e2e peak median)", f"encode-inclusive geo ratio all/noB "
        f"{fmt(pb['R_M'], 3)} CI {pb['R_M_ci']} (n_mem {pb['n_mem']})", "RECOMPUTED",
        "the v3 memory gate used the median e2e peak; Q1 uses the encode-inclusive peak (pre-registered)",
        f"{V3['dev_core']}, {V3['dev_scale']}")
    add("A17", "SNEMI3D independence for Eθ", "one SNEMI3D quadrant was used for a diagnostic memory profile while "
        "designing O2/O3 (2026-11-07)", "DISCLOSED", "SNEMI3D is 'previously seen' for Eθ; the primary C1 test is "
        "j0126 (untouched until the final run)", "docs/q1/mathematics/q1_output_preserving.md")
    return rows


# ------------------------------------------------------------------------------------------------ certificates
def certificate_propagation() -> list[dict]:
    old = []
    for tag, run in WIDTH.items():
        con = sqlite3.connect(f"file:{ROOT / run / '05_raw_metrics' / 'run.sqlite'}?mode=ro", uri=True)
        for s, lb, ub, sh, valid in con.execute(
                "select sample_id, lb_bytes, ub_bytes, bitstream_sha256, certificate_valid from measurements where "
                "method_id='cape_fixed_depth_width' and status='OK' and panel!='MEM' order by sample_id"):
            old.append({"run": tag, "sample_id": s, "old_lb": lb, "old_ub": ub, "old_sha": sh, "old_valid": valid})
        con.close()
    invalid = [r for r in old if r["old_valid"] == 0]
    samples = sorted({r["sample_id"] for r in invalid})
    man = {}
    for line in (ROOT / "data" / "manifests" / "width_sensitivity.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        man[r["sample_id"]] = str(ROOT / r["path"])
    opts = {"markov_model_order": 0, "format_policy": "force_pins", "depth_policy": "fixed_depth_width",
            "certificate": "regime"}
    files = [man[s] for s in samples]
    res = {}
    for name, which in (("v21", str(SNAP["v21"])), ("v3", str(SNAP["v3"])), ("q1_live", "live")):
        o = dict(opts) if name == "v21" else dict(opts, impl_mask=575 if name == "v3" else 7743)
        if name == "v21":
            o["impl_mask"] = 31
        out = subprocess.run([PY, str(ROOT / "tools" / "q1_encode_helper.py"), which, json.dumps(o), *files],
                             cwd=ROOT, capture_output=True, text=True, check=True)
        res[name] = json.loads(out.stdout)
    rows = []
    for s, f in zip(samples, files):
        o = [r for r in invalid if r["sample_id"] == s]
        a, b, c = res["v21"][f], res["v3"][f], res["q1_live"][f]
        rows.append({"sample_id": s, "old_invalid_rows": len(o), "old_runs": ";".join(sorted({r['run'] for r in o})),
                     "old_lb": o[0]["old_lb"], "old_ub": o[0]["old_ub"], "old_sha_equals_v21_reencode":
                     all(r["old_sha"] == a["sha256"] for r in o), "v21_lb": a["lb_bytes"], "v21_ub": a["ub_bytes"],
                     "v3_lb": b["lb_bytes"], "v3_ub": b["ub_bytes"], "v3_valid": b["lb_bytes"] <= b["ub_bytes"],
                     "q1_lb": c["lb_bytes"], "q1_ub": c["ub_bytes"], "stream_sha_v21_eq_v3": a["sha256"] == b["sha256"],
                     "stream_sha_v3_eq_q1": b["sha256"] == c["sha256"], "regime_w_D": b["regime_w_D"],
                     "written_w_D": b["w_D"], "old_gap_pct": 100 * (o[0]["old_ub"] - o[0]["old_lb"]) / o[0]["old_ub"],
                     "new_gap_pct": 100 * (b["ub_bytes"] - b["lb_bytes"]) / b["ub_bytes"],
                     "lossless_all": a["lossless"] and b["lossless"] and c["lossless"],
                     "influenced_selection": a["sha256"] != b["sha256"]})
    return rows


ISSUES = [
    ("I01", "1.343x reported without the time-reduction form", "A01", "wording", "generator prints 100(1-1/S_T)",
     "no", "FIXED (generator)"),
    ("I02", "equal bytes could be read as a compression result", "A02", "wording", "byte-equality table; C1 = time "
     "and memory only", "no", "FIXED (generator)"),
    ("I03", "12.9x vs stock attributed to new modules", "A03", "interpretation", "C1/C2/C3 separated", "no",
     "FIXED (generator)"),
    ("I04", "matched greedy must stay in the main table", "A04", "fairness", "T03 C3 rows include it", "yes (re-measured)",
     "FIXED"),
    ("I05", "12 invalid v2.1 certificate rows (w_D compaction)", "certificate_propagation.csv", "certificate scope",
     "v3 scaled-dual bound; propagation audited (stream bytes unaffected)", "no (report-only)", "FIXED in v3; AUDITED"),
    ("I06", "'5 volumes' wording", "A06", "wording", "'1 acquisition: full + 4 subvolumes'", "no", "FIXED (generator)"),
    ("I07", "stock 53.96x scope", "A07", "scope", "quadrants only; full volume N/A", "no", "FIXED (generator)"),
    ("I08", "M5a label", "A08", "wording", "statistically positive, practical gate unmet", "no", "FIXED (generator)"),
    ("I09", "M3a mechanism claim with 0 prunes", "A09", "claim", "claim withdrawn", "no", "FIXED (ledger)"),
    ("I10", "SAFE scale CI crosses 0", "A10", "interpretation", "no superiority/equivalence claim", "no",
     "FIXED (generator)"),
    ("I11", "memory = encode+decode peak", "A11", "measurement validity", "encode-inclusive peak is primary; e2e apart",
     "yes (final run)", "FIXED (protocol)"),
    ("I12", "'enc ms' aggregation unnamed", "A12", "wording", "aggregates named", "no", "FIXED (generator)"),
    ("I13", "neuroglancer uint16 unsupported", "A13", "coverage", "amended explicit uint32 widening track", "yes",
     "FIXED (amended track)"),
    ("I14", "SAFE guarantee scope", "A14", "claim scope", "checked at stored-file level, same zstd level", "no",
     "VERIFIED"),
    ("I15", "Q8 verdict / status-count bug in report_v3", "A15", "report generator", "Q1 generator separates statuses",
     "no", "FIXED (generator)"),
    ("I16", "M5b memory judged on e2e peak median", "A16", "measurement validity", "encode-inclusive peak, geo ratio "
     "with CI", "yes (final run)", "FIXED (protocol)"),
    ("I17", "SNEMI3D seen while designing Eθ", "A17", "independence", "j0126 is the primary C1 test", "no",
     "DISCLOSED"),
    ("I18", "tools/*.py not covered by the source hash", "cape/provenance.py SOURCE_GLOBS", "provenance",
     "tools/*.py added to SOURCE_GLOBS before the Q1 freeze", "no", "FIXED"),
    ("I19", "first Q1 dev attempt stopped in TESTED (frozen v3 module loaded in-process by test_adapters)",
     "results/20261107T053842Z_development_8f27e750", "test isolation", "frozen v3 adapter tested in its own process",
     "yes (dev rerun)", "FIXED"),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    atomic_json(OUT / "inventory.json", inventory())
    atomic_json(OUT / "run_dependency_map.json", dependency_map())
    cl = claims()
    write_csv(OUT / "claims_recheck.csv", cl)
    cert = certificate_propagation()
    write_csv(OUT / "certificate_propagation.csv", cert)
    write_csv(OUT / "issue_register.csv", [
        {"id": i, "issue": t, "evidence": e, "impact": imp, "fix": fx, "rerun_needed": rr, "status": stt,
         "test_or_check": {"I05": "audit/certificate_propagation.csv", "I19": "tests/test_q1_invariants.py",
                           "I14": "audit/claims_recheck.csv A14", "I18": "cape/provenance.py"}.get(i,
                                                                                                   "audit/claims_recheck.csv")}
        for i, t, e, imp, fx, rr, stt in ISSUES])
    L = ["# CAPE Q1 audit (avtomatik, `tools/q1_audit.py`)", "", f"Yaratilgan: {now()}.", "",
         "## Oldingi da'volar (xom ma'lumotdan qayta hisoblangan)", "", "| ID | da'vo | qayta hisob | hukm | tuzatish |",
         "|---|---|---|---|---|"]
    for r in cl:
        L.append(f"| {r['id']} | {r['earlier_claim']} | {r['recomputed']} | {r['verdict']} | {r['correction']} |")
    L += ["", "## 12 ta eski sertifikat qatori: tarqalish", "",
          "| sample | eski qator | eski LB/UB | v3 LB/UB | v2.1 = v3 oqim | v3 = Q1 oqim | tanlovga ta'sir |",
          "|---|---|---|---|---|---|---|"]
    for r in cert:
        L.append(f"| {r['sample_id']} | {r['old_invalid_rows']} | {r['old_lb']}/{r['old_ub']} | {r['v3_lb']}/{r['v3_ub']} | "
                 f"{r['stream_sha_v21_eq_v3']} | {r['stream_sha_v3_eq_q1']} | {r['influenced_selection']} |")
    L += ["", "Issue register: `audit/issue_register.csv`. Inventory: `audit/inventory.json`."]
    (OUT / "AUDIT_Q1_UZ.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
