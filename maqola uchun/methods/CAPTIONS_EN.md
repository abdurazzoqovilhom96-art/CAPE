# Figure captions

**F01** (OK): Fig. 1. Example inputs: 3D object-ID segmentation maps of neurons (one sample per dataset, the first in sorted sample order; geometric-centre XY and XZ slices). Colours are a deterministic function of the ID for display only and may repeat; label 0 (black) is kept as an ordinary ID. Each volume was encoded by Eθ and decoded by the original Crackle decoder: mismatch_count = 0 means voxel-identical reconstruction.
  - UZ: 1-rasm: kirish obyektlari - neyronlarning 3D ID segmentatsiya xaritalari (EM intensivlik emas). Ranglar faqat ko'rsatish uchun; ID'lar o'zgarmaydi. mismatch_count = 0: Eθ oqimi original dekoder bilan aynan tiklandi.

**F02** (OK): Fig. 2. Eθ encoder stages in the order executed by cpp/src/encoder.cpp (FAST: fixed depth width, certificate off), with the share of the native encode time per stage summed over the j0126 test samples (native stage timers; the remainder is bookkeeping). Notes name where M1a/M5b (v3) and the accepted Q1 changes act; every change writes the same bytes as E0.
  - UZ: 2-rasm: Eθ bosqichlari koddagi tartibda; foiz - j0126 da har bosqichning native vaqt ulushi.

**F03** (OK): Fig. 3. Total stored size against total encode time on j0126 for every method (raw and zstd-wrapped; SAFE counts both candidate encodes). Ringed points are Pareto non-dominated (listed at the right). Eθ (blue) and E0 (orange) have identical bytes; they differ only in time. Not a CI plot (totals).
  - UZ: 3-rasm: j0126 da hajm va encode vaqti; Eθ va E0 baytlari bir xil, faqat vaqt farqli.

**F04** (OK): Fig. 4. Geometric-mean encode speed-up S_T = exp(mean log(T_base/T_Eθ)) with 95% paired cluster-bootstrap CIs (10 000 resamples; clusters: j0126 volume, SNEMI3D macroblock, hemibrain cutout). C1 (Eθ vs frozen v3 E0) is the new contribution; 'build' isolates compiler/build drift (live binary at the E0 mask); C2 is the historical v3 gain, not re-counted; the C3 rows compare with different streams (sizes differ).
  - UZ: 4-rasm: tezlanish S_T va 95% CI; C1 - yangi hissa, C2 - tarixiy (qayta sanalmaydi).

**F05** (OK): Fig. 5. (a) Encode-inclusive peak working set (fresh process; Windows PeakWorkingSetSize read after encode and before decode; includes the Python process and the input array) against volume size for all test volumes. (b) Instrumented profile (separate run, not timed): process peak after each encoder stage on the largest profiled volume, Eθ against the live binary at the E0 mask (E0 itself cannot be instrumented). Absolute MiB; no subtraction is presented as algorithm memory.
  - UZ: 5-rasm: (a) encode peak xotira hajmga nisbatan; (b) bosqichlar bo'yicha peak (alohida profil run).

**F06** (OK): Fig. 6. Leave-one-mechanism-out ablation on the same binary: ratio of the variant without the mechanism to the full Eθ, for encode time (left) and encode-inclusive peak (right), geometric means with 95% cluster-bootstrap CIs. 'Eθ − M1a' is the plain equal-coverage hash dedup on the same infrastructure. All variants write identical bytes.
  - UZ: 6-rasm: ablation - har mexanizmsiz variant / to'liq Eθ (vaqt va xotira).

**F07** (OK): Fig. 7. Per-sample size gain 100 (B_base - B_Eθ)/B_base for raw streams, zstd9-wrapped streams and SAFE archives (all headers counted; m0/m5 and zstd levels never mixed). W/T/L counts exact bytes. Raw Eθ streams are identical to E0, so any gain here is the CAPE selection already present in v3, not a Q1 change.
  - UZ: 7-rasm: namuna bo'yicha hajm farqi; Q1 hajmni o'zgartirmaydi (E0 bilan bir xil).

**F08** (OK): Fig. 8. (a) Gap between the written stream (UB) and the restricted-model lower bound (LB) for the Eθ CERTIFIED rows (same bytes as FAST): candidate family, safe reductions, all depth regimes, all backgrounds, w_N >= 1; not a global optimum and no bound after zstd. (b) The two development volumes behind the 12 invalid v2.1 rows: v2.1 reported LB > UB (negative gap); v3/Eθ add the scaled full-width dual for compacted w_D and are valid. Stream bytes are unchanged.
  - UZ: 8-rasm: (a) cheklangan model sertifikat oralig'i; (b) 12 eski noto'g'ri qator va tuzatilgan holat.
