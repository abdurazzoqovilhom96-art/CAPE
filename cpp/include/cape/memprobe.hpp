// Q1 instrumentation: process working set and peak working set (Windows GetProcessMemoryInfo). Used only when
// Options::profile_memory is set; never on timed or byte-measured runs. Other platforms report zeros.
#pragma once

#include <cstdint>

namespace cape {

struct MemSample {
  uint64_t working_set = 0;
  uint64_t peak_working_set = 0;
};

MemSample mem_sample();

}  // namespace cape
