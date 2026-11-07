#include "cape/memprobe.hpp"

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <psapi.h>
#endif

namespace cape {

MemSample mem_sample() {
  MemSample s;
#ifdef _WIN32
  PROCESS_MEMORY_COUNTERS pmc;
  if (GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof(pmc))) {
    s.working_set = static_cast<uint64_t>(pmc.WorkingSetSize);
    s.peak_working_set = static_cast<uint64_t>(pmc.PeakWorkingSetSize);
  }
#endif
  return s;
}

}  // namespace cape
