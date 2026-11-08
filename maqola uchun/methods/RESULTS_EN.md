# Results (generated from tables; run q1_20261107T072741Z)

## C1: Eθ vs frozen v3 E0 (primary: j0126)
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
