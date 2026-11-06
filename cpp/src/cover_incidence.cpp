#include "cape/cover_incidence.hpp"

#include <algorithm>

namespace cape {

ComponentCsr build_component_csr(const Components& comps, const std::vector<uint32_t>& alive,
                                 const std::vector<Candidate>& cands, const ChainAccess& ch,
                                 std::vector<uint32_t>& local_scratch) {
  ComponentCsr csr;
  const size_t A = alive.size();
  for (uint32_t k = 0; k < comps.count; k++) {
    for (uint64_t i = comps.cc_off[k]; i < comps.cc_off[k + 1]; i++) {
      local_scratch[comps.ccs[i]] = static_cast<uint32_t>(i - comps.cc_off[k]);
    }
  }
  std::vector<uint32_t> pos_of(A);
  for (size_t j = 0; j < A; j++) pos_of[comps.cands[j]] = static_cast<uint32_t>(j);
  csr.elem_off.assign(A + 1, 0);
  for (size_t j = 0; j < A; j++) csr.elem_off[j + 1] = cands[alive[comps.cands[j]]].len;
  for (size_t j = 0; j < A; j++) csr.elem_off[j + 1] += csr.elem_off[j];
  csr.elem.resize(csr.elem_off[A]);
  csr.tie_start.resize(A);
  csr.tie_depth.resize(A);
  csr.cand.resize(A);
  for (size_t p = 0; p < A; p++) {  // ascending candidate index: sequential chain reads
    const uint32_t j = pos_of[p];
    const Candidate& c = cands[alive[p]];
    uint32_t* dst = csr.elem.data() + csr.elem_off[j];
    if (ch.colmajor) {
      const uint32_t* src = ch.chain(c);
      for (uint32_t t = 0; t < c.len; t++) dst[t] = local_scratch[src[t]];
    } else {
      for (uint32_t t = 0; t < c.len; t++) dst[t] = local_scratch[ch.at(c, t)];
    }
    csr.tie_start[j] = ch.start_index(c);
    csr.tie_depth[j] = c.len - 1;
    csr.cand[j] = alive[p];
  }
  return csr;
}

void build_local_model_csr(LocalModel& m, const Components& comps, const ComponentCsr& csr, uint32_t k,
                           uint64_t pin_cost, uint64_t single_cost, std::vector<uint64_t>& pos_scratch) {
  m.c = pin_cost;
  m.s = single_cost;
  m.no_single.clear();
  const uint64_t c0 = comps.cc_off[k], c1 = comps.cc_off[k + 1];
  m.n = static_cast<uint32_t>(c1 - c0);
  m.global_cc.assign(comps.ccs.begin() + c0, comps.ccs.begin() + c1);
  const uint64_t j0 = comps.cand_off[k], j1 = comps.cand_off[k + 1];
  m.cand.assign(csr.cand.begin() + j0, csr.cand.begin() + j1);
  m.tie_start.assign(csr.tie_start.begin() + j0, csr.tie_start.begin() + j1);
  m.tie_depth.assign(csr.tie_depth.begin() + j0, csr.tie_depth.begin() + j1);
  const uint64_t e0 = csr.elem_off[j0];
  m.off.resize(j1 - j0 + 1);
  for (uint64_t i = 0; i <= j1 - j0; i++) m.off[i] = csr.elem_off[j0 + i] - e0;
  m.elem.assign(csr.elem.begin() + e0, csr.elem.begin() + csr.elem_off[j1]);
  // finalize_incidence with a reused position buffer (identical result)
  const uint32_t M = m.M();
  m.inc_off.assign(m.n + 1, 0);
  for (uint64_t q = 0; q < m.elem.size(); q++) m.inc_off[m.elem[q] + 1]++;
  for (uint32_t u = 0; u < m.n; u++) m.inc_off[u + 1] += m.inc_off[u];
  m.inc.resize(m.inc_off[m.n]);
  pos_scratch.assign(m.inc_off.begin(), m.inc_off.end() - 1);
  for (uint32_t p = 0; p < M; p++) {
    for (uint64_t q = m.off[p]; q < m.off[p + 1]; q++) m.inc[pos_scratch[m.elem[q]]++] = p;
  }
}

Selection greedy_eager(const LocalModel& m, GreedyScratch& sc) {
  const uint32_t M = m.M();
  // lower priority = fewer new CCs, then larger start index, then larger depth (same as greedy())
  auto lower = [](const GreedyEntry& a, const GreedyEntry& b) {
    if (a.fresh != b.fresh) return a.fresh < b.fresh;
    if (a.start != b.start) return a.start > b.start;
    if (a.depth != b.depth) return a.depth > b.depth;
    return a.p > b.p;
  };
  sc.fresh.resize(M);
  sc.chosen.assign(M, 0);
  sc.covered.assign(m.n, 0);
  sc.heap.clear();
  sc.order.clear();
  for (uint32_t p = 0; p < M; p++) {
    const uint32_t len = static_cast<uint32_t>(m.off[p + 1] - m.off[p]);
    sc.fresh[p] = len;
    if (m.c < m.s * len) sc.heap.push_back(GreedyEntry{len, m.tie_start[p], m.tie_depth[p], p});
  }
  std::make_heap(sc.heap.begin(), sc.heap.end(), lower);
  while (!sc.heap.empty()) {
    std::pop_heap(sc.heap.begin(), sc.heap.end(), lower);
    const GreedyEntry e = sc.heap.back();
    sc.heap.pop_back();
    if (sc.chosen[e.p] || sc.fresh[e.p] != e.fresh) continue;  // superseded entry
    sc.chosen[e.p] = 1;
    sc.order.push_back(e.p);
    for (uint64_t k = m.off[e.p]; k < m.off[e.p + 1]; k++) {
      const uint32_t u = m.elem[k];
      if (sc.covered[u]) continue;
      sc.covered[u] = 1;
      for (uint64_t kk = m.inc_off[u]; kk < m.inc_off[u + 1]; kk++) {
        const uint32_t q = m.inc[kk];
        const uint32_t f = --sc.fresh[q];
        if (!sc.chosen[q] && f > 0 && m.c < m.s * f) {
          sc.heap.push_back(GreedyEntry{f, m.tie_start[q], m.tie_depth[q], q});
          std::push_heap(sc.heap.begin(), sc.heap.end(), lower);
        }
      }
    }
  }
  Selection sel;
  for (uint32_t u = 0; u < m.n; u++) {
    if (!sc.covered[u]) sel.singles.push_back(u);
  }
  // redundancy elimination in reverse selection order (identical to greedy())
  sc.cnt.assign(m.n, 0);
  for (uint32_t p : sc.order) {
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) sc.cnt[m.elem[k]]++;
  }
  for (uint32_t u : sel.singles) sc.cnt[u]++;
  sc.keep.assign(sc.order.size(), 1);
  for (size_t i = sc.order.size(); i-- > 0;) {
    const uint32_t p = sc.order[i];
    bool redundant = true;
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) {
      if (sc.cnt[m.elem[k]] < 2) {
        redundant = false;
        break;
      }
    }
    if (redundant) {
      sc.keep[i] = 0;
      for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) sc.cnt[m.elem[k]]--;
    }
  }
  for (size_t i = 0; i < sc.order.size(); i++) {
    if (sc.keep[i]) sel.pins.push_back(sc.order[i]);
  }
  std::sort(sel.pins.begin(), sel.pins.end());
  sel.cost = selection_cost(m, sel);
  return sel;
}

}  // namespace cape
