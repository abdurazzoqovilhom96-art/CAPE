#include "cape/incidence.hpp"

#include <string>

namespace cape {

Incidence build_cc_incidence(const std::vector<uint32_t>& alive, const std::vector<Candidate>& cands,
                             const ChainAccess& ch, uint64_t N) {
  Incidence inc;
  inc.off.assign(N + 1, 0);
  for (uint32_t p = 0; p < alive.size(); p++) {
    const Candidate& c = cands[alive[p]];
    if (ch.colmajor) {
      const uint32_t* q = ch.chain(c);
      for (uint32_t t = 0; t < c.len; t++) inc.off[q[t] + 1]++;
    } else {
      for (uint32_t t = 0; t < c.len; t++) inc.off[ch.at(c, t) + 1]++;
    }
  }
  for (uint64_t u = 0; u < N; u++) inc.off[u + 1] += inc.off[u];
  inc.idx.resize(inc.off[N]);
  std::vector<uint64_t> pos(inc.off.begin(), inc.off.end() - 1);
  for (uint32_t p = 0; p < alive.size(); p++) {
    const Candidate& c = cands[alive[p]];
    if (ch.colmajor) {
      const uint32_t* q = ch.chain(c);
      for (uint32_t t = 0; t < c.len; t++) inc.idx[pos[q[t]]++] = p;
    } else {
      for (uint32_t t = 0; t < c.len; t++) inc.idx[pos[ch.at(c, t)]++] = p;
    }
  }
  return inc;
}

uint64_t forecast_solver_bytes(uint64_t V, uint64_t N, uint64_t runs, uint64_t M, uint64_t E) {
  // cc ids (4V) + runs (16R) + candidates (12M) + reduction keys (24M) + incidence (8N + 4E twice:
  // reductions and components) + union-find/components (16N) + witness (4M)
  return 4 * V + 16 * runs + 40 * M + 16 * N + 8 * E + 16 * N;
}

void check_memory(uint64_t bytes, uint64_t cap, const char* what) {
  if (cap != 0 && bytes > cap) {
    throw MemoryCapExceeded(std::string("OOM_PREVENTED: ") + what + " needs ~" + std::to_string(bytes >> 20) +
                            " MiB > cap " + std::to_string(cap >> 20) + " MiB");
  }
}

}  // namespace cape
