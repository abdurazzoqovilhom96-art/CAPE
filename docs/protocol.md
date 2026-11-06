# Benchmark protocol

## Panels (spec §19)
- **A — selector causality**: forced pins format; identical CCs, crack codes, Markov order,
  dtype; only the label selection differs. The boundary payload of every CAPE stream equals the
  stock stream's (`StreamLayout.boundary_payload`, tested). Methods: `cape_core`, `stock_cover`,
  `weighted_greedy`, `greedy_local`, ablations.
- **B — end-to-end storage**: every method encodes the same canonical volume into a standalone
  stream (shape/dtype recoverable without the manifest). Native and zstd-wrapped rows are separate.
- **C — chunk/ROI**: second stage, disabled (`configs/roi.yaml`); every ROI artifact is
  `NOT_APPLICABLE` with that reason.

## Accounting (one rule for all methods, spec §39.7)
`total_bytes` = stored stream length; `metadata_bytes` = an uncompressed container header the
adapter adds outside the codec stream (generic, Blosc2, Neuroglancer, CSGV); `payload_bytes =
total − metadata`. Crackle-family `label_bytes` comes from the stream header; other codecs: null.

## Timing (spec §20)
- One persistent worker, pinned to the second physical P-core (first SMT thread; topology from
  `GetSystemCpuSetInformation`); controller on its own core; one timed job at a time.
- `threads = 1`; **upstream Crackle defaults to `parallel=0` (all cores) — adapters always pass
  `parallel=threads`**; BLAS/OMP/Blosc threads forced to 1.
- Per (sample, method, wrapper): warm-up on first use in the worker, then `repeats` timed
  repeats; the method order is shuffled per repeat with a fixed seed. Work below `small_task_ms`
  is repeated inside one sample until `min_batch_ms` (iterations recorded). GC paused in the
  timed region. Every iteration really encodes/decodes (no result cache).
- Encode time includes everything the codec needs online (CC labeling, candidates, reductions,
  bounds, DP/local search, background/regime search, serialization, CRCs, wrapper). Decode time
  includes dtype/axis restore. Verification, hashing and file writes are outside the timed region.
- CLI codecs (Volcanite) are timed as `cli_process_file_to_file` and never mixed with in-process
  library timings.

## Memory (spec §20, K4)
Separate fresh process per (sample, method): OS peak working set before/after one encode and one
decode (`win_peak_wset_fresh_process`) plus a 10 ms poll of the process tree. When the peak did
not grow during the call the value is labelled an upper bound.

## Statistics (spec §21)
- Size: total-bytes ratio `Σ B_new / Σ B_base` and per-family ratios; per-sample gains (negative
  values kept). Speed: geometric-mean and median per-sample speedups.
- Uncertainty: cluster bootstrap (10 000 resamples, fixed seed) over `macroblock_id`; fewer than
  5 clusters → interval marked **exploratory** and no superiority claim is allowed.
- Wilcoxon only as a secondary test with Holm adjustment across the confirmatory pairs.
- Primary pair is pre-registered (`cape_m0` vs `crackle_pins_opt_m0`, panel B, native) and never
  switched after results.

## Freeze, statuses, exit codes
- Protocol freeze (config, methods, split and source hashes) is written before any benchmark
  task; held-out metrics never exist without it.
- Measurement status: OK, FAILED_LOSSLESS, FAILED_BUILD, UNAVAILABLE, UNSUPPORTED_DTYPE, OOM,
  TIMEOUT, BLOCKED_DATA, NOT_APPLICABLE, INTERRUPTED. Every planned task ends with a row, so
  coverage denominators are complete.
- Exit codes: 0 complete (not a win claim), 2 missing config/data/dependency, 3 lossless or
  certificate failure, 4 incomplete benchmark, 5 interruption, 6 report/verification failure.
