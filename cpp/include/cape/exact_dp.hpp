// Exact bitmask DP for small components (spec section 10). From each reachable mask only the
// actions covering its lowest uncovered CC are relaxed (every cover can be ordered that way),
// which is exact and never visits more transitions than the plain recurrence (6).
// Budgets are counted in transitions (deterministic), never in wall-clock time.
#pragma once

#include <cstdint>

#include "cape/greedy.hpp"

namespace cape {

enum class DpOutcome : int {
  Solved = 0, SkippedSize = 1, SkippedForecast = 2, SkippedMemory = 3, BudgetExhausted = 4,
  Infeasible = 5  // v3: no cover exists with the allowed actions (LocalModel::no_single)
};

struct DpLimits {
  int max_cc = 20;
  uint64_t per_component = 50'000'000ull;
  uint64_t memory_bytes = uint64_t{64} << 20;
  // v2: visit only reachable masks (ascending, hash map + min-heap) instead of all 2^n. The
  // admission rules above are unchanged and the result (cover, cost, transitions) is identical.
  bool sparse_states = false;
  // v3 (M3b / M4): admit any n <= 30 and rely on the deterministic budgets instead of the dense
  // 2^n memory / forecast gates; always uses the reachable-state DP. max_states (> 0) stops the
  // search as BudgetExhausted when more reachable states would be stored.
  bool sparse_admission = false;
  uint64_t max_states = 0;
};

struct DpResult {
  DpOutcome outcome = DpOutcome::SkippedSize;
  Selection sel;
  uint64_t transitions = 0;
  uint64_t forecast = 0;
};

// remaining_total is decreased by the transitions actually performed.
DpResult exact_dp(const LocalModel& m, const DpLimits& lim, uint64_t& remaining_total);

}  // namespace cape
