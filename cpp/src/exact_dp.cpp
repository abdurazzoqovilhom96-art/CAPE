#include "cape/exact_dp.hpp"

#include <algorithm>
#include <bit>
#include <functional>
#include <limits>
#include <queue>
#include <vector>

namespace cape {

namespace {

// Reachable-state version of the dense loop below. Every transition goes from t to a strictly
// larger mask (it adds the lowest uncovered bit), so popping masks in ascending order processes
// each reachable mask after all of its predecessors, with the same action order and the same
// strict-improvement rule: D, parents, transition count and budget stop are identical.
DpResult exact_dp_sparse(const LocalModel& m, const std::vector<uint32_t>& mask, uint32_t full, const DpLimits& lim,
                         uint64_t& remaining_total, DpResult& r) {
  constexpr uint32_t INF = std::numeric_limits<uint32_t>::max();
  constexpr uint32_t EMPTY = std::numeric_limits<uint32_t>::max();
  const uint32_t M = m.M();
  struct Entry {
    uint32_t key = EMPTY;
    uint32_t D = INF;
    uint32_t pm = 0;
    uint32_t pa = 0;
  };
  size_t cap = 1024;
  std::vector<Entry> tab(cap);
  size_t used = 0;
  auto slot_of = [&](uint32_t key) -> size_t {
    size_t h = (static_cast<uint64_t>(key) * 0x9e3779b97f4a7c15ull) >> 20;
    for (size_t i = h & (cap - 1);; i = (i + 1) & (cap - 1)) {
      if (tab[i].key == key || tab[i].key == EMPTY) return i;
    }
  };
  std::priority_queue<uint32_t, std::vector<uint32_t>, std::greater<uint32_t>> heap;
  auto get = [&](uint32_t key, bool& fresh) -> Entry& {
    if (2 * (used + 1) > cap) {
      std::vector<Entry> old;
      old.swap(tab);
      cap *= 2;
      tab.assign(cap, Entry{});
      for (const Entry& e : old) {
        if (e.key != EMPTY) tab[slot_of(e.key)] = e;
      }
    }
    const size_t i = slot_of(key);
    fresh = tab[i].key == EMPTY;
    if (fresh) {
      tab[i].key = key;
      used++;
    }
    return tab[i];
  };
  bool fresh = false;
  get(0, fresh).D = 0;
  heap.push(0);
  const uint32_t c = static_cast<uint32_t>(m.c), s = static_cast<uint32_t>(m.s);
  uint64_t trans = 0;
  const uint64_t limit = std::min(lim.per_component, remaining_total);
  while (!heap.empty()) {
    const uint32_t t = heap.top();
    heap.pop();
    if (t == full) continue;
    const uint32_t Dt = tab[slot_of(t)].D;
    const uint32_t low = static_cast<uint32_t>(std::countr_one(t));
    auto relax = [&](uint32_t t2, uint32_t cost, uint32_t action) {
      Entry& e = get(t2, fresh);
      if (fresh) heap.push(t2);
      if (Dt + cost < e.D) {
        e.D = Dt + cost;
        e.pm = t;
        e.pa = action;
      }
    };
    for (uint64_t k = m.inc_off[low]; k < m.inc_off[low + 1]; k++) {
      const uint32_t p = m.inc[k];
      trans++;
      relax(t | mask[p], c, p);
    }
    trans++;
    relax(t | (1u << low), s, M + low);
    if (trans > limit) {
      r.outcome = DpOutcome::BudgetExhausted;
      r.transitions = trans;
      remaining_total -= std::min(remaining_total, trans);
      return r;
    }
  }
  r.transitions = trans;
  remaining_total -= std::min(remaining_total, trans);
  uint32_t t = full;
  while (t) {
    const Entry& e = tab[slot_of(t)];
    if (e.pa < M) {
      r.sel.pins.push_back(e.pa);
    } else {
      r.sel.singles.push_back(e.pa - M);
    }
    t = e.pm;
  }
  std::sort(r.sel.pins.begin(), r.sel.pins.end());
  std::sort(r.sel.singles.begin(), r.sel.singles.end());
  r.sel.cost = tab[slot_of(full)].D;
  r.outcome = DpOutcome::Solved;
  return r;
}

}  // namespace

DpResult exact_dp(const LocalModel& m, const DpLimits& lim, uint64_t& remaining_total) {
  DpResult r;
  const uint32_t n = m.n;
  const uint32_t M = m.M();
  if (n == 0) {
    r.outcome = DpOutcome::Solved;
    return r;
  }
  if (static_cast<int>(n) > lim.max_cc || n > 30) {
    r.outcome = DpOutcome::SkippedSize;
    return r;
  }
  const uint64_t states = uint64_t{1} << n;
  const uint64_t bytes = states * 12ull;
  if (bytes > lim.memory_bytes) {
    r.outcome = DpOutcome::SkippedMemory;
    return r;
  }
  // actions: candidates 0..M-1, singleton of CC b is action M + b
  std::vector<uint32_t> mask(M, 0);
  for (uint32_t p = 0; p < M; p++) {
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) mask[p] |= (1u << m.elem[k]);
  }
  uint64_t max_deg = 0;
  for (uint32_t b = 0; b < n; b++) max_deg = std::max<uint64_t>(max_deg, (m.inc_off[b + 1] - m.inc_off[b]) + 1);
  r.forecast = states * max_deg;
  if (r.forecast > lim.per_component || r.forecast > remaining_total) {
    r.outcome = DpOutcome::SkippedForecast;
    return r;
  }
  constexpr uint32_t INF = std::numeric_limits<uint32_t>::max();
  const uint32_t full = static_cast<uint32_t>(states - 1);
  if (lim.sparse_states && n > 12) return exact_dp_sparse(m, mask, full, lim, remaining_total, r);
  std::vector<uint32_t> D(states, INF), pm(states, 0), pa(states, 0);
  D[0] = 0;
  const uint32_t c = static_cast<uint32_t>(m.c), s = static_cast<uint32_t>(m.s);
  uint64_t trans = 0;
  const uint64_t limit = std::min(lim.per_component, remaining_total);
  for (uint32_t t = 0; t < full; t++) {
    if (D[t] == INF) continue;
    const uint32_t low = static_cast<uint32_t>(std::countr_one(t));
    for (uint64_t k = m.inc_off[low]; k < m.inc_off[low + 1]; k++) {
      const uint32_t p = m.inc[k];
      const uint32_t t2 = t | mask[p];
      trans++;
      if (D[t] + c < D[t2]) {
        D[t2] = D[t] + c;
        pm[t2] = t;
        pa[t2] = p;
      }
    }
    {
      const uint32_t t2 = t | (1u << low);
      trans++;
      if (D[t] + s < D[t2]) {
        D[t2] = D[t] + s;
        pm[t2] = t;
        pa[t2] = M + low;
      }
    }
    if (trans > limit) {
      r.outcome = DpOutcome::BudgetExhausted;
      r.transitions = trans;
      remaining_total -= std::min(remaining_total, trans);
      return r;
    }
  }
  r.transitions = trans;
  remaining_total -= std::min(remaining_total, trans);
  uint32_t t = full;
  while (t) {
    const uint32_t a = pa[t];
    if (a < M) {
      r.sel.pins.push_back(a);
    } else {
      r.sel.singles.push_back(a - M);
    }
    t = pm[t];
  }
  std::sort(r.sel.pins.begin(), r.sel.pins.end());
  std::sort(r.sel.singles.begin(), r.sel.singles.end());
  r.sel.cost = D[full];
  r.outcome = DpOutcome::Solved;
  return r;
}

}  // namespace cape
