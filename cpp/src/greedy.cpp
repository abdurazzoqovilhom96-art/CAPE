#include "cape/greedy.hpp"

#include <algorithm>
#include <queue>

namespace cape {

uint64_t selection_cost(const LocalModel& m, const Selection& s) {
  return m.c * s.pins.size() + m.s * s.singles.size();
}

bool is_cover(const LocalModel& m, const Selection& s) {
  std::vector<uint8_t> covered(m.n, 0);
  for (uint32_t p : s.pins) {
    if (p >= m.M()) return false;
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) covered[m.elem[k]] = 1;
  }
  for (uint32_t u : s.singles) {
    if (u >= m.n) return false;
    covered[u] = 1;
  }
  return std::all_of(covered.begin(), covered.end(), [](uint8_t v) { return v != 0; });
}

Selection greedy(const LocalModel& m) {
  const uint32_t M = m.M();
  std::vector<uint8_t> covered(m.n, 0);
  struct Entry {
    uint32_t fresh;
    uint64_t start;
    uint32_t depth;
    uint32_t p;
  };
  // lower priority = fewer new CCs, then larger start index, then larger depth
  auto lower = [](const Entry& a, const Entry& b) {
    if (a.fresh != b.fresh) return a.fresh < b.fresh;
    if (a.start != b.start) return a.start > b.start;
    if (a.depth != b.depth) return a.depth > b.depth;
    return a.p > b.p;
  };
  std::priority_queue<Entry, std::vector<Entry>, decltype(lower)> heap(lower);
  for (uint32_t p = 0; p < M; p++) {
    const uint32_t len = static_cast<uint32_t>(m.off[p + 1] - m.off[p]);
    if (m.c < m.s * len) heap.push(Entry{len, m.tie_start[p], m.tie_depth[p], p});
  }
  std::vector<uint32_t> chosen;
  while (!heap.empty()) {
    const Entry e = heap.top();
    heap.pop();
    uint32_t cur = 0;
    for (uint64_t k = m.off[e.p]; k < m.off[e.p + 1]; k++) cur += covered[m.elem[k]] ? 0u : 1u;
    if (cur != e.fresh) {
      if (cur > 0 && m.c < m.s * cur) heap.push(Entry{cur, e.start, e.depth, e.p});
      continue;
    }
    chosen.push_back(e.p);
    for (uint64_t k = m.off[e.p]; k < m.off[e.p + 1]; k++) covered[m.elem[k]] = 1;
  }
  Selection sel;
  for (uint32_t u = 0; u < m.n; u++) {
    if (!covered[u]) sel.singles.push_back(u);
  }
  // redundancy elimination in reverse selection order (singletons are never redundant)
  std::vector<uint32_t> cnt(m.n, 0);
  for (uint32_t p : chosen) {
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) cnt[m.elem[k]]++;
  }
  for (uint32_t u : sel.singles) cnt[u]++;
  std::vector<uint8_t> keep(chosen.size(), 1);
  for (size_t i = chosen.size(); i-- > 0;) {
    const uint32_t p = chosen[i];
    bool redundant = true;
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) {
      if (cnt[m.elem[k]] < 2) {
        redundant = false;
        break;
      }
    }
    if (redundant) {
      keep[i] = 0;
      for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) cnt[m.elem[k]]--;
    }
  }
  for (size_t i = 0; i < chosen.size(); i++) {
    if (keep[i]) sel.pins.push_back(chosen[i]);
  }
  std::sort(sel.pins.begin(), sel.pins.end());
  sel.cost = selection_cost(m, sel);
  return sel;
}

}  // namespace cape
