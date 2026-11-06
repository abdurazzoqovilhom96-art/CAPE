// Budgeted local improvement for components that are not solved exactly (spec section 11).
// Moves (neighbours from the CC -> candidate incidence, never blind all-pairs):
//   add-drop     add an unselected pin, drop singletons/pins it makes redundant (1->1 with
//                absorption, 2->1, singleton -> pin)
//   drop-repair  remove a selected pin, repair its now-uncovered CCs with the best other pins
//                (same ratio rule as greedy) or singletons, drop what became redundant (1->2,
//                pin -> singletons, 1->1)
// A move is kept only if the integer cost strictly decreases, so cycling is impossible.
#pragma once

#include <cstdint>

#include "cape/greedy.hpp"

namespace cape {

struct LocalStats {
  uint64_t checks = 0;
  uint64_t improvements = 0;
};

Selection local_search(const LocalModel& m, const Selection& start, uint64_t per_component_budget,
                       uint64_t& remaining_total, LocalStats& st);

}  // namespace cape
