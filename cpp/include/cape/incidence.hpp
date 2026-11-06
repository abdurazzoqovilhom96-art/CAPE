// CC -> candidate incidence in CSR form and memory forecasts (spec sections 7, 39.3).
#pragma once

#include <cstdint>
#include <vector>

#include "cape/candidates.hpp"
#include "cape/types.hpp"

namespace cape {

struct Incidence {
  std::vector<uint64_t> off;  // N + 1
  std::vector<uint32_t> idx;  // positions into the `alive` list, ascending per CC
};

Incidence build_cc_incidence(const std::vector<uint32_t>& alive, const std::vector<Candidate>& cands,
                             const ChainAccess& ch, uint64_t N);

// Conservative peak estimate (bytes) of the solver working set for one regime.
uint64_t forecast_solver_bytes(uint64_t V, uint64_t N, uint64_t runs, uint64_t M, uint64_t E);

// Throws MemoryCapExceeded (-> status OOM, reason OOM_PREVENTED) instead of pruning silently.
void check_memory(uint64_t bytes, uint64_t cap, const char* what);

}  // namespace cape
