// v3 M3: bounds from the integer dual (docs/V3_MATHEMATICS.md, section M3). QUALITY mode only.
//
// For a feasible dual a (q-scaled, a_u <= q s, sum over each pin <= q c) and any cover x,
//   q cost(x) = sum_u a_u cover_count(u) + sum_j slack_j x_j >= sum_u a_u + sum_j slack_j x_j,
// slack_j = q c_j - sum_{u in C_j} a_u >= 0 (pins and singletons). A cover strictly cheaper than the
// incumbent UB costs <= UB - 1 (integer costs), so an item with sum a + (forced slack) + slack_j > q (UB-1)
// is in no such cover (reduced-cost fixing); an item that is the last remaining option of a CC is in every
// such cover (forcing). If no option is left for some CC, the incumbent is optimal for the component model.
#pragma once

#include <cstdint>

#include "cape/components.hpp"
#include "cape/greedy.hpp"

namespace cape {

enum class FixOutcome : int { Proven = 0, Improved = 1, Unresolved = 2 };

struct FixResult {
  FixOutcome outcome = FixOutcome::Unresolved;
  Selection sel;              // Improved: the optimal cover of the component model
  uint64_t fixed_out = 0;     // items fixed to 0
  uint64_t forced_in = 0;     // items forced to 1
  uint64_t residual_n = 0;    // CCs left for the exact DP
  uint64_t transitions = 0;
};

// ub = current component cost (incumbent). Never returns a cover with cost >= ub as Improved.
FixResult reduced_cost_solve(const LocalModel& m, uint64_t ub, uint64_t q, int max_residual_cc,
                             uint64_t per_component_transitions, uint64_t max_states, uint64_t& remaining_total);

// ceil(c_r * dual_sum_q / (q * c_full)), exact in 128-bit arithmetic: a valid lower bound on a label's
// records cost in a narrower depth regime r (pin cost c_r) from the full-width dual (pin cost c_full).
uint64_t scaled_dual_bound(uint64_t dual_sum_q, uint64_t c_r, uint64_t c_full, uint64_t q);

}  // namespace cape
