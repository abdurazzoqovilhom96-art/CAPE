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
std::vector<Run> column_runs_colmajor(const uint32_t* colmajor, const std::vector<uint32_t>& cc_label, const Dims& d);

}  // namespace cape
