"""CAPE v3 stage PACKAGE (plan CAPE v3, section 17): one self-describing results directory

    python scripts/package_v3.py --state analysis/v3_state.json   ->  results/v3_<stamp>_<source8>/

00_protocol ... 17_package as in the plan. Folders are created only for what was really produced; a missing input
is listed in BLOCKERS.md and status.json, never replaced by an empty placeholder. Datasets are NOT copied (no
redistribution right for all of them): manifests, official sources and hashes are. Bitstreams stay in the run
directories (listed with their hashes in the raw tables).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default="analysis/v3_state.json")
    a = ap.parse_args(argv)
    st = json.loads((ROOT / a.state).read_text(encoding="utf-8"))
    frz = json.loads((ROOT / "analysis" / "v3_freeze" / "freeze.json").read_text(encoding="utf-8"))
    out = ROOT / "results" / f"v3_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{frz['expected_source_hash'][:8]}"
    out.mkdir(parents=True)
    blockers: list[str] = []
    made: dict[str, list[str]] = {}

    def put(section: str, src: Path, name: str | None = None) -> None:
        if not src.exists():
            blockers.append(f"{section}: missing {src.relative_to(ROOT) if src.is_relative_to(ROOT) else src}")
            return
        dst = out / section / (name or src.name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        made.setdefault(section, []).append(str(dst.relative_to(out)))

    runs = {k: v.get("run_dir") for k, v in st["panels"].items() if v.get("status") == "DONE" and v.get("run_dir")}
    # 00 protocol
    for f in ["configs/v3_development.yaml", "configs/v3_methods.yaml", "configs/v3_dev_core.yaml",
              "configs/v3_dev_scale.yaml", "configs/v3_dev_tracks.yaml", "configs/v3_dev_quality.yaml",
              "configs/v3_dev_quality_check.yaml", "configs/v3_confirm_frozen.yaml", "configs/v3_confirm_scale_frozen.yaml",
              "analysis/v3_freeze/freeze.json", "analysis/v3_select/selected_methods.json",
              "data/manifests/v3_dev_core.jsonl", "data/manifests/v3_dev_quality.jsonl", "data/manifests/scaling_v21.jsonl",
              "data/manifests/confirm_snemi3d.jsonl", "data/manifests/confirm_snemi3d_v3_scale.jsonl"]:
        put("00_protocol", ROOT / f)
    for f in ("configs/v3_dev_core_rerun.yaml", "configs/v3_dev_scale_rerun.yaml"):
        if (ROOT / f).exists():
            put("00_protocol", ROOT / f)
    aud = json.loads((ROOT / "analysis" / "v3_audit" / "audit_v3.json").read_text(encoding="utf-8"))
    (out / "00_protocol" / "factor_map.json").write_text(json.dumps(aud["factors"], indent=2), encoding="utf-8")
    # 01 environment
    for k, rd in runs.items():
        put("01_environment", ROOT / rd / "01_environment", f"{k}")
    put("01_environment", ROOT / "build" / "native_build.json")
    put("01_environment", ROOT / "snapshots" / "v21" / "FROZEN_V21.json")
    # 02 data audit
    for f in ("data_audit.csv", "audit_v3.json", "AUDIT_V3_UZ.md", "claims_recheck.csv", "certificate_rows.csv",
              "wD_compaction.csv", "proof_test_matrix.csv"):
        put("02_data_audit", ROOT / "analysis" / "v3_audit" / f)
    # 03 logs
    put("03_logs", ROOT / "analysis" / "v3_logs")
    put("03_logs", ROOT / a.state)
    for k, rd in runs.items():
        put("03_logs", ROOT / rd / "14_logs" / "controller.log", f"{k}_controller.log")
    # 04 raw (append-only SQLite + CSV/JSONL of every repeat)
    for k, rd in runs.items():
        put("04_raw", ROOT / rd / "05_raw_metrics", k)
    # 05 correctness
    put("05_correctness", ROOT / "analysis" / "v3_final" / "tables" / "status_by_run.csv")
    for k, rd in runs.items():
        p = ROOT / rd / "04_roundtrip"
        if p.exists() and any(p.iterdir()):
            put("05_correctness", p, k)
    # 06 model certificates / 07 oracle
    put("06_model_certificates", ROOT / "analysis" / "v3_final" / "tables" / "certificates_confirm.csv")
    for k, rd in runs.items():
        p = ROOT / rd / "06_solver_certificates"
        for f in sorted(p.glob("*")) if p.exists() else []:
            put("07_oracle" if f.name.startswith("oracle") else "06_model_certificates", f, f"{k}_{f.name}")
    # 08 development / 09 ablations
    put("08_development", ROOT / "analysis" / "v3_select")
    for f in ("fast_gate_per_sample.csv", "m4_grid.csv", "tracks_pairs.csv"):
        put("09_ablations", ROOT / "analysis" / "v3_select" / f)
    # 10 scaling / 11 archive / 12 statistics / 13 tables / 14 plot data / 15 figures / 16 reports
    fin = ROOT / "analysis" / "v3_final"
    for f in ("scale_track.csv", "scale_track_methods.csv"):
        put("10_scaling", fin / "tables" / f)
    for f in ("V3_F4_memory_vs_n.csv", "V3_F5_stage_time.csv"):
        put("10_scaling", fin / "plot_data" / f)
    put("11_archive", fin / "tables" / "secondary_confirm.csv")
    put("11_archive", fin / "plot_data" / "V3_F8_safe_archive.csv")
    put("12_statistics", fin / "primary_family.csv")
    put("12_statistics", fin / "v3_summary.json")
    put("13_tables", fin / "tables")
    put("14_plot_data", fin / "plot_data")
    put("15_figures", fin / "figures")
    for f in ("V3_YAKUNIY_TAHLIL_UZ.md", "V3_FINAL_ANALYSIS_EN.md", "claim_ledger.csv"):
        put("16_reports", fin / f)
    put("16_reports", ROOT / "analysis" / "v3_select" / "SELECT_V3_UZ.md")
    for f in ("V3_MATHEMATICS.md", "V3_CHANGELOG.md", "V3_NOVELTY_MATRIX.md"):
        put("16_reports", ROOT / "docs" / f)
    # 17 package: source zip (every SOURCE_GLOBS file + docs + frozen v2.1 binary), reproduction, data sources
    from cape.provenance import source_files, source_tree_hash

    pkg = out / "17_package"
    pkg.mkdir(parents=True, exist_ok=True)
    files = source_files() + sorted((ROOT / "docs").glob("*.md")) + [ROOT / "run_v3.cmd", ROOT / "snapshots" / "v21" /
                                                                       "_cape_native.cp312-win_amd64.pyd",
                                                                       ROOT / "snapshots" / "v21" / "FROZEN_V21.json"]
    with zipfile.ZipFile(pkg / "CAPE_V3_SOURCE.zip", "w", compression=zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if f.exists():
                z.write(f, f.relative_to(ROOT).as_posix())
    src_now = source_tree_hash()
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = None
    (pkg / "REPRODUCE_V3.md").write_text(
        "# CAPE v3 reproduction\n\n"
        f"- source tree hash of the confirm runs: `{frz['expected_source_hash']}`; packaged tree: `{src_now}`; "
        f"git commit at packaging: `{commit}`.\n"
        "- environment: Windows, MinGW-w64 g++ 16.2, CMake, Ninja, CPython 3.12 (see 01_environment).\n\n"
        "```powershell\npy -3.12 scripts\\bootstrap.py\n.\\run_v3.cmd --stage all --resume\n```\n\n"
        "Data are not redistributed: fetch them with `scripts/fetch_data.py cremi` (CREMI), `scripts/fetch_snemi3d.py` "
        "(SNEMI3D, Zenodo 10.5281/zenodo.7142003, md5 checked) and `scripts/fetch_sources.py` (Crackle samples); every "
        "crop is re-cut from the manifests in 00_protocol and checked against its voxel sha256.\n", encoding="utf-8")
    sources = [{"dataset": "CREMI A/B/C", "url": "https://cremi.org (mirror: Hugging Face pytc/tutorial, LFS sha256 checked)",
                "license": "cremi.org terms; not redistributed"},
               {"dataset": "SNEMI3D", "url": "https://doi.org/10.5281/zenodo.7142003", "license": "CC-BY-4.0; not redistributed"},
               {"dataset": "Crackle repo samples", "url": "https://github.com/seung-lab/crackle (pinned 14b39b1)",
                "license": "BSD-3-Clause repository; provenance of the volumes undocumented"}]
    (pkg / "DATA_SOURCES.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    status = {"package": out.name, "created_at": now(), "source_hash_confirm": frz["expected_source_hash"],
              "source_hash_packaged": src_now, "git_commit": commit, "runs": runs, "sections": sorted(made),
              "blockers": blockers, "complete": not blockers}
    (out / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    (out / "BLOCKERS.md").write_text("# BLOCKERS\n\n" + ("\n".join(f"- {b}" for b in blockers) if blockers else
                                                         "- none: every planned artifact was produced\n"), encoding="utf-8")
    sums = []
    for f in sorted(p for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        sums.append(f"{sha(f)}  {f.relative_to(out).as_posix()}")
    (out / "17_package" / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    (ROOT / "results" / "LATEST_V3_PACKAGE.txt").write_text(str(out.relative_to(ROOT)) + "\n", encoding="utf-8")
    print(json.dumps({"package": str(out.relative_to(ROOT)), "files": len(sums), "blockers": blockers}, indent=1))
    return 0 if not blockers else 1


if __name__ == "__main__":
    sys.exit(main())
