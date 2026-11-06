// Integer dual ascent lower bound (spec section 12). a_u = q * pi_u with integer arithmetic;
// with integer costs all values stay multiples of q (docs/mathematics.md), so the bound is exact.
#pragma once

#include <cstdint>
#include <vector>

#include "cape/components.hpp"

namespace cape {

struct DualResult {
  std::vector<uint64_t> a;  // per local CC
  uint64_t lb = 0;          // ceil(sum a / q)
};

DualResult dual_ascent(const LocalModel& m, uint64_t q);

// Independent feasibility check of a witness (a_u <= q s, sum over each pin <= q c).
bool dual_feasible(const LocalModel& m, const DualResult& d, uint64_t q);

}  // namespace cape
