#include "cape/runs.hpp"

namespace cape {

std::vector<Run> column_runs(const uint32_t* cc, const std::vector<uint32_t>& cc_label, const Dims& d) {
  const uint64_t XY = d.XY();
  const uint64_t Z = d.Z;
  if (XY == 0 || Z == 0) return {};

  // pass 1: number of runs per column
  std::vector<uint32_t> count(XY, 1);
  std::vector<uint32_t> cur(XY);
  for (uint64_t col = 0; col < XY; col++) cur[col] = cc_label[cc[col]];
  for (uint64_t z = 1; z < Z; z++) {
    const uint32_t* sl = cc + XY * z;
    for (uint64_t col = 0; col < XY; col++) {
      const uint32_t l = cc_label[sl[col]];
      if (l != cur[col]) {
        count[col]++;
        cur[col] = l;
      }
    }
  }
  std::vector<uint64_t> pos(XY + 1, 0);
  for (uint64_t col = 0; col < XY; col++) pos[col + 1] = pos[col] + count[col];
  std::vector<Run> runs(pos[XY]);

  // pass 2: fill, each column's runs stored contiguously in z order
  std::vector<uint32_t> start(XY, 0);
  for (uint64_t col = 0; col < XY; col++) cur[col] = cc_label[cc[col]];
  for (uint64_t z = 1; z < Z; z++) {
    const uint32_t* sl = cc + XY * z;
    for (uint64_t col = 0; col < XY; col++) {
      const uint32_t l = cc_label[sl[col]];
      if (l != cur[col]) {
        runs[pos[col]++] = Run{static_cast<uint32_t>(col), start[col], static_cast<uint32_t>(z) - start[col], cur[col]};
        start[col] = static_cast<uint32_t>(z);
        cur[col] = l;
      }
    }
  }
  for (uint64_t col = 0; col < XY; col++) {
    runs[pos[col]++] = Run{static_cast<uint32_t>(col), start[col], static_cast<uint32_t>(Z) - start[col], cur[col]};
  }
  return runs;
}

std::vector<Run> column_runs_colmajor(const uint32_t* colmajor, const std::vector<uint32_t>& cc_label, const Dims& d,
                                      uint64_t exact_count) {
  const uint64_t XY = d.XY();
  const uint64_t Z = d.Z;
  std::vector<Run> runs;
  if (XY == 0 || Z == 0) return runs;
  // Q1 O2: with the exact count the array is allocated once (no growth copies, no transient second buffer)
  runs.reserve(exact_count ? exact_count : XY * 2);
  for (uint64_t col = 0; col < XY; col++) {
    const uint32_t* c = colmajor + col * Z;
    uint32_t cur = cc_label[c[0]];
    uint32_t start = 0;
    for (uint64_t z = 1; z < Z; z++) {
      const uint32_t l = cc_label[c[z]];
      if (l != cur) {
        runs.push_back(Run{static_cast<uint32_t>(col), start, static_cast<uint32_t>(z) - start, cur});
        start = static_cast<uint32_t>(z);
        cur = l;
      }
    }
    runs.push_back(Run{static_cast<uint32_t>(col), start, static_cast<uint32_t>(Z) - start, cur});
  }
  return runs;
}

std::vector<Run> column_runs_colmajor16(const uint16_t* colmajor16, const uint32_t* zoff,
                                        const std::vector<uint32_t>& cc_label, const Dims& d, uint64_t exact_count) {
  const uint64_t XY = d.XY();
  const uint64_t Z = d.Z;
  std::vector<Run> runs;
  if (XY == 0 || Z == 0) return runs;
  runs.reserve(exact_count ? exact_count : XY * 2);
  for (uint64_t col = 0; col < XY; col++) {
    const uint16_t* c = colmajor16 + col * Z;
    uint32_t cur = cc_label[zoff[0] + c[0]];
    uint32_t start = 0;
    for (uint64_t z = 1; z < Z; z++) {
      const uint32_t l = cc_label[zoff[z] + c[z]];
      if (l != cur) {
        runs.push_back(Run{static_cast<uint32_t>(col), start, static_cast<uint32_t>(z) - start, cur});
        start = static_cast<uint32_t>(z);
        cur = l;
      }
    }
    runs.push_back(Run{static_cast<uint32_t>(col), start, static_cast<uint32_t>(Z) - start, cur});
  }
  return runs;
}

}  // namespace cape
