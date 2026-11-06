#include "cape/components.hpp"

#include <algorithm>
#include <numeric>

namespace cape {

namespace {

struct UnionFind {
  std::vector<uint32_t> parent;
  explicit UnionFind(uint64_t n) : parent(n) { std::iota(parent.begin(), parent.end(), 0u); }
  uint32_t find(uint32_t a) {
    while (parent[a] != a) {
      parent[a] = parent[parent[a]];
      a = parent[a];
    }
    return a;
  }
  void unite(uint32_t a, uint32_t b) {
    a = find(a);
    b = find(b);
    if (a == b) return;
    if (a < b) {
      parent[b] = a;
    } else {
      parent[a] = b;
    }
  }
};

}  // namespace

Components find_components(const std::vector<uint32_t>& alive, const std::vector<Candidate>& cands,
                           const ChainAccess& ch, uint64_t N) {
  Components out;
  UnionFind uf(N);
  for (uint32_t p : alive) {
    const Candidate& c = cands[p];
    const uint32_t first = ch.at(c, 0);
    for (uint32_t t = 1; t < c.len; t++) uf.unite(first, ch.at(c, t));
  }
  constexpr uint32_t kUnset = 0xFFFFFFFFu;
  std::vector<uint32_t> id_of_root(N, kUnset);
  out.comp_of_cc.resize(N);
  uint32_t next = 0;
  for (uint64_t u = 0; u < N; u++) {
    const uint32_t r = uf.find(static_cast<uint32_t>(u));
    if (id_of_root[r] == kUnset) id_of_root[r] = next++;
    out.comp_of_cc[u] = id_of_root[r];
  }
  out.count = next;
  // comp -> CCs (counting sort keeps ascending CC ids)
  out.cc_off.assign(next + 1, 0);
  for (uint64_t u = 0; u < N; u++) out.cc_off[out.comp_of_cc[u] + 1]++;
  for (uint32_t k = 0; k < next; k++) out.cc_off[k + 1] += out.cc_off[k];
  out.ccs.resize(N);
  {
    std::vector<uint64_t> pos(out.cc_off.begin(), out.cc_off.end() - 1);
    for (uint64_t u = 0; u < N; u++) out.ccs[pos[out.comp_of_cc[u]]++] = static_cast<uint32_t>(u);
  }
  // comp -> candidate positions
  out.cand_off.assign(next + 1, 0);
  for (uint32_t p = 0; p < alive.size(); p++) out.cand_off[out.comp_of_cc[ch.at(cands[alive[p]], 0)] + 1]++;
  for (uint32_t k = 0; k < next; k++) out.cand_off[k + 1] += out.cand_off[k];
  out.cands.resize(alive.size());
  {
    std::vector<uint64_t> pos(out.cand_off.begin(), out.cand_off.end() - 1);
    for (uint32_t p = 0; p < alive.size(); p++) out.cands[pos[out.comp_of_cc[ch.at(cands[alive[p]], 0)]]++] = p;
  }
  return out;
}

void finalize_incidence(LocalModel& m) {
  const uint32_t M = m.M();
  m.inc_off.assign(m.n + 1, 0);
  for (uint32_t p = 0; p < M; p++) {
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) m.inc_off[m.elem[k] + 1]++;
  }
  for (uint32_t u = 0; u < m.n; u++) m.inc_off[u + 1] += m.inc_off[u];
  m.inc.resize(m.inc_off[m.n]);
  std::vector<uint64_t> pos(m.inc_off.begin(), m.inc_off.end() - 1);
  for (uint32_t p = 0; p < M; p++) {
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) m.inc[pos[m.elem[k]]++] = p;
  }
}

LocalModel build_local_model(const Components& comps, uint32_t k, const std::vector<uint32_t>& alive,
                             const std::vector<Candidate>& cands, const ChainAccess& ch,
                             std::vector<uint32_t>& local_scratch, uint64_t pin_cost, uint64_t single_cost) {
  LocalModel m;
  m.c = pin_cost;
  m.s = single_cost;
  m.n = static_cast<uint32_t>(comps.cc_off[k + 1] - comps.cc_off[k]);
  m.global_cc.assign(comps.ccs.begin() + comps.cc_off[k], comps.ccs.begin() + comps.cc_off[k + 1]);
  for (uint32_t i = 0; i < m.n; i++) local_scratch[m.global_cc[i]] = i;
  const uint64_t M = comps.cand_off[k + 1] - comps.cand_off[k];
  m.cand.reserve(M);
  m.tie_start.reserve(M);
  m.tie_depth.reserve(M);
  m.off.reserve(M + 1);
  m.off.push_back(0);
  for (uint64_t j = comps.cand_off[k]; j < comps.cand_off[k + 1]; j++) {
    const uint32_t gi = alive[comps.cands[j]];
    const Candidate& c = cands[gi];
    m.cand.push_back(gi);
    m.tie_start.push_back(ch.start_index(c));
    m.tie_depth.push_back(c.len - 1);
    for (uint32_t t = 0; t < c.len; t++) m.elem.push_back(local_scratch[ch.at(c, t)]);
    m.off.push_back(m.elem.size());
  }
  finalize_incidence(m);
  return m;
}

LocalModel make_abstract_model(uint32_t n, const std::vector<std::vector<uint32_t>>& sets, uint64_t pin_cost,
                               uint64_t single_cost) {
  LocalModel m;
  m.n = n;
  m.c = pin_cost;
  m.s = single_cost;
  m.global_cc.resize(n);
  std::iota(m.global_cc.begin(), m.global_cc.end(), 0u);
  m.off.push_back(0);
  for (uint32_t p = 0; p < sets.size(); p++) {
    std::vector<uint32_t> s = sets[p];
    std::sort(s.begin(), s.end());
    s.erase(std::unique(s.begin(), s.end()), s.end());
    if (s.empty() || s.back() >= n) throw CapeError("abstract model: set out of range or empty");
    m.cand.push_back(p);
    m.tie_start.push_back(p);
    m.tie_depth.push_back(static_cast<uint32_t>(s.size() - 1));
    m.elem.insert(m.elem.end(), s.begin(), s.end());
    m.off.push_back(m.elem.size());
  }
  finalize_incidence(m);
  return m;
}

}  // namespace cape
