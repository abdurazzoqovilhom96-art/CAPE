# CAPE Q1 changelog (relative to v3, branch `v3`, frozen binary `snapshots/v3`, sha256 f1029e19...)

## Preserved
- **v3 is untouched.** The v3 source, freeze, runs and reports are not modified. Branch `q1` was created from commit
  `07362bc`.
- **E0 snapshot.** The v3 native module that ran the SNEMI3D confirm was copied to `snapshots/v3/` (`FROZEN_V3.json`),
  with adapter `cape_frozen_v3` and method `cape_v3frozen_fast_m0`, impl_mask 575.

## Native core (`cpp/`)
- **New impl bits** in `types.hpp`, byte-preserving, all effective only on the batched-CC path:
  - `kImplLeanCC = 1024` (O1);
  - `kImplExactRuns = 2048` (O2);
  - `kImplCompactChain = 4096` (O3);
  - `kImplMaxMask = 8191`.
- **`upstream_bridge.cpp`:**
  - lean CC branch: upstream labeling at start 0, crc from the batch, first-pixel CC values, offset added in the
    transpose;
  - `z_pairs` count;
  - `cc_label_colmajor16` (slice-local uint16 chain buffer, with fallback above 65536 CCs per slice).
- **`candidates.hpp` (`ChainAccess`):** uint16 view and per-slice offsets. `reductions.cpp` and `incidence.cpp`: exact
  fast paths on local numbers. `runs.cpp`: exact reservation, plus a builder for the compact buffer.
- **`memprobe.*`:** Windows working set and peak at stage ends, only with the option `profile_memory` (instrumentation,
  never on timed rows). `psapi` is linked.
- **Rejected before any panel:** a run-based 2D CC labeling. It was byte-identical but about 40% slower on fragmented
  slices.

## Python, configs, tools
- **`cape/adapters/cape_frozen.py`:** generic frozen snapshots (v21, v3). `cape_native.py`: `profile_memory` key.
- **`cape/adapters/neuroglancer.py`:** amended `widen_to: uint32` variant (method `neuroglancer_b8_u32`, a separate
  track).
- **`cape/config.py`:** merges `configs/q1_methods.yaml`. `cape/provenance.py`: `tools/*.py` are now in the source hash.
- **Configs:** `configs/q1_development.yaml` (pre-registered development rule), `q1_dev_{core,scale}.yaml`, generated
  `q1_final_*.yaml`.
- **Scripts and tools:**
  - `scripts/fetch_external_q1.py` and `make_q1_manifests.py`;
  - `scripts/q1_common.py` and `q1_develop.py`;
  - `tools/q1_audit.py`, `q1_freeze.py`, `q1_pipeline.py`, `q1_analysis.py`, `q1_figs.py`, `q1_article.py`,
    `validate_article_package.py`, `q1_encode_helper.py`.
- **External data** (authorized 2026-11-07): j0126 (33 dense GT volumes, official bucket) and hemibrain v1.2
  (4 pre-registered cutouts). See `docs/q1/EXTERNAL_DATA_PLAN.md`.

## Tests
- **New `tests/test_q1_invariants.py`:**
  - every O1/O2/O3 combination on four v3 masks, compared with the frozen v3 binary in a separate process;
  - edge cases;
  - the uint16 fallback;
  - the exact run count;
  - `profile_memory` only adds diagnostics;
  - the frozen v3 adapter contract in its own process.
- **Changed (interface extensions):**
  - `test_impl_mask.py` and `test_v3_invariants.py`: the first invalid mask is now 8192;
  - `test_adapters.py`: the frozen v3 adapter is exercised only in its own process, because two pybind11 modules with
    the same exception names share translators in one process.
