#include "cape/dual_bound.hpp"

#include <algorithm>

namespace cape {

DualResult dual_ascent(const LocalModel& m, uint64_t q) {
  const uint32_t M = m.M();
  DualResult d;
  d.a.assign(m.n, 0);
  std::vector<uint64_t> slack(M, q * m.c);
  uint64_t total = 0;
  for (uint32_t u = 0; u < m.n; u++) {  // ascending global CC id
    uint64_t delta = q * m.s;
    for (uint64_t k = m.inc_off[u]; k < m.inc_off[u + 1]; k++) delta = std::min(delta, slack[m.inc[k]]);
    d.a[u] = delta;
    for (uint64_t k = m.inc_off[u]; k < m.inc_off[u + 1]; k++) slack[m.inc[k]] -= delta;
    total += delta;
  }
  d.lb = (total + q - 1) / q;
  return d;
}

bool dual_feasible(const LocalModel& m, const DualResult& d, uint64_t q) {
  if (d.a.size() != m.n) return false;
  for (uint32_t u = 0; u < m.n; u++) {
    if (d.a[u] > q * m.s) return false;
  }
  for (uint32_t p = 0; p < m.M(); p++) {
    uint64_t sum = 0;
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) sum += d.a[m.elem[k]];
    if (sum > q * m.c) return false;
  }
  uint64_t total = 0;
  for (uint64_t v : d.a) total += v;
  return d.lb <= (total + q - 1) / q;
}

}  // namespace cape
