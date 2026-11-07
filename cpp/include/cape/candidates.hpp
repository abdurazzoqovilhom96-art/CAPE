// Depth-bounded complete candidate windows (spec section 7) as (run, offset, length) views.
#pragma once

#include <cstdint>
#include <vector>

#include "cape/types.hpp"

namespace cape {

// Read access to a candidate's CC chain without materializing it.
struct ChainAccess {
  const uint32_t* cc = nullptr;        // z-major CC volume (legacy layout); null when colmajor is set
  uint64_t XY = 0;
  const std::vector<Run>* runs = nullptr;
  const uint32_t* colmajor = nullptr;  // optional column-major copy: colmajor[col * Z + z]
  uint64_t Z = 0;
  // Q1 O3: compact column-major copy of slice-local numbers (uint16) and the per-slice id offsets; the global id
  // of (col, z) is zoff[z] + colmajor16[col * Z + z]. Set instead of colmajor.
  const uint16_t* colmajor16 = nullptr;
  const uint32_t* zoff = nullptr;
  uint64_t z_start(const Candidate& c) const { return static_cast<uint64_t>((*runs)[c.run].z0) + c.off; }
  uint32_t at(const Candidate& c, uint32_t t) const {
    const Run& r = (*runs)[c.run];
    if (colmajor) return colmajor[static_cast<uint64_t>(r.col) * Z + r.z0 + c.off + t];
    if (colmajor16) {
      const uint64_t z = static_cast<uint64_t>(r.z0) + c.off + t;
      return zoff[z] + colmajor16[static_cast<uint64_t>(r.col) * Z + z];
    }
    return cc[r.col + XY * (static_cast<uint64_t>(r.z0) + c.off + t)];
  }
  // Q1 O3 (only with colmajor16): chain16(c)[t] + zoff_of(c)[t] == at(c, t)
  const uint16_t* chain16(const Candidate& c) const {
    const Run& r = (*runs)[c.run];
    return colmajor16 + static_cast<uint64_t>(r.col) * Z + r.z0 + c.off;
  }
  const uint32_t* zoff_of(const Candidate& c) const { return zoff + z_start(c); }
  // Contiguous chain (only with colmajor): chain(c)[t] == at(c, t).
  const uint32_t* chain(const Candidate& c) const {
    const Run& r = (*runs)[c.run];
    return colmajor + static_cast<uint64_t>(r.col) * Z + r.z0 + c.off;
  }
  // upstream pin start index x + X*(y + Y*z0) == col + XY*z0
  uint64_t start_index(const Candidate& c) const { return (*runs)[c.run].col + XY * z_start(c); }
  uint32_t label(const Candidate& c) const { return (*runs)[c.run].label; }
};

struct CandidateForecast {
  uint64_t candidates = 0;  // M
  uint64_t incidences = 0;  // E = sum of candidate lengths
};

// h = longest admissible pin (min(Z, 2^(8 w_D))). Runs with length <= h give one candidate; longer
// runs give every length-h window (CompleteWindows) or nothing (MaximalRunsOnly ablation).
CandidateForecast forecast_candidates(const std::vector<Run>& runs, uint64_t h, CandidatePolicy policy);
std::vector<Candidate> make_candidates(const std::vector<Run>& runs, uint64_t h, CandidatePolicy policy);

}  // namespace cape
