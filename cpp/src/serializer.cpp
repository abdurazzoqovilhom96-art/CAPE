#include "cape/serializer.hpp"

#include <algorithm>
#include <string>

namespace cape {

namespace {

void put(std::vector<uint8_t>& out, uint64_t value, int width, const char* what) {
  if (value > width_capacity(width)) {
    throw CapeError(std::string("serializer: ") + what + " value " + std::to_string(value) +
                    " does not fit in " + std::to_string(width) + " byte(s)");
  }
  for (int i = 0; i < width; i++) {
    out.push_back(static_cast<uint8_t>((value >> (8 * i)) & 0xFF));
  }
}

int log2_width(int width) {
  switch (width) {
    case 1: return 0;
    case 2: return 1;
    case 4: return 2;
    case 8: return 3;
    default: throw CapeError("serializer: invalid field width " + std::to_string(width));
  }
}

}  // namespace

int required_count_width(const std::vector<LabelRecords>& labels) {
  uint64_t m = 0;
  for (const auto& l : labels) {
    m = std::max<uint64_t>(m, std::max<uint64_t>(l.pins.size(), l.singletons.size()));
  }
  return byte_width(m);
}

int required_depth_width(const std::vector<LabelRecords>& labels) {
  uint64_t m = 0;
  for (const auto& l : labels) {
    for (const auto& p : l.pins) m = std::max(m, p.depth);
  }
  return byte_width(m);
}

std::vector<uint8_t> serialize_pins_section(uint64_t bgcolor, const std::vector<LabelRecords>& labels,
                                            const std::vector<uint64_t>& components_per_grid, const Widths& w) {
  for (size_t i = 1; i < labels.size(); i++) {
    if (!(labels[i - 1].label_value < labels[i].label_value)) {
      throw CapeError("serializer: written labels must be strictly increasing");
    }
  }
  std::vector<uint8_t> out;
  put(out, bgcolor, w.w_L, "bgcolor");
  put(out, labels.size(), 8, "num_labels");
  for (const auto& l : labels) put(out, l.label_value, w.w_L, "label");
  for (uint64_t c : components_per_grid) put(out, c, w.w_G, "components_per_grid");
  out.push_back(static_cast<uint8_t>(log2_width(w.w_N) | (log2_width(w.w_D) << 2) | (log2_width(w.w_C) << 4)));

  std::vector<PinRecord> pins;
  std::vector<uint32_t> ccs;
  for (const auto& l : labels) {
    pins = l.pins;
    std::sort(pins.begin(), pins.end(), [](const PinRecord& a, const PinRecord& b) {
      return a.start < b.start || (a.start == b.start && a.depth < b.depth);
    });
    put(out, pins.size(), w.w_N, "num_pins");
    uint64_t prev = 0;
    for (const auto& p : pins) {
      if (p.start < prev) throw CapeError("serializer: pin start indices not sorted");
      put(out, p.start - prev, w.w_I, "pin index delta");
      prev = p.start;
    }
    for (const auto& p : pins) put(out, p.depth, w.w_D, "pin depth");
    ccs = l.singletons;
    std::sort(ccs.begin(), ccs.end());
    if (std::adjacent_find(ccs.begin(), ccs.end()) != ccs.end()) {
      throw CapeError("serializer: duplicate singleton CC id");
    }
    put(out, ccs.size(), w.w_N, "num_cc");
    uint64_t prev_cc = 0;
    for (uint32_t c : ccs) {
      put(out, c - prev_cc, w.w_C, "cc id delta");
      prev_cc = c;
    }
  }
  return out;
}

}  // namespace cape
