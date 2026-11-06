// Safe coverage reductions (spec section 8, 39.8). All candidates of one regime share one cost,
// so: singleton dominance (c >= len * s), equal coverage (one deterministic representative,
// hash-bucketed but confirmed by exact chain comparison), proper-subset dominance.
#pragma once

#include <cstdint>
#include <vector>

#include "cape/candidates.hpp"
#include "cape/types.hpp"

namespace cape {

constexpr uint32_t kRemovedBySingletons = 0xFFFFFFFFu;

struct ReductionConfig {
  bool singleton = true;
  bool equal = true;
  bool subset = true;
  uint64_t pin_cost = 0;
  uint64_t single_cost = 0;
  uint64_t subset_check_budget = 0;
  bool hash_grouping = false;  // v2 linear-time equal-coverage grouping (identical result)
  bool fast_hash = false;      // v2 multiply-add chain hash (identical result; independent of the grouping)
  uint64_t hash_mask = ~uint64_t{0};  // tests only: fewer hash bits force collisions
};

struct ReductionStats {
  uint64_t input = 0;
  uint64_t after_singleton = 0;
  uint64_t after_equal = 0;
  uint64_t after_subset = 0;
  uint64_t equal_hash_collisions = 0;  // same hash, different coverage (resolved exactly)
  uint64_t subset_checks = 0;
  bool subset_truncated = false;
  // profile (plan v2 P1.1): wall time of each reduction step
  uint64_t singleton_ns = 0;
  uint64_t equal_hash_ns = 0;   // chain hashing of the survivors
  uint64_t equal_sort_ns = 0;   // bucket sort + exact confirmation
  uint64_t subset_incidence_ns = 0;
  uint64_t subset_scan_ns = 0;
};

// Returns surviving candidate indices (ascending). witness (optional, size M): i for kept,
// kRemovedBySingletons, or the index of a candidate whose coverage contains it (acyclic: equal
// coverage points to the representative, subset dominance to a strictly longer candidate).
std::vector<uint32_t> reduce(const std::vector<Candidate>& cands, const ChainAccess& ch, uint64_t N,
                             const ReductionConfig& cfg, ReductionStats& st, std::vector<uint32_t>* witness);

// Exposed for tests: the hash used to bucket equal coverage.
uint64_t chain_hash(const Candidate& c, const ChainAccess& ch);
// v2 fast path: one multiply-add per CC id and a final mix (grouping is hash-independent).
uint64_t chain_hash_fast(const Candidate& c, const ChainAccess& ch);

}  // namespace cape
