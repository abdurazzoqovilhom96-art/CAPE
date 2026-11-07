# Q1 Eθ: why O1, O2 and O3 write exactly the bytes of E0

Notation:
- E0 is the frozen original v3 FAST encoder (`snapshots/v3`, impl_mask 575). Eθ is the live binary with Q1 bits.
- `V = X·Y·Z`. The batched CC path (`kImplBatchedCC`) labels 16 slices at a time and transposes them into a
  column-major chain buffer `colmajor[col·Z + z] = cc(col, z)`.
- Every Q1 bit only acts inside that path (`cpp/src/upstream_bridge.cpp`, `cpp/src/encoder.cpp`).

Required invariant (task v3, section 1.2): `Dec(Eθ(D)) = D` and `Eθ(D) = E0(D)` byte for byte.

## O1: lean CC (bit 1024)
**What changes.** E0 calls `connected_components2d_4(src, X, Y, 1, dst, start_label = N, tmp_N)` and then makes two
extra per-voxel passes:
1. `local[i] = dst[i] − N`, followed by `crc32c(local)`;
2. `cc_values[dst[i]] = src[i]`.

O1 instead:
- calls the **same function** with `start_label = 0`;
- takes `crc32c(dst)` directly;
- reads the value of CC `k` at the first pixel `i` where `dst[i] = k`;
- adds `N` while transposing.

**Lemma O1.1** (labels). Upstream with `start_label = N` writes exactly `local + N`, where `local` is its output with
`start_label = 0`.
- *Proof.* `relabel()` (`cc3d.hpp:116-144`) assigns `renumber = start_label + 1 + rank` and writes `renumber − 1`. The
  rank (the order of the smallest provisional label of each equivalence class) does not depend on `start_label`. ∎

Hence:
- the crc input `local` is identical, so the crc is identical;
- the transposed values `local + N` equal E0's `dst` values;
- so `colmajor` is identical.

**Lemma O1.2** (values). In raster order, the local labels first reach `0, 1, 2, …` in increasing order. The first
pixel `i` with `dst[i] = k` belongs to CC `k`, so `src[i]` is the value of CC `k`.
- *Proof.* The rank of a class is the order of its smallest provisional label. Provisional labels are created in raster
  order, and the first raster pixel of a component cannot inherit a label from its left or upper neighbour (that
  neighbour would be in the component and earlier). So the first pixel of a component creates its smallest provisional
  label, and components are numbered by first-pixel order. ∎

E0 writes `cc_values[u] = src[i]` for every pixel of CC `u`. All these values are equal (one CC has one value), so the
arrays are identical. Every quantity derived from `colmajor`, `cc_values`, `per_slice` and `cc_crcs` is unchanged:
the label map, runs, candidates, selection, records, crcs and stream.

## O2: exact run allocation (bit 2048)
**What changes.**
- E0 grows the run vector from `reserve(2·XY)`, so large inputs make it reallocate and copy. The working set briefly
  holds both buffers, and this is where the encode peak was measured (`analysis/q1_select`).
- O2 first counts `z_pairs = #{(col, z) : z ≥ 1, L(col, z) = L(col, z−1)}` during the CC pass. It then reserves
  exactly `R = V − z_pairs` runs before filling.

**Lemma O2.**
- The column runs are maximal z-intervals of equal **dense label index**. Since the dense index is a bijection of the
  value, these are maximal z-intervals of equal value.
- Each column of length Z with `t` value changes has `t + 1` runs, and `t = (Z − 1) − (equal z-pairs of the column)`.
- Summing over the XY columns gives `R = XY·Z − z_pairs = V − z_pairs`. ∎

The runs are produced by the same loop, in the same order, with the same content; only the capacity differs. Bytes are
unchanged. The encoder exports `runs_expected`, and `tests/test_q1_invariants.py` checks that `runs_expected` equals
`run_count`.

## O3: compact uint16 chain buffer (bit 4096)
**What changes.** The chain buffer stores slice-local numbers `colmajor16[col·Z + z] = cc(col, z) − zoff[z]` as uint16,
where `zoff[z] = Σ_{z'<z} per_slice[z']`. This takes 2V bytes instead of 4V. It is used only if every slice has at most
65536 CCs; otherwise the encoder falls back to the uint32 buffer, which is the E0 path.

**Lemma O3.1** (exact reconstruction). `cc(col, z) = zoff[z] + colmajor16[col·Z + z]`.
- The local number is below 65536 by the check.
- `zoff[z] + local < 2^32` because `N < 2^32 − 1` is enforced (format_audit F5). ∎

`ChainAccess::at()` returns exactly this value, so every consumer that reads chains through `at()` sees E0's ids:
components, local models, dual bound, CSR and repair.

**Lemma O3.2** (fast paths). The specialized loops in `reductions.cpp` and `incidence.cpp` return the same results:
- **Hashes.** `chain_hash` and `chain_hash_fast` hash `zoff[z] + local`, which is the global id. The values are
  identical, so the bucket structure is identical.
- **Equality.** CCs of different slices are disjoint. So two chains of equal length are equal only if they start in the
  same slice, and then only if their local numbers are equal (same `zoff` per position). This is the uint16 comparison
  after the `z_start` check.
- **Subset containment.** The tested alignment `off = z_s(p) − z_s(q)` puts the same slice under each compared
  position, so equal global ids ⟺ equal local numbers.
- **Incidence.** It counts and places the reconstructed global ids. ∎

So the kept candidate set, the components, the duals, the selections and the records are identical, and the bytes are
identical. The fallback (> 65536 CCs in a slice) is tested with a 300×300 checkerboard: 90 000 CCs per slice,
`compact_chain = 0`, bytes equal.

## Evidence
- `tests/test_q1_invariants.py`:
  - all 8 combinations of O1/O2/O3 on 4 v3 masks;
  - 2 depth policies × 16 synthetic and real cases;
  - FAST preset and 10 edge cases (dtypes uint8–uint64, Z = 1, a single label, uint64 max, many labels, tall volumes);
  - every result compared with the **frozen v3 binary** in a separate process, by sha256 and length, plus diagnostics.
- The development and final runs compare the sha256 of every stream of every sample with E0.

## Memory model (why the peak drops)
Encode-inclusive peak working set measured with the `profile_memory` diagnostics:

| Crop | E0 peak | Eθ (O1+O2+O3) peak | E0 peak happens at |
|---|---|---|---|
| SNEMI quadrant 512×512×100 uint16 | 306 MiB | 214 MiB | runs (grow-and-copy) |
| CREMI 512×512×125 uint64 | 470 MiB | 407 MiB | — |

- O2 removes the transient second run buffer.
- O3 removes 2V bytes for the whole solve.
- These are single profiling runs on development and confirm data, which illustrate the mechanism only. The evidence
  is the pre-registered development panel and the final run.
