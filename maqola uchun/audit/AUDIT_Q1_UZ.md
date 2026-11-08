# CAPE Q1 audit (avtomatik, `tools/q1_audit.py`)

Yaratilgan: 2026-11-07T07:07:25+00:00.

## Oldingi da'volar (xom ma'lumotdan qayta hisoblangan)

| ID | da'vo | qayta hisob | hukm | tuzatish |
|---|---|---|---|---|
| A01 | v3 FAST 1.343x faster than v2.1 (SNEMI3D) | S_T 1.3432 CI [1.3300525652171211, 1.3565106593587974]; time reduction 25.55% | CONFIRMED | write as 'time reduced by 25.5%' (100(1-1/S_T)), never '34.3% less time' |
| A02 | v3 and v2.1 raw sizes equal (1,410,718 B) | sum new 1410718 / base 1410718; sha256 identical on all 32 samples: True | CONFIRMED | equal bytes are NOT a compression gain |
| A03 | 12.902x vs corrected stock | v3/stock S_T 12.902; v2.1/stock S_T 9.606; v3/v2.1 1.343 | CONFIRMED (scope) | whole CAPE vs stock; the v3 modules (M1a+M5b) account only for the v3/v2.1 factor |
| A04 | CAPE vs matched weighted greedy | saving 0.0343% CI [0.029487782297841204, 0.03961670180367173]; S_T 1.001; peak ratio 1.000 | CONFIRMED | keep in the main table (size, time and memory together) |
| A06 | scale track '5 volumes' | 1 full SNEMI3D volume + its 4 quadrants (one acquisition) | CORRECTED | write '1 acquisition: full volume + 4 subvolumes'; no bootstrap over them as independent volumes |
| A07 | scale stock 53.962x | n=4 quadrants only, S_T 53.962; full volume stock SKIPPED_BUDGET | CONFIRMED (scope) | only the 4 quadrants; no ratio for the full volume |
| A08 | M5a FAIL_INCONCLUSIVE_AFTER_RERUN (1.026, CI [1.020, 1.035]) | CI above 1: statistically positive; point below the pre-registered 1.05 practical gate | RELABELED | report 'statistically positive, practical 5% gate not met'; the frozen gate decision (not in FAST) stays |
| A09 | M3a regime gate saves time (ledger L8 CONDITIONAL) | regimes checked 7, pruned 0, total time ratio 0.9940061984253096, n 19, v3 decision 'KEEP (output-identical, faster)' | WITHDRAWN | no mechanism claim: with 0 pruned the 0.994 time ratio is noise; L8 -> UNSUPPORTED |
| A10 | scale SAFE vs SAFE-stock | saving -0.0034% CI [-0.25484378469046415, 0.17506534823543332]; larger on 1/4 | RELABELED | CI contains 0: neither superiority nor equivalence shown (equivalence needs a pre-registered margin) |
| A11 | peak memory column (v3 report) = fresh-process encode+decode peak | CAPE: decode raised the peak on 0/32 samples; flat: 32/32; v3/flat encode-only peak ratio 1.412 | CORRECTED | Q1 primary memory metric = encode-inclusive peak (peak_after_encode, before decode); e2e reported apart |
| A12 | 'enc ms' column | sum over samples of the per-sample median encode time | CLARIFIED | label every aggregate (sum of medians / geomean of ratios) explicitly |
| A13 | neuroglancer_b8 rows | 672 timing rows + 32 memory rows UNSUPPORTED_DTYPE (uint16 input) | CLARIFIED | coverage limitation, not a CAPE error and not a competitor loss; Q1 adds an amended explicit uint32-widening track |
| A14 | SAFE never larger than flat+zstd9 | SAFE == min(flat+zstd9, CAPE+zstd9) on 32/32 samples (final stored file size, no selector header) | CONFIRMED | guarantee holds at the stored-file level for the same zstd level; not across levels or m0/m5 |
| A15 | Q8 verdict FAIL (v3 report) | triggered only by neuroglancer_b8 UNSUPPORTED_DTYPE; report_v3 also overwrote status counts per run (672 shown vs 704 rows) | CORRECTED (generator) | Q1 generator separates CAPE statuses from comparator coverage; the frozen v3 verdict stays in history |
| A16 | M5b peak ratio 1.000 (v3 select, e2e peak median) | encode-inclusive geo ratio all/noB 0.951 CI [0.9213560540183287, 0.988343844151277] (n_mem 61) | RECOMPUTED | the v3 memory gate used the median e2e peak; Q1 uses the encode-inclusive peak (pre-registered) |
| A17 | SNEMI3D independence for Eθ | one SNEMI3D quadrant was used for a diagnostic memory profile while designing O2/O3 (2026-11-07) | DISCLOSED | SNEMI3D is 'previously seen' for Eθ; the primary C1 test is j0126 (untouched until the final run) |

## 12 ta eski sertifikat qatori: tarqalish

| sample | eski qator | eski LB/UB | v3 LB/UB | v2.1 = v3 oqim | v3 = Q1 oqim | tanlovga ta'sir |
|---|---|---|---|---|---|---|
| crackle_connectomics_x256_y256_z0_256x256x512 | 6 | 1072941/1071856 | 1058597/1071856 | True | True | False |
| crackle_ws_x0_y0_z0_256x256x512 | 6 | 4256561/4205939 | 4079923/4205939 | True | True | False |

Issue register: `audit/issue_register.csv`. Inventory: `audit/inventory.json`.
