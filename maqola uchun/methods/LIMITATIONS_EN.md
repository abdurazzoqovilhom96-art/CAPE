# Limitations

- Acquisitions actually used in the final test: 3 (j0126, snemi, hemibrain).
  The primary C1 evidence rests on ONE new acquisition (j0126; 33 volumes, 31 non-overlapping clusters: 2 pairs of volumes overlap); SNEMI3D was
  seen before (and one SNEMI3D subvolume was used for a diagnostic memory profile while designing O2/O3); hemibrain is
  descriptive (4 cutouts). Generalization beyond these acquisitions is not claimed.
- Timing: one machine (Windows 11, MinGW g++ 16.2, i7-13700F), one thread. Other platforms may differ.
- Memory: process peak working set including the Python interpreter and the input array; it is not an
  algorithm-only memory figure.
- Size: Eθ writes exactly the bytes of E0; there is no compression gain from Q1. Size gains against other encoders
  belong to the CAPE selection already present in v2.1/v3 and are small against matched greedy.
- Certificates bound a restricted model (candidate family, safe reductions); not a global optimum; no bound after zstd.
- Rejected / unsuccessful mechanisms are listed in T05 (development) and docs; a run-based CC labeling was dropped
  before measurement (slower on fragmented slices).
- Novelty: the Q1 changes are engineering (buffer layout, allocation, fused passes) with proofs of output equivalence;
  inverted-index / dedup ideas are known (methods/CONTRIBUTION_AND_PRIOR_ART_EN.md).
- The amended neuroglancer uint32-widening track (neuroglancer_b8_u32) produced 0/704 SUCCESS rows on uint8/uint16 inputs (SNEMI3D): the runner rejected the dtype before the adapter, so this baseline is unavailable on uint16 data in the final run (it ran only on uint64 data, where it is the native path).
- AMENDMENT I13_neuroglancer_b8_u32_snemi (results/20261107T183016Z_all_296f78da, source 3710dd61bb48): neuroglancer_b8_u32 704/704 uint8/uint16 rows SUCCESS, lossless True. Against Eθ on the same 32 crops (cross-run): Eθ is 90.39% smaller and S_T 0.523. Not merged into the final rows (table T09).
- Interference window 2026-11-07T07:28:50Z to 2026-11-07T07:31:35Z (the agent re-rendered the smoke-test article package (CPU-heavy analysis) after the j0126 timing had started; window = benchmark start to the last file the rebuild wrote (07:31:31Z)): j0126 79/12672 rows; C1 timed rows 3/462, C1 memory rows 0; S_T 1.0739 with all rows, 1.0741 without the window rows.
