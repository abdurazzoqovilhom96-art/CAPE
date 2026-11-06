#include "cape/candidate_store.hpp"

#include <limits>

namespace cape {

namespace {

// Does the neighbour column (runs [p, e), z-ordered partition of [0, Z)) hold a candidate with z-range
// [zs, zs + len) and dense label `label`? p only moves forward: zs never decreases within one column.
inline bool has_twin(const std::vector<Run>& runs, uint32_t& p, uint32_t e, uint64_t zs, uint32_t len,
                     uint32_t label, uint64_t h, CandidatePolicy policy) {
  while (p < e && static_cast<uint64_t>(runs[p].z0) + runs[p].len <= zs) p++;
  if (p == e) return false;
  const Run& q = runs[p];
  if (q.label != label || q.z0 > zs) return false;
  if (zs + len > static_cast<uint64_t>(q.z0) + q.len) return false;
  if (q.len <= h) return q.z0 == zs && q.len == len;  // q is one whole-run candidate
  // q gives every length-h window (complete windows) or nothing (maximal runs only)
  return policy == CandidatePolicy::CompleteWindows && len == h;
}

}  // namespace

std::vector<Candidate> make_candidates_dedup(const std::vector<Run>& runs, uint64_t h, CandidatePolicy policy,
                                             uint64_t X, uint64_t XY, bool singleton_rule, uint64_t pin_cost,
                                             uint64_t single_cost, CandidateGenStats& st) {
  st = CandidateGenStats{};
  const CandidateForecast f = forecast_candidates(runs, h, policy);
  if (f.candidates >= std::numeric_limits<uint32_t>::max()) {
    throw MemoryCapExceeded("candidate count exceeds the 32-bit index space");
  }
  if (runs.size() >= std::numeric_limits<uint32_t>::max()) {
    throw MemoryCapExceeded("run count exceeds the 32-bit index space");
  }
  // column -> first run (runs are sorted by column, then z)
  std::vector<uint32_t> first(XY + 1, 0);
  for (const Run& r : runs) first[static_cast<uint64_t>(r.col) + 1]++;
  for (uint64_t c = 0; c < XY; c++) first[c + 1] += first[c];

  std::vector<Candidate> out;
  out.reserve(static_cast<size_t>(f.candidates / 4 + 16));
  for (uint64_t col = 0; col < XY; col++) {
    const bool has_left = X > 0 && (col % X) != 0;
    const bool has_up = col >= X;
    uint32_t pl = has_left ? first[col - 1] : 0;
    const uint32_t el = has_left ? first[col] : 0;
    uint32_t pu = has_up ? first[col - X] : 0;
    const uint32_t eu = has_up ? first[col - X + 1] : 0;
    for (uint32_t r = first[col]; r < first[col + 1]; r++) {
      const Run& run = runs[r];
      auto emit = [&](uint32_t off, uint32_t len) {
        st.total++;
        if (singleton_rule && static_cast<uint64_t>(len) * single_cost <= pin_cost) return;
        st.after_singleton++;
        const uint64_t zs = static_cast<uint64_t>(run.z0) + off;
        if ((has_left && has_twin(runs, pl, el, zs, len, run.label, h, policy)) ||
            (has_up && has_twin(runs, pu, eu, zs, len, run.label, h, policy))) {
          st.adjacent_dropped++;
          return;
        }
        out.push_back(Candidate{r, off, len});
      };
      if (run.len <= h) {
        emit(0, run.len);
      } else if (policy == CandidatePolicy::CompleteWindows) {
        const uint32_t hh = static_cast<uint32_t>(h);
        for (uint32_t s = 0; s + hh <= run.len; s++) emit(s, hh);
      }
    }
  }
  return out;
}

}  // namespace cape
