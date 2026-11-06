// Exact byte model of the PINS_VARIABLE_WIDTH labels section (spec formula (3)).
#pragma once

#include <cstdint>

#include "cape/types.hpp"

namespace cape {

// B_label = w_L + 8 + (K-1) w_L + num_grids w_G + 1 + 2 (K-1) w_N + P (w_I + w_D) + Q w_C
uint64_t predict_label_bytes(const Widths& w, uint64_t n_written_labels, uint64_t num_grids, uint64_t P,
                             uint64_t Q);

// Background-independent part H(theta) of the section for a given regime (everything except
// the per-written-label overhead and the records).
uint64_t fixed_section_bytes(const Widths& w, uint64_t num_grids);

// Per written label constant: its dictionary entry and two counts.
inline uint64_t per_label_overhead(const Widths& w) { return static_cast<uint64_t>(w.w_L) + 2ull * w.w_N; }

}  // namespace cape
