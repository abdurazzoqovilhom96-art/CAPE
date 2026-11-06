// v3 M4: bounded exact repair (a deterministic large-neighbourhood step) for heuristic components.
//
// Incumbent cover S of a component. A subset A of S is released; F = S \ A stays fixed; the CCs no
// longer covered, R = U \ cover(F) (|R| <= max_r), are re-covered optimally with a pool P of pins that meet
// R (always including A's pins, so the old choice stays feasible) and R's singletons, by the exact
// reachable-state DP under a deterministic transition / state budget. The move is kept only when the
// component cost strictly drops; the encoder additionally keeps the regime result only when the whole
// labels section gets strictly smaller. Never a global optimality claim.
#pragma once

#include <cstdint>

#include "cape/components.hpp"
#include "cape/greedy.hpp"

namespace cape {

struct RepairParams {
  uint32_t max_r = 24;
  uint32_t max_pool = 512;
  uint32_t attempts = 1;
  uint64_t per_attempt_transitions = 5'000'000ull;
  uint64_t max_states = uint64_t{1} << 20;
  uint64_t q = uint64_t{1} << 20;  // dual scale (seed ordering only)
};

struct RepairStats {
  uint64_t attempts = 0;
  uint64_t accepted = 0;
  uint64_t transitions = 0;
  uint64_t saved = 0;          // component-model cost removed
  uint64_t dp_unsolved = 0;    // neighbourhood DP hit its budget
};

Selection component_repair(const LocalModel& m, const Selection& start, const RepairParams& prm,
                           uint64_t& remaining_total, RepairStats& st);

}  // namespace cape
