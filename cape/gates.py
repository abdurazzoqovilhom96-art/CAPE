"""Machine-readable claim permissions (spec sections 31, 35, 39.7). A flag is true only with
evidence; every flag carries the evidence or the reason it is false. No q1_guaranteed or
novelty flags exist."""

from __future__ import annotations

ALLOWED = ("lossless", "smaller_than_stock", "faster_than_stock", "joint_win", "restricted_optimality",
           "modern_comparison_complete", "roi_claim_supported", "heldout_complete")


def _flag(value: bool, evidence: str, reason: str | None = None) -> dict:
    return {"value": bool(value), "evidence": evidence, "reason": None if value else (reason or "not supported")}


def claim_gates(*, rows: list[dict], cells: dict, primary: dict | None, coverage: list[dict], cfg: dict,
                tasks: list[dict], oracle: dict | None, freeze: dict | None, real_samples: list[str]) -> dict:
    cape_rows = [r for r in rows if r["method_id"].startswith("cape")]
    cape_ok = [r for r in cape_rows if r["status"] == "OK"]
    cape_bad = [r for r in cape_rows if r["status"] == "FAILED_LOSSLESS"]
    g = {}
    g["lossless"] = _flag(bool(cape_ok) and not cape_bad and all(r["lossless"] for r in cape_ok),
                          f"{len(cape_ok)} CAPE rows verified voxel-exact; {len(cape_bad)} FAILED_LOSSLESS",
                          "no verified CAPE rows" if not cape_ok else f"{len(cape_bad)} CAPE rows failed lossless")

    new, base = cfg["primary"]["new"], cfg["primary"]["baseline"]
    cov = {c["method"]: c for c in coverage if c["panel"] == "B"}
    complete = all(cov.get(m, {}).get("pending", 1) == 0 and cov.get(m, {}).get("committed", 0) ==
                   cov.get(m, {}).get("ok", -1) for m in (new, base))
    if primary is None:
        reason = "primary pair not measured on real samples"
        g["smaller_than_stock"] = _flag(False, "none", reason)
        g["faster_than_stock"] = _flag(False, "none", reason)
    else:
        conf = primary["interval_kind"] == "confirmatory"
        ci = primary["total_ratio_ci95"]
        size_ok = conf and complete and ci is not None and ci[1] < 1.0
        g["smaller_than_stock"] = _flag(
            size_ok, f"total ratio {primary['total_ratio']:.4f} CI {ci} over {primary['n_samples']} real samples / "
                     f"{primary['n_clusters']} clusters ({primary['interval_kind']}); coverage complete={complete}",
            "exploratory interval (too few independent clusters)" if not conf else
            ("coverage incomplete" if not complete else "CI upper bound is not below 1"))
        sci = primary["geo_speedup_encode_ci95"]
        speed_ok = conf and complete and sci is not None and sci[0] > 1.0
        g["faster_than_stock"] = _flag(
            speed_ok, f"geometric encode speedup {primary['geo_speedup_encode']:.3f} CI {sci}",
            "exploratory interval (too few independent clusters)" if not conf else
            ("coverage incomplete" if not complete else "CI lower bound is not above 1"))
    g["joint_win"] = _flag(g["smaller_than_stock"]["value"] and g["faster_than_stock"]["value"],
                           f"pre-registered primary pair {new} vs {base}",
                           "requires both smaller_than_stock and faster_than_stock")

    certs = [r.get("certificate_valid") for r in cape_ok if r.get("certificate_valid") is not None]
    contradictions = (oracle or {}).get("contradictions", 0)
    audit_ran = bool(oracle) and oracle.get("status") == "COMPLETE"
    g["restricted_optimality"] = _flag(
        bool(certs) and all(certs) and contradictions == 0 and audit_ran,
        f"{sum(bool(c) for c in certs)}/{len(certs)} certificates valid; oracle contradictions={contradictions}; "
        f"audit ran={audit_ran}; scope: see certificate_scope (restricted model, not global format optimality)",
        "no certificates" if not certs else ("oracle audit missing" if not audit_ran else
                                             "invalid certificate or oracle contradiction"))

    req = ["csgv_rans_b64", "neuroglancer_b8", "compresso_native"]
    ok_all = all(cells.get((s, m, "B"), {}).get("n_ok", 0) > 0 for s in real_samples for m in req) and bool(real_samples)
    missing = [m for m in req if not any(cells.get((s, m, "B"), {}).get("n_ok", 0) for s in real_samples)]
    g["modern_comparison_complete"] = _flag(ok_all, f"required modern comparators {req} on {len(real_samples)} real samples",
                                            f"missing or failed: {missing}" if missing else "incomplete coverage")
    g["roi_claim_supported"] = _flag(False, "ROI panel C",
                                     "ROI panel disabled (second stage)" if not cfg["roi"]["enabled"] else
                                     "ROI evidence incomplete")
    held = [t for t in tasks if t["split"] == "heldout"]
    held_pending = [t for t in held if t["status"] in ("PENDING", "RUNNING")]
    g["heldout_complete"] = _flag(bool(held) and not held_pending and bool(freeze),
                                  f"{len(held)} held-out tasks, {len(held_pending)} pending, freeze={'yes' if freeze else 'no'}",
                                  "no held-out split in this run" if not held else "held-out tasks pending or no freeze")
    assert set(g) == set(ALLOWED)
    return g
