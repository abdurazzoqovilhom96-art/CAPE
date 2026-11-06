#include "cape/candidates.hpp"

#include <limits>

namespace cape {

CandidateForecast forecast_candidates(const std::vector<Run>& runs, uint64_t h, CandidatePolicy policy) {
  CandidateForecast f;
  for (const Run& r : runs) {
    if (r.len <= h) {
      f.candidates += 1;
      f.incidences += r.len;
    } else if (policy == CandidatePolicy::CompleteWindows) {
      f.candidates += r.len - h + 1;
      f.incidences += (r.len - h + 1) * h;
    }
  }
  return f;
}

std::vector<Candidate> make_candidates(const std::vector<Run>& runs, uint64_t h, CandidatePolicy policy) {
  const CandidateForecast f = forecast_candidates(runs, h, policy);
  if (f.candidates >= std::numeric_limits<uint32_t>::max()) {
    throw MemoryCapExceeded("candidate count exceeds the 32-bit index space");
  }
  std::vector<Candidate> out;
  out.reserve(f.candidates);
  for (uint32_t r = 0; r < runs.size(); r++) {
    const uint32_t k = runs[r].len;
    if (k <= h) {
      out.push_back(Candidate{r, 0, k});
    } else if (policy == CandidatePolicy::CompleteWindows) {
      const uint32_t hh = static_cast<uint32_t>(h);
      for (uint32_t s = 0; s + hh <= k; s++) out.push_back(Candidate{r, s, hh});
    }
  }
  return out;
}

}  // namespace cape
