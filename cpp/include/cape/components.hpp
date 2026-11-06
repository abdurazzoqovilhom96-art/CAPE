// Independent parts of the CC-pin incidence graph (spec section 9) and the per-component
// local model consumed by the solvers.
#pragma once

#include <cstdint>
#include <vector>

#include "cape/candidates.hpp"
#include "cape/types.hpp"

namespace cape {

struct Components {
  uint32_t count = 0;
  std::vector<uint32_t> comp_of_cc;  // N
  std::vector<uint64_t> cc_off;      // count + 1
  std::vector<uint32_t> ccs;         // CC ids per component, ascending
  std::vector<uint64_t> cand_off;    // count + 1
  std::vector<uint32_t> cands;       // positions into `alive`, ascending
};

// Components are numbered by their smallest CC id (deterministic).
Components find_components(const std::vector<uint32_t>& alive, const std::vector<Candidate>& cands,
                           const ChainAccess& ch, uint64_t N);

// Weighted set cover of one component with uniform costs (all pins cost c, singletons cost s).
struct LocalModel {
  uint32_t n = 0;                   // CCs (local ids follow ascending global ids)
  std::vector<uint32_t> global_cc;  // n
  std::vector<uint32_t> cand;       // M: global candidate index (into cands), ascending
  std::vector<uint64_t> tie_start;  // M: upstream start index (tie-break key)
  std::vector<uint32_t> tie_depth;  // M
  std::vector<uint64_t> off;        // M + 1
  std::vector<uint32_t> elem;       // local CC ids per candidate, ascending
  std::vector<uint64_t> inc_off;    // n + 1
  std::vector<uint32_t> inc;        // local candidate ids per CC, ascending
  uint64_t c = 0;
  uint64_t s = 0;

  uint32_t M() const { return static_cast<uint32_t>(cand.size()); }
};

// local_scratch must have size N; it is used as a global->local map and left dirty.
LocalModel build_local_model(const Components& comps, uint32_t k, const std::vector<uint32_t>& alive,
                             const std::vector<Candidate>& cands, const ChainAccess& ch,
                             std::vector<uint32_t>& local_scratch, uint64_t pin_cost, uint64_t single_cost);

// Abstract model (tests): sets over 0..n-1, tie keys = (index, |set|-1).
LocalModel make_abstract_model(uint32_t n, const std::vector<std::vector<uint32_t>>& sets, uint64_t pin_cost,
                               uint64_t single_cost);

void finalize_incidence(LocalModel& m);

}  // namespace cape
