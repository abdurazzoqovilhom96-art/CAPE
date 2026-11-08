# Methods

## Problem
Given a label volume D and the frozen original v3 encoder E0 (impl_mask 575: v2.1 FAST + M1a neighbour-column
duplicate filter + M5b batched CC), find an encoder Eθ with Dec(Eθ(D)) = D and Eθ(D) = E0(D) byte for byte that lowers
encode time T and peak memory M (Pareto sense; no weighted score).

## Encoder (Eθ = impl_mask 6719; accepted Q1 bits: O2, O3)
1. scan (max label, pixel pairs) -> upstream crack-code boundaries (unchanged).
2. 2D 4-connected CC per slice, batched (M5b). Upstream labeling with start_label = N, local copy for
   the crc and one pass for the CC values, exactly as in E0 (O1 lean CC was tested and rejected in development (S_T 0.993, 95% CI lower 0.986); not part of Eθ). O3 compact chain: the
   column-major chain buffer stores slice-local uint16 numbers (2V bytes) with a per-slice offset when every slice
   has <= 65536 CCs, else the uint32 buffer.
3. Same-label z-runs; O2 allocates them once with the exact count V - z_pairs.
4. Depth-bounded complete-window candidates with the M1a neighbour filter; singleton, equal-coverage and subset
   reductions; independent components; greedy + integer dual bound; exact bitmask DP / local search on small
   components; explicit serializer.
Proofs: mathematics/m1a_proposition.md, mathematics/q1_output_preserving.md; certificate: mathematics/certificate_model.md.

Pseudocode (one regime, FAST):
```
labels -> boundaries (upstream)
for z-batch of 16 slices: CC2D_4(slice, start=N) -> crc(local), cc_values pass, transpose [uint16 if O3]
runs <- column runs (reserve V - z_pairs if O2)
cands <- windows(runs, h) minus neighbour twins (M1a)
alive <- reduce(cands); comps <- components(alive)
for comp: UB <- greedy; LB <- dual ascent; if small: exact DP / local search
records -> serialize -> assemble(header, labels section, boundaries, crcs)
```
Complexity: unchanged from v3 (linear passes over V plus the candidate work); Q1 changes constants and memory only
(O3: chain buffer 4V -> 2V bytes; O2: no transient second run array).

## Measurement
- One thread, worker pinned to one P-core, tasks sequential, randomized block order, 2 warmups; 7 repeats (j0126,
  SNEMI3D), 3 repeats (hemibrain, scale). T = median over repeats of the encode time of each (sample, method).
- Memory: a fresh worker process per (sample, method); Windows PeakWorkingSetSize read after encode and before decode
  (encode-inclusive peak, includes the Python process and the input array); end-to-end peak reported separately.
- Every stream decoded by the original Crackle decoder and compared voxel by voxel; sha256 of every stream stored.
- Statistics: S_T = exp(mean log(T_base/T_new)), R_M = exp(mean log(M_new/M_base)), pooled byte gain; paired cluster
  bootstrap (10 000, seed 20261107); Holm over the pre-registered primary family (C1 speed and memory on j0126).
- Reproduction: reproducibility/REPRODUCE.md.
