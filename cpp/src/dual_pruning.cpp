#include "cape/dual_pruning.hpp"

#include <algorithm>

#include "cape/dual_bound.hpp"
#include "cape/exact_dp.hpp"

namespace cape {

uint64_t scaled_dual_bound(uint64_t dual_sum_q, uint64_t c_r, uint64_t c_full, uint64_t q) {
  if (c_full == 0 || q == 0) return 0;
  const unsigned __int128 num = static_cast<unsigned __int128>(dual_sum_q) * c_r;
  const unsigned __int128 den = static_cast<unsigned __int128>(q) * c_full;
  return static_cast<uint64_t>((num + den - 1) / den);
}

FixResult reduced_cost_solve(const LocalModel& m, uint64_t ub, uint64_t q, int max_residual_cc,
                             uint64_t per_component_transitions, uint64_t max_states, uint64_t& remaining_total) {
  FixResult res;
  const uint32_t n = m.n, M = m.M();
  if (ub == 0) {
    res.outcome = FixOutcome::Proven;
    return res;
  }
  const DualResult dr = dual_ascent(m, q);
  if (!dual_feasible(m, dr, q)) return res;  // never expected; stays Unresolved
  uint64_t lbq = 0;
  for (uint64_t a : dr.a) lbq += a;
  const uint64_t T = q * (ub - 1);  // q * (largest strictly better cost)
  if (lbq > T) {
    res.outcome = FixOutcome::Proven;
    return res;
  }
  std::vector<uint64_t> pin_slack(M), single_slack(n);
  for (uint32_t p = 0; p < M; p++) {
    uint64_t s = 0;
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) s += dr.a[m.elem[k]];
    pin_slack[p] = q * m.c - s;
  }
  for (uint32_t u = 0; u < n; u++) single_slack[u] = q * m.s - dr.a[u];
  enum : uint8_t { kFree = 0, kOut = 1, kIn = 2 };
  std::vector<uint8_t> ps(M, kFree), ss(n, kFree), covered(n, 0);
  uint64_t forced_slack = 0, forced_cost = 0;
  bool changed = true;
  for (int round = 0; changed && round < 64; round++) {
    changed = false;
    for (uint32_t p = 0; p < M; p++) {
      if (ps[p] != kFree) continue;
      bool useful = false;
      for (uint64_t k = m.off[p]; k < m.off[p + 1] && !useful; k++) useful = !covered[m.elem[k]];
      // a pin covering only already-covered CCs is never in an irredundant cover
      if (!useful || lbq + forced_slack + pin_slack[p] > T) {
        ps[p] = kOut;
        res.fixed_out++;
        changed = true;
      }
    }
    for (uint32_t u = 0; u < n; u++) {
      if (ss[u] != kFree) continue;
      if (covered[u] || lbq + forced_slack + single_slack[u] > T) {
        ss[u] = kOut;
        res.fixed_out++;
        changed = true;
      }
    }
    for (uint32_t u = 0; u < n; u++) {
      if (covered[u]) continue;
      uint32_t options = (ss[u] == kFree) ? 1u : 0u;
      uint32_t last_pin = 0;
      for (uint64_t k = m.inc_off[u]; k < m.inc_off[u + 1]; k++) {
        if (ps[m.inc[k]] == kFree) {
          options++;
          last_pin = m.inc[k];
        }
      }
      if (options == 0) {  // no strictly better cover exists
        res.outcome = FixOutcome::Proven;
        return res;
      }
      if (options == 1) {
        if (ss[u] == kFree) {
          ss[u] = kIn;
          forced_slack += single_slack[u];
          forced_cost += m.s;
          covered[u] = 1;
        } else {
          ps[last_pin] = kIn;
          forced_slack += pin_slack[last_pin];
          forced_cost += m.c;
          for (uint64_t k = m.off[last_pin]; k < m.off[last_pin + 1]; k++) covered[m.elem[k]] = 1;
        }
        res.forced_in++;
        changed = true;
        if (lbq + forced_slack > T) {
          res.outcome = FixOutcome::Proven;
          return res;
        }
      }
    }
  }
  if (changed) return res;  // propagation round cap reached: Unresolved
  std::vector<uint32_t> resid;  // residual CCs (ascending local ids)
  for (uint32_t u = 0; u < n; u++) {
    if (!covered[u]) resid.push_back(u);
  }
  res.residual_n = resid.size();
  Selection base;
  for (uint32_t p = 0; p < M; p++) {
    if (ps[p] == kIn) base.pins.push_back(p);
  }
  for (uint32_t u = 0; u < n; u++) {
    if (ss[u] == kIn) base.singles.push_back(u);
  }
  if (resid.empty()) {
    if (forced_cost < ub) {
      base.cost = forced_cost;
      res.sel = base;
      res.outcome = FixOutcome::Improved;
    } else {
      res.outcome = FixOutcome::Proven;
    }
    return res;
  }
  if (static_cast<int>(resid.size()) > max_residual_cc || resid.size() > 30) return res;  // Unresolved
  // residual model: free pins restricted to the residual CCs
  std::vector<uint32_t> loc(n, 0xFFFFFFFFu);
  for (uint32_t i = 0; i < resid.size(); i++) loc[resid[i]] = i;
  LocalModel r;
  r.n = static_cast<uint32_t>(resid.size());
  r.c = m.c;
  r.s = m.s;
  r.global_cc = resid;
  r.off.push_back(0);
  std::vector<uint32_t> pin_of;  // residual pin -> component pin
  for (uint32_t p = 0; p < M; p++) {
    if (ps[p] != kFree) continue;
    const size_t before = r.elem.size();
    for (uint64_t k = m.off[p]; k < m.off[p + 1]; k++) {
      const uint32_t u = m.elem[k];
      if (!covered[u]) r.elem.push_back(loc[u]);
    }
    if (r.elem.size() == before) continue;
    pin_of.push_back(p);
    r.cand.push_back(m.cand.empty() ? p : m.cand[p]);
    r.tie_start.push_back(m.tie_start[p]);
    r.tie_depth.push_back(m.tie_depth[p]);
    r.off.push_back(r.elem.size());
  }
  r.no_single.assign(r.n, 0);
  for (uint32_t i = 0; i < r.n; i++) r.no_single[i] = ss[resid[i]] == kFree ? 0 : 1;
  finalize_incidence(r);
  DpLimits lim;
  lim.max_cc = 30;
  lim.per_component = per_component_transitions;
  lim.sparse_states = true;
  lim.sparse_admission = true;
  lim.max_states = max_states;
  const DpResult d = exact_dp(r, lim, remaining_total);
  res.transitions = d.transitions;
  if (d.outcome == DpOutcome::Infeasible) {
    res.outcome = FixOutcome::Proven;
    return res;
  }
  if (d.outcome != DpOutcome::Solved) return res;  // Unresolved (budget)
  const uint64_t total = forced_cost + d.sel.cost;
  if (total >= ub) {
    res.outcome = FixOutcome::Proven;
    return res;
  }
  Selection out = base;
  for (uint32_t p : d.sel.pins) out.pins.push_back(pin_of[p]);
  for (uint32_t u : d.sel.singles) out.singles.push_back(resid[u]);
  std::sort(out.pins.begin(), out.pins.end());
  std::sort(out.singles.begin(), out.singles.end());
  out.cost = selection_cost(m, out);
  if (out.cost != total || !is_cover(m, out)) return res;  // defensive: never accept an inconsistent cover
  res.sel = std::move(out);
  res.outcome = FixOutcome::Improved;
  return res;
}

}  // namespace cape
