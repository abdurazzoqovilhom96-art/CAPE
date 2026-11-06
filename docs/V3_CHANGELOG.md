# CAPE v3 changelog (relative to v2.1, git tag `v2.1`, frozen binary `snapshots/v21`, sha256 39dca94b...)

## Preserved
- v2.1 source tree committed as `main` / tag `v2.1`; the v2.1 native module copied to `snapshots/v21/` and used
  as the etalon (`cape_v21_fast_m0`, adapter `cape_frozen_v21`, checksum verified on load). No v2.1 run or report was
  deleted. The interrupted v2.1 run `20261106T111350Z_development_e91c32fe` (307/400, source hash changed after INIT)
  is kept and marked SUPERSEDED in `analysis/v21_state.json`.

## Native core (`cpp/`)
- `types.hpp`: five new implementation bits (A=32 adjacent dedup, C=64 component CSR, G=128 eager greedy, F=256 fused
  scan, B=512 batched CC); `kImplV3`, `kImplMaxMask = 1023`. QUALITY options `regime_gate`, `rc_fixing` (+ limits),
  `repair` (+ grid parameters); all default off.
- new `candidate_store.*` (M1a), `cover_incidence.*` (M1b CSR, M2 eager greedy), `dual_pruning.*` (M3b, scaled
  bound), `component_repair.*` (M4).
- `exact_dp.*`: `LocalModel::no_single`, `DpLimits::sparse_admission` / `max_states`, outcome `Infeasible` (v2.1 paths
  unchanged; tested byte-identical).
- `upstream_bridge.*`: `cc_label_colmajor` (M5b) in the single vendor-including translation unit.
- `encoder.cpp`: M1a / M1b / M2 / M5 switches; M3a regime gate; M3b / M4 in pass 2 (M4 kept only if the whole section
  shrinks); **certificate fix** for fixed-depth Regime certificates under w_D compaction (stream bytes unchanged).
- `bindings.cpp`: new options, `impl_mask` range 0..1023, test hooks (`solve_abstract` returns eager / rc / repair
  results; `_v3_candidate_guard_raises`).

## Python / configs / scripts
- `cape/adapters/cape_frozen.py` (frozen v2.1 adapter); `cape/config.py` merges `configs/v3_methods.yaml`;
  `cape/adapters/cape_native.py` knows the v3 options; package version 0.3.0.dev0.
- `configs/v3_development.yaml` (pre-registered gates, panels, confirm plan, primary family),
  `configs/v3_dev_{core,scale,tracks,quality}.yaml`, generated `v3_dev_quality_check.yaml`, frozen
  `v3_confirm_frozen.yaml`, `v3_confirm_scale_frozen.yaml`.
- `scripts/`: `audit_v3.py`, `make_v3_manifests.py`, `run_v3.py` (+ `run_v3.cmd`), `pilot_select_v3.py`,
  `freeze_v3.py`, `report_v3.py`, `package_v3.py`, `v3_common.py`.

## Tests
- new `tests/test_v3_invariants.py` (+ `v3_cases.py`, `v3_frozen_digests.py`): byte identity of every v3 bit
  combination with the frozen v2.1 binary (computed in a separate process), diagnostics identity, forced hash
  collisions, edge-case roundtrips (FAST and QUALITY), 32-bit guard, regime-gate identity and bound validity,
  360 random abstract models against brute force (eager = lazy greedy; reduced-cost "Improved" = optimum, "Proven"
  holds; repair between optimum and incumbent), QUALITY never larger than FAST and lossless with LB <= UB, frozen
  adapter contract in its own process.
- changed (interface extensions, documented): `test_impl_mask.py` (invalid mask is now 1024; 32..1023 are v3 bits),
  `test_experimental_refine.py` (v3 QUALITY methods may be experimental, never "new"), `test_adapters.py` (the frozen
  adapter is exercised in its own process: two pybind11 modules with the same C++ exception names share pybind11's
  exception translators within one process).

## Found and fixed
- v2.1 fixed-depth Regime certificate could report `lb_bytes > ub_bytes` when the written depth width compacts
  (12 rows of the `cape_fixed_depth_width` ablation on Z=512 crops in v1/v2 width runs; they were already flagged
  `certificate_valid = False`, now explained and fixed).

## Selection and freeze (2026-11-06, development data only)
- FAST = `impl_mask 575` (v2.1 bits + M1a + M5b). M1b, M2 failed the FAST gate; M5a stayed inconclusive after the
  one 15-repeat rerun the protocol allows and is not in FAST. QUALITY composite did not pass (1.74x > 1.5x): no
  QUALITY default. Details: `analysis/v3_select/SELECT_V3_UZ.md`.
- `scripts/pilot_select_v3.py` writes its development configs idempotently (an unchanged definition keeps its file
  and the source hash, so an interrupted run resumes).
- Freeze applies the v2.1 stock budget rule (corrected stock only on volumes <= 2^25 voxels): the SNEMI3D scale track
  runs stock in a separate frozen run on the four quadrants with v3 FAST repeated as the matched reference; the whole
  volume is `SKIPPED_BUDGET` for stock (`data/manifests/confirm_snemi3d_v3_scale_skipped.json`).
