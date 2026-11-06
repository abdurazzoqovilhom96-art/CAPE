#include "cape/component_repair.hpp"

#include <algorithm>

#include "cape/dual_bound.hpp"
#include "cape/exact_dp.hpp"

namespace cape {

Selection component_repair(const LocalModel& m, const Selection& start, const RepairParams& prm,
                           uint64_t& remaining_total, RepairStats& st) {
  const uint32_t n = m.n, M = m.M();
  Selection cur = start;
  if (n == 0 || prm.attempts == 0) return cur;
  const DualResult dr = dual_ascent(m, prm.q);
  std::vector<uint64_t> pin_slack(M), single_slack(n);
  for (uint32_t p = 0; p < M; p++) {
    uint64_t s = 0;
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) s += dr.a[m.elem[k]];
    pin_slack[p] = prm.q * m.c - std::min(prm.q * m.c, s);
  }
  for (uint32_t u = 0; u < n; u++) single_slack[u] = prm.q * m.s - std::min(prm.q * m.s, dr.a[u]);

  std::vector<uint8_t> in_pin(M), in_single(n), a_pin(M), a_single(n), in_r(n), in_pool(M);
  std::vector<uint32_t> cov(n), acov(n), loc(n), rcount(M);
  for (uint32_t attempt = 0; attempt < prm.attempts && remaining_total > 0; attempt++) {
    std::fill(in_pin.begin(), in_pin.end(), 0);
    std::fill(in_single.begin(), in_single.end(), 0);
    std::fill(cov.begin(), cov.end(), 0);
    for (uint32_t p : cur.pins) {
      in_pin[p] = 1;
      for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) cov[m.elem[k]]++;
    }
    for (uint32_t u : cur.singles) {
      in_single[u] = 1;
      cov[u]++;
    }
    // deterministic seeds: selected pins by dual slack (desc), start (asc); then selected singletons
    struct Seed {
      uint8_t kind;  // 0 pin, 1 singleton
      uint64_t slack;
      uint64_t key;
      uint32_t id;
    };
    std::vector<Seed> seeds;
    for (uint32_t p : cur.pins) seeds.push_back(Seed{0, pin_slack[p], m.tie_start[p], p});
    for (uint32_t u : cur.singles) seeds.push_back(Seed{1, single_slack[u], u, u});
    std::sort(seeds.begin(), seeds.end(), [](const Seed& a, const Seed& b) {
      if (a.kind != b.kind) return a.kind < b.kind;
      if (a.slack != b.slack) return a.slack > b.slack;
      if (a.key != b.key) return a.key < b.key;
      return a.id < b.id;
    });
    if (attempt >= seeds.size()) break;
    st.attempts++;

    std::fill(a_pin.begin(), a_pin.end(), 0);
    std::fill(a_single.begin(), a_single.end(), 0);
    std::fill(acov.begin(), acov.end(), 0);
    std::fill(in_r.begin(), in_r.end(), 0);
    std::vector<uint32_t> R, A_pins, A_singles;
    auto try_add = [&](bool pin, uint32_t id) -> bool {
      if (pin ? a_pin[id] : a_single[id]) return true;
      uint32_t add = 0;
      if (pin) {
        for (uint64_t k = m.off[id]; k < m.off[id + 1]; k++) add += (acov[m.elem[k]] + 1 == cov[m.elem[k]]) ? 1u : 0u;
      } else {
        add = (acov[id] + 1 == cov[id]) ? 1u : 0u;
      }
      if (R.size() + add > prm.max_r) return false;
      auto touch = [&](uint32_t u) {
        if (++acov[u] == cov[u] && !in_r[u]) {
          in_r[u] = 1;
          R.push_back(u);
        }
      };
      if (pin) {
        a_pin[id] = 1;
        A_pins.push_back(id);
        for (uint64_t k = m.off[id]; k < m.off[id + 1]; k++) touch(m.elem[k]);
      } else {
        a_single[id] = 1;
        A_singles.push_back(id);
        touch(id);
      }
      return true;
    };
    const Seed& sd = seeds[attempt];
    if (!try_add(sd.kind == 0, sd.id)) continue;
    uint64_t work = 0;
    constexpr uint64_t kWorkCap = 200'000;
    for (size_t i = 0; i < R.size() && work < kWorkCap; i++) {
      const uint32_t u = R[i];
      for (uint64_t k = m.inc_off[u]; k < m.inc_off[u + 1] && work < kWorkCap; k++) {
        const uint32_t j = m.inc[k];
        for (uint64_t e = m.off[j]; e < m.off[j + 1]; e++) {
          const uint32_t v = m.elem[e];
          work++;
          if (in_r[v]) continue;
          if (in_single[v]) try_add(false, v);
          for (uint64_t kk = m.inc_off[v]; kk < m.inc_off[v + 1]; kk++) {
            work++;
            if (in_pin[m.inc[kk]]) try_add(true, m.inc[kk]);
          }
        }
      }
    }
    // pool: A's pins first, then pins meeting R by |C_j cap R| (desc), start (asc), id (asc)
    std::vector<uint32_t> others;
    for (uint32_t p : A_pins) in_pool[p] = 1;
    for (uint32_t u : R) {
      for (uint64_t k = m.inc_off[u]; k < m.inc_off[u + 1]; k++) {
        const uint32_t j = m.inc[k];
        if (!in_pool[j] && !in_pin[j]) {
          in_pool[j] = 1;
          others.push_back(j);
        }
      }
    }
    for (uint32_t j : others) {
      uint32_t r = 0;
      for (uint64_t e = m.off[j]; e < m.off[j + 1]; e++) r += in_r[m.elem[e]];
      rcount[j] = r;
    }
    std::sort(others.begin(), others.end(), [&](uint32_t a, uint32_t b) {
      if (rcount[a] != rcount[b]) return rcount[a] > rcount[b];
      if (m.tie_start[a] != m.tie_start[b]) return m.tie_start[a] < m.tie_start[b];
      return a < b;
    });
    std::vector<uint32_t> pool(A_pins);
    std::sort(pool.begin(), pool.end());
    for (uint32_t j : others) {
      if (pool.size() >= std::max<size_t>(prm.max_pool, A_pins.size())) break;
      pool.push_back(j);
    }
    for (uint32_t p : A_pins) in_pool[p] = 0;
    for (uint32_t j : others) in_pool[j] = 0;
    // neighbourhood model over R (ascending local ids)
    std::vector<uint32_t> Rs(R);
    std::sort(Rs.begin(), Rs.end());
    for (uint32_t i = 0; i < Rs.size(); i++) loc[Rs[i]] = i;
    LocalModel sub;
    sub.n = static_cast<uint32_t>(Rs.size());
    sub.c = m.c;
    sub.s = m.s;
    sub.global_cc = Rs;
    sub.off.push_back(0);
    std::vector<uint32_t> sub_pin;
    for (uint32_t j : pool) {
      const size_t before = sub.elem.size();
      for (uint64_t e = m.off[j]; e < m.off[j + 1]; e++) {
        if (in_r[m.elem[e]]) sub.elem.push_back(loc[m.elem[e]]);
      }
      if (sub.elem.size() == before) continue;  // an A pin made redundant by F: dropping it is free
      sub_pin.push_back(j);
      sub.cand.push_back(j);
      sub.tie_start.push_back(m.tie_start[j]);
      sub.tie_depth.push_back(m.tie_depth[j]);
      sub.off.push_back(sub.elem.size());
    }
    finalize_incidence(sub);
    DpLimits lim;
    lim.max_cc = 30;
    lim.per_component = prm.per_attempt_transitions;
    lim.sparse_states = true;
    lim.sparse_admission = true;
    lim.max_states = prm.max_states;
    const DpResult d = exact_dp(sub, lim, remaining_total);
    st.transitions += d.transitions;
    if (d.outcome != DpOutcome::Solved) {
      st.dp_unsolved++;
      continue;
    }
    const uint64_t old_cost = m.c * A_pins.size() + m.s * A_singles.size();
    if (d.sel.cost >= old_cost) continue;
    Selection next;
    for (uint32_t p : cur.pins) {
      if (!a_pin[p]) next.pins.push_back(p);
    }
    for (uint32_t p : d.sel.pins) next.pins.push_back(sub_pin[p]);
    for (uint32_t u : cur.singles) {
      if (!a_single[u]) next.singles.push_back(u);
    }
    for (uint32_t u : d.sel.singles) next.singles.push_back(Rs[u]);
    std::sort(next.pins.begin(), next.pins.end());
    std::sort(next.singles.begin(), next.singles.end());
    next.cost = selection_cost(m, next);
    if (next.cost < cur.cost && is_cover(m, next)) {
      st.accepted++;
      st.saved += cur.cost - next.cost;
      cur = std::move(next);
    }
  }
  return cur;
}

}  // namespace cape
