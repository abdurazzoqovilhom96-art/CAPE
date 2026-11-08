# Output-preserving acceleration of a certified Crackle label encoder (draft)

*Draft generated from the verified tables of run q1_20261107T072741Z; not submitted anywhere.*

## Abstract
Lossless compression of dense neuron segmentation maps with the Crackle format spends much of its encode time and memory in connected-component labeling, run extraction and candidate handling. We present output-preserving changes to the CAPE encoder (impl_mask 6719) that write byte-identical streams to the frozen previous version. On a new external test set (j0126, 33 volumes) the encode speed-up is S_T = 1.074 [1.065, 1.083] and the encode-inclusive peak memory ratio is R_M = 0.915 [0.911, 0.919], with 100.0% byte identity. Results on a previously seen volume (SNEMI3D) and on hemibrain cutouts are reported separately. The contribution is engineering; compression ratios are unchanged.

## 1. Introduction
Connectomics produces large 3D label volumes. Crackle stores them as crack-code boundaries plus a label section;
CAPE chooses the PINS records by a set-cover model with a certificate. This paper asks whether the encoder can be made
faster and leaner without changing a single output byte.

## 2. Object and data
# Object and data

**What is compressed.** 3D neuron object-ID segmentation maps (dense label volumes in which every voxel carries the ID
of the neurite it belongs to). They are not electron-microscopy intensity images; no RGB or medical intensity data is
used. Every encoding is lossless: the decoded volume equals the input voxel by voxel, and object IDs and boundaries
are preserved exactly.

**Codec.** Crackle (seung-lab, pinned commit 14b39b1): crack-code boundaries plus a label section. CAPE chooses the
records of the PINS label section; the stream is decoded by the unmodified upstream decoder.
See Table T01 and Fig. 1.

## 3. Method
See methods/METHODS_EN.md (algorithm, pseudocode, proofs in mathematics/).

## 4. Results
 Eθ vs frozen v3 E0 (primary: j0126)
- **j0126** (j0126 zebra finch (new external, primary)): n = 33; S_T 1.074 [1.065, 1.083] (time reduction 6.89%); R_M 0.915 [0.911, 0.919]; byte-identical to E0: 100.0%; worst sample speed-up 1.022 (j0126_z3710_y8691_x2889_150x150x150).
- **snemi** (SNEMI3D 32 crops (previously seen)): n = 32; S_T 1.079 [1.067, 1.091] (time reduction 7.36%); R_M 0.893 [0.885, 0.900]; byte-identical to E0: 100.0%; worst sample speed-up 1.002 (snemi3d_x256_y768_z0_128x128x64).
- **hemibrain** (hemibrain v1.2 cutouts (new external, descriptive)): n = 4; S_T 1.066 [1.009, 1.124] (time reduction 6.17%); R_M 0.859 [0.858, 0.860]; byte-identical to E0: 100.0%; worst sample speed-up 0.985 (hemibrain_x20096_y17792_z13312_512x512x256).

Primary family (two-sided bootstrap p, Holm): {"H1_C1_speed_j0126": 0.0002, "H2_C1_memory_j0126": 0.0002}.
Practical targets (pre-registered): S_T >= 1.05 and R_M <= 0.95 on j0126 -> speed reached: True,
memory reached: True.

Build drift (live binary at the E0 mask vs E0, j0126): S_T 1.004 [0.998, 1.011], R_M 0.999.

## C2: historical (Eθ vs v2.1, j0126)
S_T 1.315 [1.295, 1.334], R_M 0.842 [0.835, 0.848]; bytes identical:
True. This includes the v3 gain (M1a, M5b) and is not counted as a Q1 contribution.

## C3: competitors (j0126; different streams)
- matched weighted greedy (same infrastructure): size gain 0.0368% [0.0317, 0.0416], S_T
  0.988, R_M 1.000.
- corrected stock pins: size gain 0.1216% [0.1031, 0.1399], S_T 7.054
  [6.361, 7.892], R_M 0.411.
- Crackle flat: size gain 3.091% [2.899, 3.300], S_T 0.501, R_M
  1.224 (a size-time trade-off when S_T < 1).
Other codecs, archive and SAFE: tables T03 and T06. Negative results and statuses: T08.

## Amendment: j0126 cluster definition (found after the final run)
The registered analysis treated the 33 j0126 volumes as 33 clusters, but 2 pairs overlap (1.4% of j0126_z2868_y5744_x5157_150x150x150; 30.9% of j0126_z4951_y9415_x2272_150x150x150). The registered result is kept; overlap-merged clusters and a proximity sensitivity (volumes within 150 voxels in every axis merged) are reported next to it:
  - registered_33: 33 clusters; S_T 1.0739 [1.0650, 1.0832], R_M 0.9154 [0.9112, 0.9192]; bootstrap p (S_T) 0.0001, p (R_M) 0.0001
  - overlap_merged: 31 clusters; S_T 1.0739 [1.0653, 1.0833], R_M 0.9154 [0.9112, 0.9191]; bootstrap p (S_T) 0.0001, p (R_M) 0.0001
  - gap_le_150_merged: 26 clusters; S_T 1.0739 [1.0645, 1.0837], R_M 0.9154 [0.9111, 0.9194]; bootstrap p (S_T) 0.0001, p (R_M) 0.0001


## 5. Discussion
The new encoder is a constant-factor and memory improvement over its predecessor on the measured data, with exact
output equivalence. Against other encoders the size differences are those of the CAPE selection and are small against
a matched greedy; Crackle flat remains faster where S_T < 1.

## 6. Limitations
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

