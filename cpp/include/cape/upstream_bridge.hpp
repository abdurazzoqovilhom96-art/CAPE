// Narrow interface to the pinned upstream Crackle sources (vendor/crackle @ 14b39b1).
// upstream_bridge.cpp is the ONLY translation unit that includes vendor headers: they define
// non-inline functions, so a second including TU in the same module would violate the ODR.
#pragma once

#include <cstdint>
#include <vector>

#include "cape/types.hpp"

namespace cape::bridge {

constexpr const char* kUpstreamSha = "14b39b196a14b3b1ba7d1cd34f350c324308000f";

// Upstream per-slice 2D 4-connected CC labeling with global ids (x fastest, ids grow with z).
struct Labeling {
  Dims d;
  std::vector<uint32_t> cc;         // V
  std::vector<uint64_t> per_slice;  // Z
  uint64_t N = 0;
  std::vector<uint32_t> cc_crcs;    // Z: crc32c of each slice-local CC image (stream tail)
};

// Everything the label selection must not change (spec section 19, panel A).
struct Boundary {
  int crack_format = 0;  // crackle::CrackFormat: 0 impermissible, 1 permissible
  int markov_order = 0;  // effective order (reset to 0 when there are no cracks)
  std::vector<uint8_t> stored_model;
  std::vector<std::vector<uint8_t>> crack_codes;  // per slice
};

struct HeaderFields {
  int label_format = 0;  // 0 FLAT, 2 PINS_VARIABLE_WIDTH
  int data_width = 1;
  int stored_data_width = 1;
  Dims d;
};

template <typename LABEL>
Labeling cc_label(const LABEL* labels, const Dims& d);

// v3 M5b: the same upstream labeling (connected_components2d_4 per slice, identical ids, per-slice counts
// and crcs) computed in 16-slice batches and written straight into the column-major chain buffer
// colmajor[col * Z + z]; the z-major CC volume is never allocated (Labeling::cc stays empty).
// cc_values[u] receives the label value of CC u.
template <typename LABEL>
Labeling cc_label_colmajor(const LABEL* labels, const Dims& d, std::vector<uint32_t>& colmajor,
                           std::vector<uint64_t>& cc_values);

template <typename LABEL>
Boundary boundaries(const LABEL* labels, const Dims& d, bool impermissible, int markov_order, size_t parallel);

// Upstream FLAT labels section (encode_flat) and its CC crcs.
template <typename LABEL>
std::vector<uint8_t> flat_section(const LABEL* labels, const Dims& d, int stored_width, size_t parallel,
                                  std::vector<uint32_t>& cc_crcs);

template <typename LABEL>
uint64_t pixel_pairs(const LABEL* labels, uint64_t voxels);

template <typename LABEL>
uint64_t max_label(const LABEL* labels, uint64_t voxels);

// Upstream pins labels section with upstream's own selection, background and serializer
// (crackle::pins::compute + encode_condensed_pins), regardless of the pins/flat rule.
template <typename LABEL>
std::vector<uint8_t> stock_pins_section(const LABEL* labels, const Dims& d, bool optimize, int stored_width,
                                        std::vector<uint32_t>& cc_crcs);

// v2 (plan P1.4): upstream's selection, background and serializer with ONE change - the count
// width w_N is taken from the counts actually written after short pins become CC lists
// (format_audit F2). Wherever upstream's own width suffices the bytes are identical to
// stock_pins_section; `widened` reports whether the fix changed w_N.
template <typename LABEL>
std::vector<uint8_t> stock_pins_section_corrected(const LABEL* labels, const Dims& d, bool optimize, int stored_width,
                                                  std::vector<uint32_t>& cc_crcs, bool& widened);

// Full upstream encoder (used for V == 0 and as an in-module reference in tests).
template <typename LABEL>
std::vector<uint8_t> stock_compress(const LABEL* labels, const Dims& d, bool allow_pins, int markov_order,
                                    bool optimize_pins, size_t parallel);

// Assemble a v1 stream exactly like crackle::compress_helper.
std::vector<uint8_t> assemble(const HeaderFields& h, const std::vector<uint8_t>& labels_section,
                              const Boundary& b, const std::vector<uint32_t>& cc_crcs);

uint32_t crc32c(const uint8_t* data, size_t n);

}  // namespace cape::bridge
