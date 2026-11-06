#include "cape/local_search.hpp"

#include <algorithm>

namespace cape {

namespace {

class State {
 public:
  explicit State(const LocalModel& m) : m_(m), in_p_(m.M(), 0), in_s_(m.n, 0), cnt_(m.n, 0), mark_(m.n, 0) {}

  void load(const Selection& sel) {
    for (uint32_t p : sel.pins) add_pin(p, false);
    for (uint32_t u : sel.singles) add_single(u, false);
    log_.clear();
  }

  Selection selection() const {
    Selection s;
    for (uint32_t p = 0; p < m_.M(); p++) {
      if (in_p_[p]) s.pins.push_back(p);
    }
    for (uint32_t u = 0; u < m_.n; u++) {
      if (in_s_[u]) s.singles.push_back(u);
    }
    s.cost = cost_;
    return s;
  }

  uint64_t cost() const { return cost_; }
  bool has_pin(uint32_t p) const { return in_p_[p] != 0; }
  void begin() { log_.clear(); }

  void undo() {
    for (size_t i = log_.size(); i-- > 0;) {
      const Op op = log_[i];
      switch (op.kind) {
        case 0: rem_pin(op.idx, false); break;
        case 1: add_pin(op.idx, false); break;
        case 2: rem_single(op.idx, false); break;
        case 3: add_single(op.idx, false); break;
      }
    }
    log_.clear();
  }

  void add_pin(uint32_t p, bool record = true) {
    in_p_[p] = 1;
    for (uint64_t k = m_.off[p]; k < m_.off[p + 1]; k++) cnt_[m_.elem[k]]++;
    cost_ += m_.c;
    if (record) log_.push_back(Op{0, p});
  }
  void rem_pin(uint32_t p, bool record = true) {
    in_p_[p] = 0;
    for (uint64_t k = m_.off[p]; k < m_.off[p + 1]; k++) cnt_[m_.elem[k]]--;
    cost_ -= m_.c;
    if (record) log_.push_back(Op{1, p});
  }
  void add_single(uint32_t u, bool record = true) {
    in_s_[u] = 1;
    cnt_[u]++;
    cost_ += m_.s;
    if (record) log_.push_back(Op{2, u});
  }
  void rem_single(uint32_t u, bool record = true) {
    in_s_[u] = 0;
    cnt_[u]--;
    cost_ -= m_.s;
    if (record) log_.push_back(Op{3, u});
  }

  // Drop singletons and pins that are fully covered by other records, scanning only the
  // neighbourhood of `touched` CCs in ascending order (deterministic).
  void drop_redundant(const std::vector<uint32_t>& touched) {
    for (uint32_t u : touched) {
      if (in_s_[u] && cnt_[u] >= 2) rem_single(u);
    }
    for (uint32_t u : touched) {
      for (uint64_t k = m_.inc_off[u]; k < m_.inc_off[u + 1]; k++) {
        const uint32_t p = m_.inc[k];
        if (!in_p_[p]) continue;
        bool redundant = true;
        for (uint64_t j = m_.off[p]; j < m_.off[p + 1]; j++) {
          if (cnt_[m_.elem[j]] < 2) {
            redundant = false;
            break;
          }
        }
        if (redundant) rem_pin(p);
      }
    }
  }

  // Covers `need` (CCs with cnt == 0) with other pins by the greedy ratio rule, then
  // singletons. Returns every CC touched.
  void repair(std::vector<uint32_t>& need, uint32_t excluded, std::vector<uint32_t>& touched) {
    while (!need.empty()) {
      for (uint32_t u : need) mark_[u] = 1;
      uint32_t best = 0xFFFFFFFFu, best_gain = 0;
      uint64_t best_start = 0;
      uint32_t best_depth = 0;
      for (uint32_t u : need) {
        for (uint64_t k = m_.inc_off[u]; k < m_.inc_off[u + 1]; k++) {
          const uint32_t q = m_.inc[k];
          if (q == excluded || in_p_[q]) continue;
          uint32_t gain = 0;
          for (uint64_t j = m_.off[q]; j < m_.off[q + 1]; j++) gain += mark_[m_.elem[j]];
          if (!(m_.c < m_.s * gain)) continue;
          const bool better = gain > best_gain ||
                              (gain == best_gain && (m_.tie_start[q] < best_start ||
                                                     (m_.tie_start[q] == best_start && m_.tie_depth[q] < best_depth)));
          if (best == 0xFFFFFFFFu || better) {
            best = q;
            best_gain = gain;
            best_start = m_.tie_start[q];
            best_depth = m_.tie_depth[q];
          }
        }
      }
      for (uint32_t u : need) mark_[u] = 0;
      if (best == 0xFFFFFFFFu) {
        for (uint32_t u : need) {
          add_single(u);
          touched.push_back(u);
        }
        need.clear();
        break;
      }
      add_pin(best);
      for (uint64_t j = m_.off[best]; j < m_.off[best + 1]; j++) touched.push_back(m_.elem[j]);
      std::vector<uint32_t> rest;
      for (uint32_t u : need) {
        if (cnt_[u] == 0) rest.push_back(u);
      }
      need.swap(rest);
    }
  }

  uint32_t count(uint32_t u) const { return cnt_[u]; }
  bool single(uint32_t u) const { return in_s_[u] != 0; }

 private:
  struct Op {
    uint8_t kind;
    uint32_t idx;
  };
  const LocalModel& m_;
  std::vector<uint8_t> in_p_, in_s_;
  std::vector<uint32_t> cnt_;
  std::vector<uint8_t> mark_;
  std::vector<Op> log_;
  uint64_t cost_ = 0;
};

}  // namespace

Selection local_search(const LocalModel& m, const Selection& start, uint64_t per_component_budget,
                       uint64_t& remaining_total, LocalStats& st) {
  if (m.M() == 0) return start;
  State S(m);
  S.load(start);
  auto can_check = [&]() { return st.checks < per_component_budget && remaining_total > 0; };
  auto charge = [&]() {
    st.checks++;
    remaining_total--;
  };
  std::vector<uint32_t> touched, need;
  bool improved = true;
  while (improved && can_check()) {
    improved = false;
    // add-drop
    for (uint32_t q = 0; q < m.M() && can_check(); q++) {
      if (S.has_pin(q)) continue;
      uint32_t singles_hit = 0, covered_hit = 0;
      for (uint64_t j = m.off[q]; j < m.off[q + 1]; j++) {
        const uint32_t u = m.elem[j];
        singles_hit += S.single(u) ? 1u : 0u;
        covered_hit += S.count(u) > 0 ? 1u : 0u;
      }
      if (singles_hit == 0 && covered_hit < 2) continue;  // cannot make anything redundant
      charge();
      const uint64_t before = S.cost();
      S.begin();
      S.add_pin(q);
      touched.assign(m.elem.begin() + m.off[q], m.elem.begin() + m.off[q + 1]);
      S.drop_redundant(touched);
      if (S.cost() < before) {
        improved = true;
        st.improvements++;
      } else {
        S.undo();
      }
    }
    // drop-repair
    for (uint32_t p = 0; p < m.M() && can_check(); p++) {
      if (!S.has_pin(p)) continue;
      charge();
      const uint64_t before = S.cost();
      S.begin();
      S.rem_pin(p);
      touched.assign(m.elem.begin() + m.off[p], m.elem.begin() + m.off[p + 1]);
      need.clear();
      for (uint32_t u : touched) {
        if (S.count(u) == 0) need.push_back(u);
      }
      S.repair(need, p, touched);
      std::sort(touched.begin(), touched.end());
      touched.erase(std::unique(touched.begin(), touched.end()), touched.end());
      S.drop_redundant(touched);
      if (S.cost() < before) {
        improved = true;
        st.improvements++;
      } else {
        S.undo();
      }
    }
  }
  return S.selection();
}

}  // namespace cape
