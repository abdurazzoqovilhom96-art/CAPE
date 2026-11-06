// v3 M1b / M2: compact component-ordered incidence and the eager greedy.
#pragma once

#include <cstdint>
#include <vector>

#include "cape/candidates.hpp"
#include "cape/components.hpp"
#include "cape/greedy.hpp"

namespace cape {

// Every surviving candidate's chain, already mapped to component-local CC ids, stored contiguously in
// component order (the order of Components::cands). Built by ONE pass over the candidates in ascending
// index order, i.e. sequential reads of the column-major chain buffer.
struct ComponentCsr {
  std::vector<uint64_t> elem_off;   // A + 1 (A = number of surviving candidates)
  std::vector<uint32_t> elem;       // E: local CC ids
  std::vector<uint64_t> tie_start;  // A
  std::vector<uint32_t> tie_depth;  // A
  std::vector<uint32_t> cand;       // A: global candidate index
};

// local_scratch (size N) receives the component-local id of every CC.
ComponentCsr build_component_csr(const Components& comps, const std::vector<uint32_t>& alive,
                                 const std::vector<Candidate>& cands, const ChainAccess& ch,
                                 std::vector<uint32_t>& local_scratch);

// Fills m (reusing its buffers) with exactly the model build_local_model() returns for component k.
void build_local_model_csr(LocalModel& m, const Components& comps, const ComponentCsr& csr, uint32_t k,
                           uint64_t pin_cost, uint64_t single_cost, std::vector<uint64_t>& pos_scratch);

// Eager weighted greedy: identical selection to greedy() (same rule and tie order); fresh counts are
// maintained exactly by CC -> candidate decrements instead of being recounted on every pop.
struct GreedyEntry {
  uint32_t fresh;
  uint64_t start;
  uint32_t depth;
  uint32_t p;
};
struct GreedyScratch {
  std::vector<GreedyEntry> heap;
  std::vector<uint32_t> fresh;
  std::vector<uint8_t> covered, chosen;
  std::vector<uint32_t> cnt, order;
  std::vector<uint8_t> keep;
};
Selection greedy_eager(const LocalModel& m, GreedyScratch& sc);

}  // namespace cape
