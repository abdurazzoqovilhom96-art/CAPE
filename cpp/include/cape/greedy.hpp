// Deterministic weighted greedy with singletons (spec sections 5, 11).
#pragma once

#include <cstdint>
#include <vector>

#include "cape/components.hpp"

namespace cape {

struct Selection {
  std::vector<uint32_t> pins;     // local candidate ids, ascending
  std::vector<uint32_t> singles;  // local CC ids, ascending
  uint64_t cost = 0;
};

// argmin cost/new over pins and singletons, exact integer comparison (c*n_b vs c*n_a), ties by
// (cost, kind, start index | CC id, depth). With uniform costs this is: take the pin with the
// most new CCs while c < s*new, then singletons; finally drop redundant pins in reverse order.
Selection greedy(const LocalModel& m);

bool is_cover(const LocalModel& m, const Selection& s);
uint64_t selection_cost(const LocalModel& m, const Selection& s);

}  // namespace cape
