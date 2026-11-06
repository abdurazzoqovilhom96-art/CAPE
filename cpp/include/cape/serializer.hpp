// Explicit-record serializer for the PINS_VARIABLE_WIDTH labels section (spec section 6).
// It never converts a pin into CC ids or vice versa, and refuses any field overflow.
#pragma once

#include <cstdint>
#include <vector>

#include "cape/types.hpp"

namespace cape {

struct PinRecord {
  uint64_t start;  // upstream start index x + X*(y + Y*z0)
  uint64_t depth;  // length - 1
};

struct LabelRecords {
  uint64_t label_value = 0;
  std::vector<PinRecord> pins;     // any order; serialized sorted by start
  std::vector<uint32_t> singletons;  // global CC ids; serialized sorted
};

// Smallest widths that fit the records (count/depth/cc compaction, spec sections 6, 39.5).
int required_count_width(const std::vector<LabelRecords>& labels);
int required_depth_width(const std::vector<LabelRecords>& labels);

std::vector<uint8_t> serialize_pins_section(uint64_t bgcolor, const std::vector<LabelRecords>& labels,
                                            const std::vector<uint64_t>& components_per_grid, const Widths& w);

}  // namespace cape
