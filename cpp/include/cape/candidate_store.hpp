// v3 M1a: candidate generation with exact on-the-fly duplicate filtering.
//
// Claim (docs/V3_MATHEMATICS.md, section M1): let p be a candidate of column (x, y) with z-range
// [zs, zs + len) and dense label l. If column (x - 1, y) or (x, y - 1) has a candidate q with the same
// z-range and label, then chain(p) == chain(q): at every slice z of the range both voxels carry label l
// and are 4-neighbours, so the upstream 4-connected 2D labeling puts them in the same CC. q's start
// index is smaller (by 1 or by X), so p is never the smallest-start member of its equal-coverage class
// and the equal-coverage reduction would discard it anyway. Dropping p therefore leaves the set of class
// representatives - and every later step and byte - unchanged; only fewer chains are hashed.
#pragma once

#include <cstdint>
#include <vector>

#include "cape/candidates.hpp"
#include "cape/types.hpp"

namespace cape {

struct CandidateGenStats {
  uint64_t total = 0;            // candidates of the regime (== forecast_candidates().candidates)
  uint64_t after_singleton = 0;  // not removed by singleton dominance
  uint64_t adjacent_dropped = 0; // removed by the neighbour-column rule
};

// Candidates that survive singleton dominance (if enabled) and the neighbour-column rule, in the same
// relative order as make_candidates(). X is the volume width, XY the slice size.
std::vector<Candidate> make_candidates_dedup(const std::vector<Run>& runs, uint64_t h, CandidatePolicy policy,
                                             uint64_t X, uint64_t XY, bool singleton_rule, uint64_t pin_cost,
                                             uint64_t single_cost, CandidateGenStats& st);

}  // namespace cape
