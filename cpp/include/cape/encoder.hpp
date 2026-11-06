// CAPE encoder entry points (spec sections 5-14, 25 `encoder`).
#pragma once

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include "cape/serializer.hpp"
#include "cape/types.hpp"

namespace cape {

struct Diagnostics {
  std::vector<std::pair<std::string, int64_t>> ints;
  std::vector<std::pair<std::string, uint64_t>> uints;  // label values are full-range uint64
  std::vector<std::pair<std::string, double>> reals;
  std::vector<std::pair<std::string, std::string>> texts;
  std::vector<std::pair<std::string, std::vector<int64_t>>> arrays;

  void i(const std::string& k, int64_t v) { ints.emplace_back(k, v); }
  void u(const std::string& k, uint64_t v) { uints.emplace_back(k, v); }
  void r(const std::string& k, double v) { reals.emplace_back(k, v); }
  void t(const std::string& k, std::string v) { texts.emplace_back(k, std::move(v)); }
  void a(const std::string& k, std::vector<int64_t> v) { arrays.emplace_back(k, std::move(v)); }
};

// A written component model exported for the offline CP-SAT audit (spec section 12).
struct ExportedComponent {
  uint32_t label_index = 0;
  uint32_t n = 0;
  uint64_t pin_cost = 0, single_cost = 0;
  uint64_t ub = 0, lb = 0;
  int status = 0;  // SolveStatus
  std::vector<std::vector<uint32_t>> sets;
};

struct EncodeResult {
  std::vector<uint8_t> bytes;
  Diagnostics diag;
  std::vector<ExportedComponent> components;
  // filled when Options::collect_records (tests / certificates)
  uint64_t bgcolor = 0;
  std::vector<LabelRecords> records;
  std::vector<uint64_t> components_per_grid;
  // Options::keep_alternative: the other complete stream (flat <-> pins) when both were built
  std::vector<uint8_t> alt_bytes;
  std::vector<uint32_t> cc;  // Options::return_cc
};

// labels: x-fastest (Fortran (x,y,z)) unsigned array of dims d. Never returns a stream that
// violates the format invariants; throws CapeError / MemoryCapExceeded / UnsupportedInput.
template <typename LABEL>
EncodeResult encode(const LABEL* labels, const Dims& d, const Options& opt);

}  // namespace cape
