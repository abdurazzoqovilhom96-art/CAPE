#include "cape/encoder.hpp"

#include <algorithm>
#include <bit>
#include <chrono>
#include <limits>
#include <numeric>

#include "cape/byte_model.hpp"
#include "cape/candidate_store.hpp"
#include "cape/candidates.hpp"
#include "cape/component_repair.hpp"
#include "cape/components.hpp"
#include "cape/cover_incidence.hpp"
#include "cape/dual_bound.hpp"
#include "cape/dual_pruning.hpp"
#include "cape/exact_dp.hpp"
#include "cape/greedy.hpp"
#include "cape/incidence.hpp"
#include "cape/local_search.hpp"
#include "cape/reductions.hpp"
#include "cape/runs.hpp"
#include "cape/serializer.hpp"
#include "cape/upstream_bridge.hpp"

namespace cape {

namespace {

using Clock = std::chrono::steady_clock;

int64_t ns_since(Clock::time_point t0) {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - t0).count();
}

template <typename LABEL>
LabelMap build_label_map(const LABEL* labels, const bridge::Labeling& lab) {
  LabelMap lm;
  const uint64_t N = lab.N;
  std::vector<uint64_t> val(N, 0);
  std::vector<uint8_t> seen(N, 0);
  const uint64_t V = lab.d.V();
  for (uint64_t i = 0; i < V; i++) {
    const uint32_t u = lab.cc[i];
    if (!seen[u]) {
      seen[u] = 1;
      val[u] = static_cast<uint64_t>(labels[i]);
    }
  }
  lm.values = val;
  std::sort(lm.values.begin(), lm.values.end());
  lm.values.erase(std::unique(lm.values.begin(), lm.values.end()), lm.values.end());
  lm.cc_label.resize(N);
  for (uint64_t u = 0; u < N; u++) {
    lm.cc_label[u] = static_cast<uint32_t>(std::lower_bound(lm.values.begin(), lm.values.end(), val[u]) - lm.values.begin());
  }
  return lm;
}

LabelMap build_label_map_from_values(std::vector<uint64_t>&& val) {
  LabelMap lm;
  lm.values = val;
  std::sort(lm.values.begin(), lm.values.end());
  lm.values.erase(std::unique(lm.values.begin(), lm.values.end()), lm.values.end());
  lm.cc_label.resize(val.size());
  for (uint64_t u = 0; u < val.size(); u++) {
    lm.cc_label[u] = static_cast<uint32_t>(std::lower_bound(lm.values.begin(), lm.values.end(), val[u]) - lm.values.begin());
  }
  return lm;
}

// v3 M5a: max label and pixel pairs (equal consecutive voxels in memory order) in one pass; identical
// results to crackle::lib::max_label / pixel_pairs.
template <typename LABEL>
void fused_scan(const LABEL* a, uint64_t V, uint64_t& maxlab, uint64_t& pairs) {
  LABEL mx = a[0];
  uint64_t pp = 0;
  for (uint64_t i = 1; i < V; i++) {
    const LABEL v = a[i];
    mx = std::max(mx, v);
    pp += (v == a[i - 1]) ? 1u : 0u;
  }
  maxlab = static_cast<uint64_t>(mx);
  pairs = pp;
}

struct ComponentState {
  uint32_t label = 0;
  uint32_t n = 0;
  uint64_t ub = 0;
  uint64_t lb = 0;
  SolveStatus status = SolveStatus::Trivial;
  Selection sel;  // local ids
};

struct RegimeOutcome {
  bool evaluated = false;
  std::string skip_reason;
  int regime_w_D = 1;
  uint64_t h = 0;
  Widths w;  // compacted widths actually written
  uint64_t section_bytes = 0;
  uint64_t lb_section_bytes = 0;  // valid for every background and every count width
  uint64_t bg_label = 0;          // dense index
  std::vector<LabelRecords> records;
  uint64_t P = 0, Q = 0;
  Diagnostics diag;
  std::vector<ExportedComponent> exported;
  std::vector<uint64_t> dual_sum_q;  // v3 M3a: per label, sum of the pass-1 dual (q-scaled); regime_gate only
};

struct Budgets {
  uint64_t dp_remaining = 0;
  uint64_t local_remaining = 0;
  uint64_t rc_remaining = 0;      // v3 M3b
  uint64_t repair_remaining = 0;  // v3 M4
};

RegimeOutcome solve_regime(const bridge::Labeling& lab, const uint32_t* colmajor, const LabelMap& lm,
                           const std::vector<Run>& runs, const Dims& d, const Widths& base, int w_D, const Options& opt,
                           Budgets& budgets, bool lb_only = false) {
  RegimeOutcome out;
  out.regime_w_D = w_D;
  const uint64_t Z = d.Z;
  const uint64_t cap_h = w_D >= 4 ? std::numeric_limits<uint64_t>::max() : (uint64_t{1} << (8 * w_D));
  out.h = std::min<uint64_t>(Z, cap_h);
  const uint64_t N = lab.N;
  const uint32_t K = static_cast<uint32_t>(lm.values.size());
  Diagnostics& dg = out.diag;

  auto t0 = Clock::now();
  const CandidateForecast fc = forecast_candidates(runs, out.h, opt.candidate_policy);
  check_memory(forecast_solver_bytes(d.V(), N, runs.size(), fc.candidates, fc.incidences), opt.memory_cap_bytes,
               "candidate/incidence working set");
  const uint64_t c = static_cast<uint64_t>(base.w_I + w_D);
  const uint64_t s = static_cast<uint64_t>(base.w_C);
  const int impl = opt.impl();
  // v3 M1a: exact neighbour-column duplicate filter while generating (equal-coverage reduction on)
  const bool adj_dedup = (impl & kImplAdjDedup) && opt.reduce_equal;
  CandidateGenStats gen;
  std::vector<Candidate> cands =
      adj_dedup ? make_candidates_dedup(runs, out.h, opt.candidate_policy, d.X, d.XY(), opt.reduce_singleton, c, s, gen)
                : make_candidates(runs, out.h, opt.candidate_policy);
  const ChainAccess ch{colmajor ? nullptr : lab.cc.data(), d.XY(), &runs, colmajor, d.Z};
  dg.i("candidate_ns", ns_since(t0));
  dg.i("candidate_count_before", static_cast<int64_t>(adj_dedup ? gen.total : cands.size()));
  dg.i("incidence_count_before", static_cast<int64_t>(fc.incidences));
  if (adj_dedup) {
    dg.i("candidates_after_adjacency", static_cast<int64_t>(cands.size()));
    dg.i("candidates_adjacent_dropped", static_cast<int64_t>(gen.adjacent_dropped));
  }

  t0 = Clock::now();
  ReductionConfig rc;
  rc.singleton = opt.reduce_singleton;
  rc.equal = opt.reduce_equal;
  rc.subset = opt.reduce_subset;
  rc.pin_cost = c;
  rc.single_cost = s;
  rc.subset_check_budget = opt.subset_checks_total;
  rc.hash_grouping = (opt.impl() & kImplTable) != 0;
  rc.fast_hash = (opt.impl() & kImplHashFn) != 0;
  rc.hash_mask = opt.debug_hash_bits >= 64 ? ~uint64_t{0} : ((uint64_t{1} << std::max(0, opt.debug_hash_bits)) - 1);
  ReductionStats rs;
  const std::vector<uint32_t> alive = reduce(cands, ch, N, rc, rs, nullptr);
  dg.i("reduction_ns", ns_since(t0));
  dg.i("candidates_after_singleton", static_cast<int64_t>(adj_dedup ? gen.after_singleton : rs.after_singleton));
  dg.i("candidates_after_equal", static_cast<int64_t>(rs.after_equal));
  dg.i("candidate_count_after", static_cast<int64_t>(rs.after_subset));
  dg.i("equal_hash_collisions", static_cast<int64_t>(rs.equal_hash_collisions));
  dg.i("subset_checks", static_cast<int64_t>(rs.subset_checks));
  dg.i("subset_truncated", rs.subset_truncated ? 1 : 0);
  dg.i("reduction_singleton_ns", static_cast<int64_t>(rs.singleton_ns));
  dg.i("reduction_equal_hash_ns", static_cast<int64_t>(rs.equal_hash_ns));
  dg.i("reduction_equal_sort_ns", static_cast<int64_t>(rs.equal_sort_ns));
  dg.i("reduction_subset_incidence_ns", static_cast<int64_t>(rs.subset_incidence_ns));
  dg.i("reduction_subset_scan_ns", static_cast<int64_t>(rs.subset_scan_ns));
  uint64_t E_after = 0;
  for (uint32_t p : alive) E_after += cands[p].len;
  dg.i("incidence_count", static_cast<int64_t>(E_after));

  t0 = Clock::now();
  const Components comps = find_components(alive, cands, ch, N);
  dg.i("component_ns", ns_since(t0));
  dg.i("component_count", comps.count);

  // ---- v3 M1b: component-ordered CSR (one sequential chain pass) ------------------------------
  std::vector<uint32_t> scratch(N, 0);
  const bool use_csr = (impl & kImplCsr) != 0;
  const bool eager = (impl & kImplEagerGreedy) != 0;
  ComponentCsr csr;
  LocalModel mbuf;
  std::vector<uint64_t> posbuf;
  GreedyScratch gsc;
  if (use_csr) {
    t0 = Clock::now();
    csr = build_component_csr(comps, alive, cands, ch, scratch);
    dg.i("csr_ns", ns_since(t0));
  }

  // ---- pass 1: greedy UB + dual LB for every component -------------------------------------
  t0 = Clock::now();
  std::vector<ComponentState> cs(comps.count);
  bool dual_ok = true;
  uint64_t greedy_ns = 0, dual_ns = 0;
  const bool want_dual_sums = opt.regime_gate || opt.certificate != CertificateMode::Off;
  if (want_dual_sums) out.dual_sum_q.assign(K, 0);
  auto pass1_component = [&](ComponentState& st, const LocalModel& m) {
    auto tg = Clock::now();
    st.sel = eager ? greedy_eager(m, gsc) : greedy(m);
    greedy_ns += ns_since(tg);
    auto td = Clock::now();
    const DualResult dr = dual_ascent(m, opt.dual_scale);
    dual_ns += ns_since(td);
    dual_ok = dual_ok && dual_feasible(m, dr, opt.dual_scale);
    st.ub = st.sel.cost;
    st.lb = dr.lb;
    st.status = st.ub == st.lb ? SolveStatus::LbTight : SolveStatus::Heuristic;
    if (want_dual_sums) {
      uint64_t sum = 0;
      for (uint64_t a : dr.a) sum += a;
      out.dual_sum_q[st.label] += sum;
    }
  };
  for (uint32_t k = 0; k < comps.count; k++) {
    ComponentState& st = cs[k];
    st.label = lm.cc_label[comps.ccs[comps.cc_off[k]]];
    st.n = static_cast<uint32_t>(comps.cc_off[k + 1] - comps.cc_off[k]);
    if (comps.cand_off[k + 1] == comps.cand_off[k]) {  // no pins: singletons are optimal
      st.sel.singles.resize(st.n);
      std::iota(st.sel.singles.begin(), st.sel.singles.end(), 0u);
      st.ub = st.lb = s * st.n;
      st.sel.cost = st.ub;
      st.status = SolveStatus::Trivial;
      if (want_dual_sums) out.dual_sum_q[st.label] += opt.dual_scale * s * st.n;  // a_u = q s is feasible
      continue;
    }
    if (use_csr) {
      build_local_model_csr(mbuf, comps, csr, k, c, s, posbuf);
      pass1_component(st, mbuf);
    } else {
      const LocalModel m = build_local_model(comps, k, alive, cands, ch, scratch, c, s);
      pass1_component(st, m);
    }
  }
  dg.i("greedy_ns", static_cast<int64_t>(greedy_ns));
  dg.i("dual_ns", static_cast<int64_t>(dual_ns));
  dg.i("pass1_ns", ns_since(t0));

  if (lb_only) {  // v2 CERTIFIED: dual-only bound of a regime the stream search did not use
    std::vector<uint64_t> Lr(K, 0);
    for (const auto& st : cs) Lr[st.label] += st.lb;
    uint64_t sumL = 0, maxL = 0;
    for (uint32_t l = 0; l < K; l++) {
      sumL += Lr[l];
      maxL = std::max(maxL, Lr[l]);
    }
    Widths wl = base;
    wl.w_N = 1;
    out.lb_section_bytes =
        fixed_section_bytes(wl, d.Z) + (K ? (K - 1) : 0) * per_label_overhead(wl) + (sumL - maxL);
    out.evaluated = true;
    dg.i("certificate_dual_feasible", dual_ok ? 1 : 0);
    return out;
  }

  // ---- background (formula (8)) -------------------------------------------------------------
  std::vector<uint64_t> U(K, 0), L(K, 0), records(K, 0), depth_sum(K, 0);
  for (const auto& st : cs) {
    U[st.label] += st.ub;
    L[st.label] += st.lb;
    records[st.label] += st.sel.pins.size() + st.sel.singles.size();
  }
  uint32_t bg = 0;
  if (opt.background_policy == BackgroundPolicy::MinCost) {
    for (uint32_t l = 1; l < K; l++) {
      if (U[l] > U[bg] || (U[l] == U[bg] && L[l] > L[bg])) bg = l;
    }
  } else {  // upstream-rule analogue: most records, then larger total pin depth
    for (uint32_t k = 0; k < comps.count; k++) {
      for (uint32_t p : cs[k].sel.pins) {
        const uint32_t gi = alive[comps.cands[comps.cand_off[k] + p]];
        depth_sum[cs[k].label] += cands[gi].len - 1;
      }
    }
    for (uint32_t l = 1; l < K; l++) {
      if (records[l] > records[bg] || (records[l] == records[bg] && depth_sum[l] > depth_sum[bg])) bg = l;
    }
  }
  out.bg_label = bg;

  // ---- pass 2: exact / local refinement of written labels -----------------------------------
  t0 = Clock::now();
  std::vector<uint32_t> order;
  for (uint32_t k = 0; k < comps.count; k++) {
    if (cs[k].label == bg) continue;
    if (cs[k].status == SolveStatus::Trivial) continue;
    if (cs[k].status == SolveStatus::LbTight && opt.use_dual_gate) continue;
    order.push_back(k);
  }
  std::stable_sort(order.begin(), order.end(), [&](uint32_t a, uint32_t b) {
    return (cs[a].ub - cs[a].lb) > (cs[b].ub - cs[b].lb);
  });
  DpLimits lim;
  lim.max_cc = opt.exact_max_cc;
  lim.per_component = opt.exact_max_transitions_per_component;
  lim.memory_bytes = opt.exact_memory_bytes;
  lim.sparse_states = (opt.impl() & kImplSparseDp) != 0;
  uint64_t dp_solved = 0, dp_skipped = 0, dp_exhausted = 0, dp_trans = 0, local_checks = 0, local_impr = 0;
  uint64_t dp_ns = 0, local_ns = 0;
  // v3 M3b / M4 counters
  uint64_t rc_tried = 0, rc_proven = 0, rc_improved = 0, rc_fixed = 0, rc_forced = 0, rc_trans = 0, rc_ns = 0;
  uint64_t rc_saved = 0;
  RepairStats rst;
  uint64_t repair_components = 0, repair_ns = 0;
  RepairParams rprm;
  rprm.max_r = static_cast<uint32_t>(std::clamp(opt.repair_max_r, 1, 30));
  rprm.max_pool = static_cast<uint32_t>(std::max(1, opt.repair_max_pool));
  rprm.attempts = static_cast<uint32_t>(std::max(0, opt.repair_attempts));
  rprm.per_attempt_transitions = opt.repair_transitions_per_attempt;
  rprm.max_states = opt.repair_max_states;
  rprm.q = opt.dual_scale;
  std::vector<std::pair<uint32_t, ComponentState>> repair_backup;
  auto pass2_component = [&](uint32_t k, const LocalModel& m) {
    ComponentState& st = cs[k];
    bool solved = false;
    if (opt.use_exact) {
      auto tdp = Clock::now();
      DpResult r = exact_dp(m, lim, budgets.dp_remaining);
      dp_ns += ns_since(tdp);
      dp_trans += r.transitions;
      if (r.outcome == DpOutcome::Solved) {
        dp_solved++;
        if (!is_cover(m, r.sel) || r.sel.cost > st.ub) throw CapeError("internal: exact DP returned an invalid cover");
        st.sel = r.sel;
        st.ub = r.sel.cost;
        st.lb = r.sel.cost;  // exact optimum of this component model
        st.status = SolveStatus::ExactDp;
        solved = true;
      } else if (r.outcome == DpOutcome::BudgetExhausted) {
        dp_exhausted++;
      } else {
        dp_skipped++;
      }
    }
    if (!solved && opt.rc_fixing && st.ub > st.lb && budgets.rc_remaining > 0) {
      auto trc = Clock::now();
      rc_tried++;
      const FixResult fr = reduced_cost_solve(m, st.ub, opt.dual_scale, opt.rc_max_cc, opt.rc_transitions_per_component,
                                              opt.rc_max_states, budgets.rc_remaining);
      rc_ns += ns_since(trc);
      rc_fixed += fr.fixed_out;
      rc_forced += fr.forced_in;
      rc_trans += fr.transitions;
      if (fr.outcome == FixOutcome::Proven) {
        rc_proven++;
        st.lb = st.ub;  // no strictly cheaper cover of this component model exists
        st.status = SolveStatus::ExactDp;
        solved = true;
      } else if (fr.outcome == FixOutcome::Improved) {
        if (!is_cover(m, fr.sel) || fr.sel.cost >= st.ub) throw CapeError("internal: reduced-cost solve returned an invalid cover");
        rc_improved++;
        rc_saved += st.ub - fr.sel.cost;
        st.sel = fr.sel;
        st.ub = st.lb = fr.sel.cost;  // optimum of the component model
        st.status = SolveStatus::ExactDp;
        solved = true;
      }
    }
    if (!solved && opt.use_local && budgets.local_remaining > 0) {
      auto tl = Clock::now();
      LocalStats ls;
      Selection improved = local_search(m, st.sel, opt.local_checks_per_component, budgets.local_remaining, ls);
      local_ns += ns_since(tl);
      local_checks += ls.checks;
      local_impr += ls.improvements;
      if (improved.cost < st.ub) {
        if (!is_cover(m, improved)) throw CapeError("internal: local search produced an invalid cover");
        st.sel = improved;
        st.ub = improved.cost;
        st.status = st.ub == st.lb ? SolveStatus::LbTight : SolveStatus::Heuristic;
      }
    }
    if (opt.repair && st.status == SolveStatus::Heuristic && st.ub > st.lb && budgets.repair_remaining > 0) {
      auto tr = Clock::now();
      repair_components++;
      const ComponentState before = st;
      Selection rep = component_repair(m, st.sel, rprm, budgets.repair_remaining, rst);
      repair_ns += ns_since(tr);
      if (rep.cost < st.ub) {
        if (!is_cover(m, rep)) throw CapeError("internal: component repair produced an invalid cover");
        repair_backup.emplace_back(k, before);
        st.sel = std::move(rep);
        st.ub = st.sel.cost;
        st.status = st.ub == st.lb ? SolveStatus::LbTight : SolveStatus::Heuristic;
      }
    }
  };
  for (uint32_t k : order) {
    if (use_csr) {
      build_local_model_csr(mbuf, comps, csr, k, c, s, posbuf);
      pass2_component(k, mbuf);
    } else {
      const LocalModel m = build_local_model(comps, k, alive, cands, ch, scratch, c, s);
      pass2_component(k, m);
    }
  }
  if (opt.rc_fixing) {
    dg.i("rc_components_tried", static_cast<int64_t>(rc_tried));
    dg.i("rc_components_proven", static_cast<int64_t>(rc_proven));
    dg.i("rc_components_improved", static_cast<int64_t>(rc_improved));
    dg.i("rc_items_fixed_out", static_cast<int64_t>(rc_fixed));
    dg.i("rc_items_forced_in", static_cast<int64_t>(rc_forced));
    dg.i("rc_transitions", static_cast<int64_t>(rc_trans));
    dg.i("rc_model_bytes_saved", static_cast<int64_t>(rc_saved));
    dg.i("rc_ns", static_cast<int64_t>(rc_ns));
  }
  if (opt.repair) {
    // M4 is kept only if the whole labels section gets strictly smaller (count / depth widths included)
    auto section_of = [&](const std::vector<ComponentState>& states) -> uint64_t {
      std::vector<uint64_t> pins(K, 0), singles(K, 0);
      uint64_t P = 0, Q = 0, maxdepth = 0;
      for (uint32_t k = 0; k < comps.count; k++) {
        const ComponentState& x = states[k];
        if (x.label == bg) continue;
        pins[x.label] += x.sel.pins.size();
        singles[x.label] += x.sel.singles.size();
        P += x.sel.pins.size();
        Q += x.sel.singles.size();
        for (uint32_t p : x.sel.pins) {
          maxdepth = std::max<uint64_t>(maxdepth, cands[alive[comps.cands[comps.cand_off[k] + p]]].len - 1);
        }
      }
      uint64_t maxcount = 0;
      for (uint32_t l = 0; l < K; l++) {
        if (l != bg) maxcount = std::max(maxcount, std::max(pins[l], singles[l]));
      }
      Widths w = base;
      w.w_D = byte_width(maxdepth);
      w.w_N = byte_width(maxcount);
      return predict_label_bytes(w, K ? K - 1 : 0, d.Z, P, Q);
    };
    int64_t delta = 0;
    bool kept = false;
    if (!repair_backup.empty()) {
      const uint64_t with = section_of(cs);
      std::vector<ComponentState> alt = cs;
      for (auto& [k, before] : repair_backup) alt[k] = before;
      const uint64_t without = section_of(alt);
      delta = static_cast<int64_t>(without) - static_cast<int64_t>(with);
      if (with < without) {
        kept = true;
      } else {
        cs.swap(alt);
      }
    }
    dg.i("repair_components", static_cast<int64_t>(repair_components));
    dg.i("repair_attempts", static_cast<int64_t>(rst.attempts));
    dg.i("repair_accepted", static_cast<int64_t>(rst.accepted));
    dg.i("repair_model_bytes_saved", static_cast<int64_t>(rst.saved));
    dg.i("repair_dp_unsolved", static_cast<int64_t>(rst.dp_unsolved));
    dg.i("repair_transitions", static_cast<int64_t>(rst.transitions));
    dg.i("repair_section_delta", delta);
    dg.i("repair_kept", kept ? 1 : 0);
    dg.i("repair_ns", static_cast<int64_t>(repair_ns));
  }
  dg.i("dp_ns", static_cast<int64_t>(dp_ns));
  dg.i("local_ns", static_cast<int64_t>(local_ns));
  dg.i("pass2_ns", ns_since(t0));
  dg.i("dp_components_solved", static_cast<int64_t>(dp_solved));
  dg.i("dp_components_skipped", static_cast<int64_t>(dp_skipped));
  dg.i("dp_components_budget_exhausted", static_cast<int64_t>(dp_exhausted));
  dg.i("dp_transitions", static_cast<int64_t>(dp_trans));
  dg.i("local_checks", static_cast<int64_t>(local_checks));
  dg.i("local_improvements", static_cast<int64_t>(local_impr));

  // ---- records, compaction, bounds ----------------------------------------------------------
  std::fill(U.begin(), U.end(), 0);
  std::fill(L.begin(), L.end(), 0);
  std::vector<LabelRecords> recs(K);
  for (uint32_t l = 0; l < K; l++) recs[l].label_value = lm.values[l];
  uint64_t n_exact_cc = 0, n_cc_written = 0, exact_cost = 0, written_cost = 0, max_comp = 0;
  std::vector<int64_t> status_count(4, 0);
  std::vector<int64_t> size_hist_count(33, 0), size_hist_cc(33, 0);
  for (uint32_t k = 0; k < comps.count; k++) {
    const ComponentState& st = cs[k];
    U[st.label] += st.ub;
    L[st.label] += st.lb;
    max_comp = std::max<uint64_t>(max_comp, st.n);
    const int bucket = std::bit_width(static_cast<uint32_t>(st.n)) - 1;
    size_hist_count[bucket]++;
    size_hist_cc[bucket] += st.n;
    status_count[static_cast<int>(st.status)]++;
    if (st.label == bg) continue;
    n_cc_written += st.n;
    written_cost += st.ub;
    if (st.status != SolveStatus::Heuristic) {
      n_exact_cc += st.n;
      exact_cost += st.ub;
    }
    LabelRecords& lr = recs[st.label];
    const uint64_t base_off = comps.cand_off[k];
    for (uint32_t p : st.sel.pins) {
      const Candidate& cd = cands[alive[comps.cands[base_off + p]]];
      lr.pins.push_back(PinRecord{ch.start_index(cd), static_cast<uint64_t>(cd.len - 1)});
    }
    const uint64_t cc_base = comps.cc_off[k];
    for (uint32_t u : st.sel.singles) lr.singletons.push_back(comps.ccs[cc_base + u]);
  }
  std::vector<LabelRecords> written;
  written.reserve(K ? K - 1 : 0);
  for (uint32_t l = 0; l < K; l++) {
    if (l == bg) continue;
    out.P += recs[l].pins.size();
    out.Q += recs[l].singletons.size();
    written.push_back(std::move(recs[l]));
  }
  Widths w = base;
  w.w_D = required_depth_width(written);
  w.w_N = required_count_width(written);
  if (w.w_D > w_D) throw CapeError("internal: chosen pin depth exceeds the regime width");
  const uint64_t num_grids = d.Z;  // default grid size: one grid per slice
  out.w = w;
  out.section_bytes = predict_label_bytes(w, written.size(), num_grids, out.P, out.Q);
  // LB valid for every background (8) and every count width (w_N >= 1)
  uint64_t sumL = 0, maxL = 0;
  for (uint32_t l = 0; l < K; l++) {
    sumL += L[l];
    maxL = std::max(maxL, L[l]);
  }
  Widths wl = base;
  wl.w_N = 1;
  out.lb_section_bytes = fixed_section_bytes(wl, num_grids) + (K ? (K - 1) : 0) * per_label_overhead(wl) + (sumL - maxL);
  out.records = std::move(written);
  out.evaluated = true;

  if (opt.export_components_max_cc > 0) {
    for (uint32_t k = 0; k < comps.count && out.exported.size() < opt.export_components_limit; k++) {
      const ComponentState& st = cs[k];
      if (st.label == bg || st.status == SolveStatus::Trivial) continue;
      if (st.n > static_cast<uint32_t>(opt.export_components_max_cc)) continue;
      const LocalModel m = build_local_model(comps, k, alive, cands, ch, scratch, c, s);
      ExportedComponent e;
      e.label_index = st.label;
      e.n = m.n;
      e.pin_cost = c;
      e.single_cost = s;
      e.ub = st.ub;
      e.lb = st.lb;
      e.status = static_cast<int>(st.status);
      for (uint32_t p = 0; p < m.M(); p++) e.sets.emplace_back(m.elem.begin() + m.off[p], m.elem.begin() + m.off[p + 1]);
      out.exported.push_back(std::move(e));
    }
  }

  dg.i("max_component_cc", static_cast<int64_t>(max_comp));
  dg.i("cc_written", static_cast<int64_t>(n_cc_written));
  dg.i("cc_exact", static_cast<int64_t>(n_exact_cc));
  dg.r("exact_cc_fraction", n_cc_written ? static_cast<double>(n_exact_cc) / static_cast<double>(n_cc_written) : 1.0);
  dg.r("exact_cost_fraction", written_cost ? static_cast<double>(exact_cost) / static_cast<double>(written_cost) : 1.0);
  dg.a("component_status_counts", status_count);  // Trivial, LbTight, ExactDp, Heuristic
  dg.a("component_size_hist_count", size_hist_count);  // bucket b: sizes in [2^b, 2^(b+1))
  dg.a("component_size_hist_cc", size_hist_cc);
  dg.i("payload_ub_bytes", static_cast<int64_t>(written_cost));
  dg.i("payload_lb_bytes_fixed_background", static_cast<int64_t>(sumL - L[bg]));
  dg.i("certificate_dual_feasible", dual_ok ? 1 : 0);
  return out;
}

}  // namespace

template <typename LABEL>
EncodeResult encode(const LABEL* labels, const Dims& d, const Options& opt) {
  EncodeResult res;
  Diagnostics& dg = res.diag;
  const auto t_all = Clock::now();
  const uint64_t V = d.V();
  if (V >= (uint64_t{1} << 32)) {
    throw UnsupportedInput("volume has >= 2^32 voxels: upstream pin index width wraps (format_audit F4)");
  }
  dg.i("voxels", static_cast<int64_t>(V));
  if (V == 0) {
    res.bytes = bridge::stock_compress(labels, d, false, 0, false, 1);
    dg.t("label_format", "FLAT");
    return res;
  }
  auto t0 = Clock::now();
  const int impl = opt.impl();
  uint64_t maxlab = 0, pairs = 0;
  if (impl & kImplFusedScan) {  // v3 M5a
    fused_scan(labels, V, maxlab, pairs);
  } else {
    maxlab = bridge::max_label(labels, V);
    pairs = bridge::pixel_pairs(labels, V);
  }
  const int stored_width = byte_width(maxlab);
  const bool impermissible = pairs >= V / 2;
  const bool pins_possible = d.Z > 1;
  const bool stock_pins = pins_possible && pairs >= V / 2;
  bool try_pins = false, try_flat = false;
  switch (opt.format_policy) {
    case FormatPolicy::SameAsStock:
      try_pins = stock_pins;
      try_flat = !stock_pins;
      break;
    case FormatPolicy::ForcePins:
      try_pins = pins_possible;
      try_flat = !pins_possible;
      break;
    case FormatPolicy::MinExact:
      try_pins = pins_possible;
      try_flat = true;
      break;
  }
  dg.i("pixel_pairs", static_cast<int64_t>(pairs));
  dg.i("stock_rule_pins", stock_pins ? 1 : 0);
  dg.i("scan_ns", ns_since(t0));

  t0 = Clock::now();
  const bridge::Boundary boundary = bridge::boundaries(labels, d, impermissible, opt.markov_model_order, opt.parallel);
  dg.i("boundary_ns", ns_since(t0));
  bridge::HeaderFields hf;
  hf.data_width = static_cast<int>(sizeof(LABEL));
  hf.stored_data_width = stored_width;
  hf.d = d;

  std::vector<uint8_t> flat_stream, pins_stream;
  if (try_flat) {
    t0 = Clock::now();
    std::vector<uint32_t> crcs;
    std::vector<uint8_t> section = bridge::flat_section(labels, d, stored_width, opt.parallel, crcs);
    hf.label_format = 0;
    flat_stream = bridge::assemble(hf, section, boundary, crcs);
    dg.i("flat_ns", ns_since(t0));
    dg.i("flat_total_bytes", static_cast<int64_t>(flat_stream.size()));
    dg.i("flat_label_bytes", static_cast<int64_t>(section.size()));
  }
  if (try_pins && opt.selector != Selector::Cape) {
    // stock_cover: upstream's own selection, background and serializer in the pins format
    t0 = Clock::now();
    std::vector<uint32_t> crcs;
    std::vector<uint8_t> section;
    if (opt.selector == Selector::StockGreedyCorrected) {
      bool widened = false;
      section = bridge::stock_pins_section_corrected(labels, d, true, stored_width, crcs, widened);
      dg.i("stock_count_width_widened", widened ? 1 : 0);
    } else {
      section = bridge::stock_pins_section(labels, d, opt.selector == Selector::StockGreedy, stored_width, crcs);
    }
    hf.label_format = 2;
    pins_stream = bridge::assemble(hf, section, boundary, crcs);
    dg.i("stock_selection_ns", ns_since(t0));
    dg.i("pins_total_bytes", static_cast<int64_t>(pins_stream.size()));
    dg.i("label_bytes", static_cast<int64_t>(section.size()));
    dg.t("selector", opt.selector == Selector::StockGreedy            ? "stock_greedy"
                     : opt.selector == Selector::StockGreedyCorrected ? "stock_greedy_corrected"
                                                                      : "stock_fast");
  } else if (try_pins) {
    t0 = Clock::now();
    // v3 M5b: batched CC labeling straight into the column-major chain buffer (no z-major CC volume)
    const bool batched = (impl & kImplBatchedCC) && (impl & kImplLayout) && (impl & kImplRuns) && !opt.return_cc;
    bridge::Labeling lab;
    LabelMap lm;
    std::vector<uint32_t> colmajor;
    if (batched) {
      check_memory(4 * V, opt.memory_cap_bytes, "column-major chain buffer");
      std::vector<uint64_t> cc_values;
      lab = bridge::cc_label_colmajor(labels, d, colmajor, cc_values);
      if (lab.N >= (uint64_t{1} << 32) - 1) throw UnsupportedInput("CC count does not fit uint32 (format_audit F5)");
      lm = build_label_map_from_values(std::move(cc_values));
    } else {
      lab = bridge::cc_label(labels, d);
      if (opt.return_cc) res.cc = lab.cc;
      if (lab.N >= (uint64_t{1} << 32) - 1) throw UnsupportedInput("CC count does not fit uint32 (format_audit F5)");
      lm = build_label_map(labels, lab);
    }
    dg.i("cc_ns", ns_since(t0));
    dg.i("cc_count", static_cast<int64_t>(lab.N));
    dg.i("label_count", static_cast<int64_t>(lm.values.size()));
    dg.i("batched_cc", batched ? 1 : 0);

    // v2 P1.2: column-major chain buffer. The z-major CC volume is not read again after this
    // point (crcs and per-slice counts are already in lab), so it is released: the extra memory
    // is transient (8V bytes during the transpose); the solver working set is unchanged.
    std::vector<Run> runs;
    if (batched) {
      dg.i("transpose_ns", 0);  // the transpose is part of cc_ns in the batched path
      t0 = Clock::now();
      runs = column_runs_colmajor(colmajor.data(), lm.cc_label, d);
      dg.i("runs_ns", ns_since(t0));
    } else if (impl & kImplLayout) {
      int64_t runs_before_ns = 0;
      if (!(impl & kImplRuns)) {  // v2.1 attribution: layout without one-pass runs -> v1 runs before the release
        t0 = Clock::now();
        runs = column_runs(lab.cc.data(), lm.cc_label, d);
        runs_before_ns = ns_since(t0);
      }
      t0 = Clock::now();
      check_memory(8 * V, opt.memory_cap_bytes, "column-major chain buffer (transient)");
      colmajor.resize(V);
      const uint64_t XY = d.XY(), Z = d.Z;
      constexpr uint64_t B = 16;  // one 64-byte line of uint32 per slice and block
      const uint32_t* src = lab.cc.data();
      for (uint64_t c0 = 0; c0 < XY; c0 += B) {
        const uint64_t c1 = std::min(XY, c0 + B);
        for (uint64_t z = 0; z < Z; z++) {
          const uint32_t* row = src + XY * z;
          for (uint64_t c = c0; c < c1; c++) colmajor[c * Z + z] = row[c];
        }
      }
      std::vector<uint32_t>().swap(lab.cc);
      dg.i("transpose_ns", ns_since(t0));
      if (impl & kImplRuns) {
        t0 = Clock::now();
        runs = column_runs_colmajor(colmajor.data(), lm.cc_label, d);
        dg.i("runs_ns", ns_since(t0));
      } else {
        dg.i("runs_ns", runs_before_ns);
      }
    } else {
      t0 = Clock::now();
      runs = column_runs(lab.cc.data(), lm.cc_label, d);
      dg.i("runs_ns", ns_since(t0));
    }
    dg.i("run_count", static_cast<int64_t>(runs.size()));
    {
      const int low = impl & kImplAll;  // the v2.1 attribution bits keep their v2.1 meaning
      dg.t("reduction_impl", low == kImplAll ? "fast" : (low == 0 ? "legacy" : "mixed"));
    }
    dg.i("impl_mask", impl);

    Widths base;
    base.w_L = stored_width;
    base.w_I = byte_width(V);
    base.w_G = byte_width(d.XY());
    base.w_C = byte_width(lab.N);
    // depth regimes: full width first (every run fits), then narrower windowed regimes
    std::vector<int> regimes;
    const int full = byte_width(d.Z - 1);
    regimes.push_back(full);
    if (opt.depth_policy == DepthPolicy::FullWidthFirst) {
      for (int wd : {1, 2, 4}) {
        if (wd < full) regimes.push_back(wd);
      }
    }
    Budgets budgets{opt.exact_max_transitions_total, opt.local_checks_total, opt.rc_transitions_total,
                    opt.repair_transitions_total};
    RegimeOutcome best;
    std::vector<int64_t> regime_bytes;
    std::string regime_log;
    uint64_t lb_all = std::numeric_limits<uint64_t>::max();
    bool all_regimes_covered = true;
    // v3 M3a regime gate: full-width pass-1 dual per label, scaled to a narrower regime
    std::vector<uint64_t> full_dual;
    uint64_t gate_checked = 0, gate_pruned = 0;
    int64_t gate_ns = 0;
    const uint64_t K_labels = lm.values.size();
    for (int wd : regimes) {
      if (opt.regime_gate && wd != full && best.evaluated && !full_dual.empty()) {
        const auto tg = Clock::now();
        gate_checked++;
        const uint64_t c_full = static_cast<uint64_t>(base.w_I + full), c_r = static_cast<uint64_t>(base.w_I + wd);
        uint64_t sumL = 0, maxL = 0;
        for (uint64_t l = 0; l < K_labels; l++) {
          const uint64_t Ll = scaled_dual_bound(full_dual[l], c_r, c_full, opt.dual_scale);
          sumL += Ll;
          maxL = std::max(maxL, Ll);
        }
        Widths wl = base;
        wl.w_N = 1;
        const uint64_t lb = fixed_section_bytes(wl, d.Z) + (K_labels ? (K_labels - 1) : 0) * per_label_overhead(wl) +
                            (sumL - maxL);
        gate_ns += ns_since(tg);
        if (lb >= best.section_bytes) {  // regime wd cannot be strictly smaller
          gate_pruned++;
          lb_all = std::min(lb_all, lb);
          regime_log += "wD" + std::to_string(wd) + ":pruned_lb" + std::to_string(lb) + ";";
          regime_bytes.push_back(-2);
          continue;
        }
        regime_log += "gate_lb_wD" + std::to_string(wd) + ":" + std::to_string(lb) + ";";
      }
      RegimeOutcome ro;
      try {
        ro = solve_regime(lab, colmajor.empty() ? nullptr : colmajor.data(), lm, runs, d, base, wd, opt, budgets);
      } catch (const MemoryCapExceeded& e) {
        ro.evaluated = false;
        ro.regime_w_D = wd;
        ro.skip_reason = e.what();
        all_regimes_covered = false;
      }
      regime_log += "wD" + std::to_string(wd) + (ro.evaluated ? ":" + std::to_string(ro.section_bytes) : ":" + ro.skip_reason) + ";";
      regime_bytes.push_back(ro.evaluated ? static_cast<int64_t>(ro.section_bytes) : -1);
      if (!ro.evaluated) continue;
      lb_all = std::min(lb_all, ro.lb_section_bytes);
      if ((opt.regime_gate || opt.certificate != CertificateMode::Off) && wd == full) {
        bool feasible = true;
        for (const auto& kv : ro.diag.ints) {
          if (kv.first == "certificate_dual_feasible" && kv.second != 1) feasible = false;
        }
        if (feasible) full_dual = ro.dual_sum_q;  // only a verified feasible dual is scaled
      }
      if (!best.evaluated || ro.section_bytes < best.section_bytes) best = std::move(ro);
    }
    // v3 certificate fix (found by tests/test_v3_invariants.py): with a fixed depth width the written stream
    // may compact w_D below the regime width (no chosen pin is that deep). Such a stream is a cover from the
    // full-width runs of length <= h_w priced at c_w = w_I + w, which the full-width regime LB does not bound
    // (v2.1 could report lb_bytes > ub_bytes there). The full-width dual scaled by c_w / c_full is feasible
    // for that family, so its bound is added for every narrower width. Stream bytes are unchanged.
    auto scaled_lb = [&](int w) -> uint64_t {
      const uint64_t c_full = static_cast<uint64_t>(base.w_I + full), c_r = static_cast<uint64_t>(base.w_I + w);
      uint64_t sumL = 0, maxL = 0;
      for (uint64_t l = 0; l < K_labels; l++) {
        const uint64_t Ll = scaled_dual_bound(full_dual[l], c_r, c_full, opt.dual_scale);
        sumL += Ll;
        maxL = std::max(maxL, Ll);
      }
      Widths wl = base;
      wl.w_N = 1;
      return fixed_section_bytes(wl, d.Z) + (K_labels ? (K_labels - 1) : 0) * per_label_overhead(wl) + (sumL - maxL);
    };
    bool scaled_cert_ok = true;
    if (opt.certificate == CertificateMode::Regime && opt.depth_policy == DepthPolicy::FixedDepthWidth && full > 1) {
      if (full_dual.empty()) {
        scaled_cert_ok = false;  // no verified dual: the certificate is reported as not valid
      } else {
        for (int w : {1, 2, 4}) {
          if (w >= full) continue;
          const uint64_t lbw = scaled_lb(w);
          lb_all = std::min(lb_all, lbw);
          regime_log += "cert_scaled_lb_wD" + std::to_string(w) + ":" + std::to_string(lbw) + ";";
        }
      }
    }
    if (opt.regime_gate) {
      dg.i("regime_gate_checked", static_cast<int64_t>(gate_checked));
      dg.i("regime_gate_pruned", static_cast<int64_t>(gate_pruned));
      dg.i("regime_gate_ns", gate_ns);
    }
    if (!best.evaluated) throw MemoryCapExceeded("OOM_PREVENTED: no depth regime fits the memory cap (" + regime_log + ")");
    // v2 CERTIFIED: bound the regimes a fixed-depth stream search skipped (stream unchanged)
    bool certificate_dual_ok = scaled_cert_ok;
    for (const auto& kv : best.diag.ints) {
      if (kv.first == "certificate_dual_feasible" && kv.second != 1) certificate_dual_ok = false;
    }
    if (opt.certificate == CertificateMode::AllRegimes && opt.depth_policy == DepthPolicy::FixedDepthWidth) {
      const auto tc = Clock::now();
      for (int wd : {1, 2, 4}) {
        if (wd >= full) continue;
        try {
          Budgets none{0, 0};
          RegimeOutcome lo = solve_regime(lab, colmajor.empty() ? nullptr : colmajor.data(), lm, runs, d, base, wd, opt,
                                          none, /*lb_only=*/true);
          lb_all = std::min(lb_all, lo.lb_section_bytes);
          for (const auto& kv : lo.diag.ints) {
            if (kv.first == "certificate_dual_feasible" && kv.second != 1) certificate_dual_ok = false;
          }
          regime_log += "lbwD" + std::to_string(wd) + ":" + std::to_string(lo.lb_section_bytes) + ";";
        } catch (const MemoryCapExceeded& e) {
          all_regimes_covered = false;
          regime_log += "lbwD" + std::to_string(wd) + ":" + e.what() + ";";
        }
      }
      dg.i("certificate_extra_ns", ns_since(tc));
    }
    for (const auto& kv : best.diag.ints) {
      if (kv.first == "certificate_dual_feasible") {
        if (opt.certificate != CertificateMode::Off) dg.i(kv.first, certificate_dual_ok ? 1 : 0);
        continue;
      }
      dg.ints.push_back(kv);
    }
    for (const auto& kv : best.diag.reals) dg.reals.push_back(kv);
    for (const auto& kv : best.diag.arrays) dg.arrays.push_back(kv);
    dg.t("regimes", regime_log);
    dg.a("regime_section_bytes", regime_bytes);
    dg.i("regime_w_D", best.regime_w_D);
    dg.i("regime_h", static_cast<int64_t>(best.h));

    t0 = Clock::now();
    std::vector<uint8_t> section =
        serialize_pins_section(lm.values[best.bg_label], best.records, lab.per_slice, best.w);
    if (section.size() != best.section_bytes) throw CapeError("internal: byte model and serializer disagree");
    hf.label_format = 2;
    pins_stream = bridge::assemble(hf, section, boundary, lab.cc_crcs);
    dg.i("serialize_ns", ns_since(t0));
    dg.i("pins_total_bytes", static_cast<int64_t>(pins_stream.size()));
    dg.i("label_bytes", static_cast<int64_t>(section.size()));
    const uint64_t rest = pins_stream.size() - section.size();
    if (opt.certificate != CertificateMode::Off) {
      dg.i("ub_bytes", static_cast<int64_t>(pins_stream.size()));
      dg.i("lb_bytes", static_cast<int64_t>(lb_all + rest));
      dg.i("label_lb_bytes", static_cast<int64_t>(lb_all));
    }
    dg.t("certificate_mode", opt.certificate == CertificateMode::Off      ? "off"
                             : opt.certificate == CertificateMode::Regime ? "regime"
                                                                          : "all_regimes");
    dg.i("P", static_cast<int64_t>(best.P));
    dg.i("Q", static_cast<int64_t>(best.Q));
    dg.i("w_L", best.w.w_L);
    dg.i("w_I", best.w.w_I);
    dg.i("w_G", best.w.w_G);
    dg.i("w_N", best.w.w_N);
    dg.i("w_D", best.w.w_D);
    dg.i("w_C", best.w.w_C);
    dg.u("background_label", lm.values[best.bg_label]);
    if (opt.certificate != CertificateMode::Off)
    dg.t("certificate_scope",
         std::string("pins format; candidate family ") +
             (opt.candidate_policy == CandidatePolicy::CompleteWindows ? "depth_bounded_complete_windows" : "maximal_runs_only") +
             "; safe reductions; LB over all backgrounds (8) and all count widths (w_N>=1); depth regimes " +
             (all_regimes_covered ? "all evaluated" : "partially evaluated (memory cap)") +
             (opt.depth_policy == DepthPolicy::FixedDepthWidth
                  ? (opt.certificate == CertificateMode::AllRegimes
                         ? " [stream: fixed depth width; LB: all regimes, dual-only for the skipped ones]"
                         : " [fixed depth width]")
                  : ""));
    if (opt.collect_records) {
      res.bgcolor = lm.values[best.bg_label];
      res.records = best.records;
      res.components_per_grid = lab.per_slice;
    }
    res.components = std::move(best.exported);
  }

  if (!pins_stream.empty() && (flat_stream.empty() || pins_stream.size() <= flat_stream.size())) {
    res.bytes = std::move(pins_stream);
    if (opt.keep_alternative) res.alt_bytes = std::move(flat_stream);
    dg.t("label_format", "PINS_VARIABLE_WIDTH");
  } else {
    res.bytes = std::move(flat_stream);
    if (opt.keep_alternative) res.alt_bytes = std::move(pins_stream);
    dg.t("label_format", "FLAT");
  }
  dg.i("total_bytes", static_cast<int64_t>(res.bytes.size()));
  dg.i("encode_core_ns", ns_since(t_all));
  return res;
}

template EncodeResult encode<uint8_t>(const uint8_t*, const Dims&, const Options&);
template EncodeResult encode<uint16_t>(const uint16_t*, const Dims&, const Options&);
template EncodeResult encode<uint32_t>(const uint32_t*, const Dims&, const Options&);
template EncodeResult encode<uint64_t>(const uint64_t*, const Dims&, const Options&);

}  // namespace cape
