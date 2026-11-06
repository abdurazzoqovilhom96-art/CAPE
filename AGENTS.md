# Notes for agents working on CAPE-Pins

Read `docs/HANDOFF_UZ.md` first (current state), then the spec
(`CAPE_PINS_Q1_TOLIQ_LOYIHA_VA_AGENT_TOPSHIRIGI_UZ.md`, kept outside this tree).

## Non-negotiable rules
- Never fabricate numbers. Missing comparators are `UNAVAILABLE`/`FAILED_BUILD`, missing data is
  `BLOCKED_DATA`, failed renders are `REPORT_FAILED`. Never copy numbers from papers into tables.
- Never hide regressions, failures or synthetic-only evidence; synthetic rows stay out of real tables.
- Do not change the pre-registered primary pair (`configs/*.yaml: primary`) after seeing results.
- The CAPE serializer never converts a pin into CC ids or back; widths come from explicit records.
- Every encoded result is decoded by the original decoder and compared voxel-by-voxel.
- H01 / MICrONS downloads are NOT authorized (user decision 2026-11-05); ask before fetching.

## Build and test
```powershell
py -3.12 scripts\bootstrap.py                      # venv + hashed lock + vendor + native build + doctor
.venv\Scripts\python scripts\build_native.py       # rebuild native modules only
.venv\Scripts\python -m pytest tests -m "not acceptance"   # ~8 s
.venv\Scripts\python -m pytest tests -m acceptance        # T1-T12, ~75 s, writes tests_acceptance.json
```

## Architecture invariants
- `cpp/src/upstream_bridge.cpp` is the ONLY translation unit that includes vendor headers
  (they define non-inline functions; a second including TU breaks the ODR).
- Canonical arrays are (Z,Y,X) C-order == Crackle (X,Y,Z) F-order (`canonical.crackle_view`).
- Upstream `crackle.compress/decompress` default to `parallel=0` (all cores); adapters always pass
  `parallel=threads`.
- The controller (`cape/runner.py`) is the only SQLite writer; workers return packets.
- Changing any file in `provenance.SOURCE_GLOBS` changes the source hash: a running run refuses
  to continue, and results never mix sources.
- Pure-Python `cape/reference_model.py` is the test oracle for the native core; keep them in sync
  (greedy tie rule: singletons before pins on exact ratio ties).
