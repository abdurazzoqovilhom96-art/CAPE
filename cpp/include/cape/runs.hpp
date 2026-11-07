// Same-label column runs (spec section 7) and the CC -> label map.
#pragma once

#include <cstdint>
#include <vector>

#include "cape/types.hpp"

namespace cape {

struct LabelMap {
  std::vector<uint64_t> values;    // K sorted unique label values
  std::vector<uint32_t> cc_label;  // N: dense label index of each CC
};

// Immutable maximal runs of every column (col = x + X*y ascending, z ascending inside a column),
// computed slice by slice for contiguous memory access.
std::vector<Run> column_runs(const uint32_t* cc, const std::vector<uint32_t>& cc_label, const Dims& d);
// v2: the same runs, in the same order, from a column-major CC copy (colmajor[col * Z + z]) in one pass.
// exact_count > 0 (Q1 O2): the run count is known (V - z_pairs), so the array is allocated once; same runs.
std::vector<Run> column_runs_colmajor(const uint32_t* colmajor, const std::vector<uint32_t>& cc_label, const Dims& d,
                                      uint64_t exact_count = 0);
// Q1 O3: the same runs from the compact buffer (global id = zoff[z] + colmajor16[col * Z + z]).
std::vector<Run> column_runs_colmajor16(const uint16_t* colmajor16, const uint32_t* zoff,
                                        const std::vector<uint32_t>& cc_label, const Dims& d, uint64_t exact_count = 0);

}  // namespace cape
