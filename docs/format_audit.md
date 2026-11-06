# Crackle format audit (spec sections 3, 6, 39.5)

Audit date: 2026-11-05. Every statement below is either a direct reading of the pinned
upstream source or is backed by a test that runs on every `pytest` invocation.

| Item | Value |
|---|---|
| Upstream repository | https://github.com/seung-lab/crackle |
| Pinned commit (vendor/) | `14b39b196a14b3b1ba7d1cd34f350c324308000f` (tree `734e41ca657f929372be5c9070f79f0f77507275`) |
| PyPI baseline | `crackle-codec==0.53.0` (wheel, used as an independent decoder and as `crackle_stock`) |
| Vendor build | `cape/_crackle_vendor` — our pybind11 glue over unmodified upstream headers, g++ 16.2 (MinGW-w64 UCRT) `-O3 -msse4.2 -mpclmul -std=c++20`, static runtime |
| Licenses | BSD-3-Clause; `src/cc3d.hpp` is LGPL-3.0 (reduced cc3d) — see THIRD_PARTY_NOTICES.md |

## 1. Version audit

`tests/test_interop.py::test_vendor_build_matches_pypi_and_cross_decodes` compresses 9 volumes
(uint16/32/64, large IDs, dense, sparse, single slice, all background) under 5 settings
(flat m0, pins fast m0, pins opt m0, flat m5, pins opt m5). The PyPI 0.53.0 wheel and the vendor
build at the pinned SHA produce **byte-identical streams in all 45 cases**, and each decoder
reconstructs the other's stream exactly. The newer upstream commit pushed after the pin is not used.

## 2. Stream layout (format version 1)

| Part | Bytes | Notes |
|---|---|---|
| Header | 29 | magic `crkl`, version, 16-bit format field, sx, sy, sz (uint32), log2 grid size, num_label_bytes (uint64), crc8 over bytes 5..27 |
| z-index | 4·Z + 4 | per-slice crack-code sizes, then crc32c of those sizes |
| Labels section | num_label_bytes | FLAT or PINS_VARIABLE_WIDTH (below) |
| Markov model | ⌈5·4^order / 8⌉ | only when markov order > 0 |
| Crack codes | Σ z-index | boundary payload, independent of label selection |
| Labels crc32c | 4 | crc32c of the labels section |
| CC crc32c | 4·Z | crc32c of each slice-local CC label image |

`cape/crackle_format.py` mirrors these rules (header, split, labels replacement); parsing and
re-serializing real upstream streams is byte-identical (`tests/test_byte_model.py`).

Header format field: bits 0-1 data width, 2-3 stored data width, 4 crack format, 5-6 label
format, 7 fortran order, 8 signed, 9-12 markov order, 13 not-sorted, 14 remapped.

## 3. PINS_VARIABLE_WIDTH labels section

```
bgcolor (w_L) | num_labels K-1 (8) | K-1 labels sorted, background removed (w_L each)
| components per grid, num_grids = Z for the default grid size (w_G each)
| combined_width (1): bits 0-1 log2 w_N, bits 2-3 log2 w_D, bits 4-5 log2 w_C
| per written label: num_pins (w_N) | pin start-index deltas (w_I each) | pin depths (w_D each)
                     | num_cc (w_N) | CC id deltas, sorted (w_C each)
```

* `w_L` = stored data width = byte width of the maximum label value.
* `w_I` = `byte_width(sx·sy·sz)` — fixed by the volume, **not** stored in `combined_width`.
* `w_G` = `byte_width(sx·sy)` — fixed.
* `w_N`, `w_D`, `w_C` are stored in `combined_width`: the decoder accepts any of 1/2/4/8 bytes.
  Upstream picks `w_N = width(max pins per label)`, `w_D = width(max chosen depth)`,
  `w_C = width(total CC count N)`.
* Spec formula (3) is exact for this layout:
  `B_label = w_L + 8 + (K-1)w_L + Z·w_G + 1 + 2(K-1)w_N + P(w_I+w_D) + Q·w_C`
  (`tests/test_byte_model.py::test_pins_section_parse_serialize_formula3`, 32 stream cases).
* Hence, for fixed widths, a pin costs `w_I + w_D` bytes and an explicit CC costs `w_C` bytes,
  and the per-label overhead `w_L + 2w_N` does not depend on the selection: the selection
  problem per label is exactly the weighted set cover of spec section 5.

Decoder semantics (`decode_condensed_pins`): every CC starts as `bgcolor`; explicit CC ids are
painted, then pins paint every CC they cross in their column, so pins override CC lists. A pin
must therefore only cross CCs of its own label (the decoder does not check this).

## 4. Upstream pin selection (stock)

* Candidates (`extract_columns`): one maximal same-label z-run per (x, y) column, with a small
  de-duplication against the previous column.
* `allow_pins=2` (`find_optimal_pins`): **unweighted** greedy — repeatedly take the candidate
  covering the most still-uncovered CCs; then `shrink_pin_to_fit` trims it to its newly covered
  CCs. The name is not an optimality claim.
* `allow_pins=1` (`find_suboptimal_pins`): for an arbitrary uncovered CC, take a deeper covering
  candidate (see F8).
* Serializer rewrite: a chosen pin with `depth < (w_I + w_D) div w_C` is written as an explicit CC
  list instead of a pin. CAPE's serializer never rewrites a decision (spec section 6).
* Replaying `pins_compute()` through `cape.crackle_format.upstream_records` reproduces the upstream
  labels section byte-for-byte (`test_stock_selection_replay_is_byte_identical`, 16 cases).

## 5. Decision rules

* Label format: `PINS` iff `sz > 1 and allow_pins and unsigned and pixel_pairs >= voxels div 2`,
  otherwise `FLAT` (`compress_helper`). `pixel_pairs` counts equal consecutive voxels in memory
  order. Crack format AUTO: impermissible iff `pixel_pairs >= voxels div 2`.
* Background (`find_bgcolor`): the label with the most chosen pins, ties by larger total depth;
  remaining ties follow `std::unordered_map` iteration order (implementation-defined), so
  `upstream_background_candidates` returns the whole tie set.

## 6. Findings

| ID | Finding | Evidence | Consequence for CAPE / benchmark |
|---|---|---|---|
| F1 | `allow_pins=1/2` does not force pins; fragmented volumes stay FLAT. | `test_upstream_label_format_rule`, `test_allow_pins_does_not_force_pins_on_fragmented_volume` | Every measurement records `label_format_actual` from the header. Panel A forces the pins format through the bridge. |
| F2 | **Count-width overflow corrupts data silently.** `w_N` is sized from the pin count *before* short pins become CC lists, but `num_cc` uses the same width. Reproducer: 200 depth-1 pins → 400 CC ids behind a 1-byte count; both PyPI 0.53.0 and the vendor build decode **256 wrong voxels without an error**. Re-serializing the same selection with `w_N = width(max(P_l, Q_l))` decodes losslessly with both original decoders. | `test_upstream_count_width_overflow_corrupts_silently`, `cape.synthetic.count_width_adversarial` | CAPE invariant: `w_N` from explicit `P_l, Q_l`; the strict serializer refuses overflow. Stock rows are lossless-checked; a stock failure is reported as `FAILED_LOSSLESS`, never hidden. Reporting upstream is the project owner's decision. **Re-check 2026-11-06:** upstream HEAD `3426263` ("feat: add anisotropy", 2026-11-05) has the same `encode_condensed_pins` code and, built as the optional `_crackle_head` module, decodes the reproducer with 256 wrong voxels (`test_f2_recheck_on_current_upstream_head`). Corrected baseline: selector `stock_greedy_corrected` (upstream selection + background + serializer, only `w_N` fixed; byte-identical wherever stock is lossless). |
| F3 | `compress_helper` declares `manual_bgcolor` as `bool`: a requested background 5 is stored as 1. | `test_upstream_manual_bgcolor_is_truncated_to_bool` | Stock baselines use automatic background only. |
| F4 | `pin_index_width()` multiplies three uint32 fields in 32-bit arithmetic; for `V >= 2^32` the index width wraps. | code reading (`header.hpp`) | CAPE refuses `V >= 2^32` volumes (chunk panel instead). |
| F5 | CC ids are uint32 (`cc3d`, decoder). | code reading | CAPE refuses `N > 2^32 - 1`. |
| F6 | `decompress` verifies the z-index crc and the per-slice CC crcs but not the labels crc32c. | code reading (`crackle.hpp` 510-670) | Label-section corruption (F2) is silent; every benchmark result is checked voxel-by-voxel. |
| F7 | The decoder re-parses the entire labels section once per z-slice: decode cost grows with `Z·(K + P + Q)`. | code reading | Fewer records (P+Q) can also speed up decoding (K3). |
| F8 | `find_suboptimal_pins` never updates `max_depth` inside its loop, so it keeps the last candidate deeper than the first rather than the deepest. | code reading (`pins.hpp`) | Affects only the quality of `crackle_pins_fast_m0`, not correctness. |
| F9 | `src/cc3d.hpp` is LGPL-3.0 inside a BSD-3 repository. | file header | Notice + license texts shipped (THIRD_PARTY_NOTICES.md); vendor sources not redistributed in release ZIPs. |
| F10 | Decoder-adjustable widths are `w_N, w_D, w_C`; `w_I, w_G, w_L` are fixed. CC ids are delta-coded, so a smaller `w_C` is valid whenever every first id and delta fits. | code reading + parser | CAPE regime space: `w_D` (depth windows, spec 7), `w_N` (count compaction, spec 6); `w_C` compaction is a secondary, separately reported mechanism. |

## 7. CAPE invariants derived from this audit

1. Explicit `pins` and `singletons` lists; the serializer never converts one into the other.
2. `w_N >= width(max_l max(P_l, Q_l))`, `w_D >= width(max chosen depth)`, `w_C >= width` of every
   first CC id and delta; strict overflow checks everywhere (`FormatError`).
3. Header, z-index, markov model, crack codes and CC crc32c come from upstream code through the
   bridge, so the boundary payload (`StreamLayout.boundary_payload`) equals the stock stream's
   (panel A causality check); only `num_label_bytes`, header crc8 and the labels crc32c change.
4. Volumes with `V >= 2^32` or `N >= 2^32` are rejected with an explicit error.
5. Every encoded result is decoded by the original decoder and compared voxel-by-voxel.
