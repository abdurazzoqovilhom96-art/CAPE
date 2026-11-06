// The only translation unit that includes the pinned upstream Crackle headers.
// Stream assembly mirrors crackle::compress_helper (crackle.hpp lines 75-221) step by step;
// tests check byte equality with the upstream encoder.

#include "cape/upstream_bridge.hpp"

#include <algorithm>
#include <cmath>
#include <thread>
#include <unordered_map>

#include "crackle.hpp"

namespace cape::bridge {

template <typename LABEL>
Labeling cc_label(const LABEL* labels, const Dims& d) {
  Labeling out;
  out.d = d;
  const uint64_t V = d.V();
  const uint64_t sxy = d.XY();
  out.cc.resize(V);
  out.per_slice.assign(d.Z, 0);
  out.cc_crcs.assign(d.Z, 0);
  if (V == 0) return out;
  uint64_t N = 0;
  crackle::cc3d::connected_components<LABEL, uint32_t>(labels, static_cast<int64_t>(d.X), static_cast<int64_t>(d.Y),
                                                      static_cast<int64_t>(d.Z), out.per_slice, out.cc.data(), N);
  out.N = N;
  std::vector<uint32_t> local(sxy);
  uint64_t offset = 0;
  for (uint64_t z = 0; z < d.Z; z++) {
    const uint32_t* src = out.cc.data() + sxy * z;
    for (uint64_t i = 0; i < sxy; i++) local[i] = src[i] - static_cast<uint32_t>(offset);
    out.cc_crcs[z] = crackle::crc::crc32c(local.data(), sxy);
    offset += out.per_slice[z];
  }
  return out;
}

template <typename LABEL>
Boundary boundaries(const LABEL* labels, const Dims& d, bool impermissible, int markov_order, size_t parallel) {
  Boundary b;
  b.crack_format = impermissible ? static_cast<int>(crackle::CrackFormat::IMPERMISSIBLE)
                                 : static_cast<int>(crackle::CrackFormat::PERMISSIBLE);
  b.markov_order = markov_order;
  if (parallel == 0) parallel = std::thread::hardware_concurrency();
  parallel = std::max<size_t>(1, std::min<size_t>(parallel, static_cast<size_t>(std::max<uint64_t>(d.Z, 1))));

  auto codepoints = crackle::crackcodes::encode_boundaries(labels, static_cast<int64_t>(d.X), static_cast<int64_t>(d.Y),
                                                           static_cast<int64_t>(d.Z), /*permissible=*/!impermissible,
                                                           parallel);
  if (b.markov_order > 0) {
    bool empty = true;
    for (auto& code : codepoints) {
      if (code.size()) {
        empty = false;
        break;
      }
    }
    if (empty) b.markov_order = 0;
  }
  b.crack_codes.resize(codepoints.size());
  ThreadPool pool(parallel);
  if (b.markov_order > 0) {
    auto stats = crackle::markov::gather_statistics(codepoints, b.markov_order, parallel);
    auto model = crackle::markov::stats_to_model(stats);
    b.stored_model = crackle::markov::to_stored_model(model);
    for (uint64_t z = 0; z < codepoints.size(); z++) {
      pool.enqueue([&, z](size_t) {
        b.crack_codes[z] = crackle::markov::compress(codepoints[z], model, b.markov_order, d.X, d.Y);
      });
    }
    pool.join();
  } else {
    for (uint64_t z = 0; z < codepoints.size(); z++) {
      pool.enqueue([&, z](size_t) { b.crack_codes[z] = crackle::crackcodes::pack_codepoints(codepoints[z], d.X, d.Y); });
    }
    pool.join();
  }
  return b;
}

template <typename LABEL>
std::vector<uint8_t> flat_section(const LABEL* labels, const Dims& d, int stored_width, size_t parallel,
                                  std::vector<uint32_t>& cc_crcs) {
  if (parallel == 0) parallel = std::thread::hardware_concurrency();
  parallel = std::max<size_t>(1, std::min<size_t>(parallel, static_cast<size_t>(std::max<uint64_t>(d.Z, 1))));
  const auto sx = static_cast<int64_t>(d.X), sy = static_cast<int64_t>(d.Y), sz = static_cast<int64_t>(d.Z);
  switch (stored_width) {
    case 1: {
      auto [bin, crcs] = crackle::labels::encode_flat<LABEL, uint8_t>(labels, sx, sy, sz, parallel);
      cc_crcs = std::move(crcs);
      return bin;
    }
    case 2: {
      auto [bin, crcs] = crackle::labels::encode_flat<LABEL, uint16_t>(labels, sx, sy, sz, parallel);
      cc_crcs = std::move(crcs);
      return bin;
    }
    case 4: {
      auto [bin, crcs] = crackle::labels::encode_flat<LABEL, uint32_t>(labels, sx, sy, sz, parallel);
      cc_crcs = std::move(crcs);
      return bin;
    }
    default: {
      auto [bin, crcs] = crackle::labels::encode_flat<LABEL, uint64_t>(labels, sx, sy, sz, parallel);
      cc_crcs = std::move(crcs);
      return bin;
    }
  }
}

template <typename LABEL>
std::vector<uint8_t> stock_pins_section(const LABEL* labels, const Dims& d, bool optimize, int stored_width,
                                        std::vector<uint32_t>& cc_crcs) {
  const auto sx = static_cast<int64_t>(d.X), sy = static_cast<int64_t>(d.Y), sz = static_cast<int64_t>(d.Z);
  auto [all_pins, per_slice, n_components, crcs] = crackle::pins::compute(labels, sx, sy, sz, optimize);
  cc_crcs = std::move(crcs);
  const int64_t index_width = crackle::lib::compute_byte_width(d.V());
  switch (stored_width) {
    case 1:
      return crackle::labels::encode_condensed_pins<LABEL, uint8_t>(all_pins, sx, sy, sz, index_width, per_slice,
                                                                    n_components, true, 0);
    case 2:
      return crackle::labels::encode_condensed_pins<LABEL, uint16_t>(all_pins, sx, sy, sz, index_width, per_slice,
                                                                     n_components, true, 0);
    case 4:
      return crackle::labels::encode_condensed_pins<LABEL, uint32_t>(all_pins, sx, sy, sz, index_width, per_slice,
                                                                     n_components, true, 0);
    default:
      return crackle::labels::encode_condensed_pins<LABEL, uint64_t>(all_pins, sx, sy, sz, index_width, per_slice,
                                                                     n_components, true, 0);
  }
}

namespace {

// Copy of crackle::labels::encode_condensed_pins (vendor/crackle/src/labels.hpp, SHA 14b39b1,
// BSD-3-Clause, see THIRD_PARTY_NOTICES.md) with the count-width fix: num_pins_width covers
// max(pin count, upstream's own width input, written CC-id count) of every label.
template <typename STORED_LABEL>
std::vector<unsigned char> condensed_pins_corrected(
    std::unordered_map<uint64_t, std::vector<crackle::pins::CandidatePin>>& all_pins, const int64_t sx,
    const int64_t sy, const int64_t sz, const int64_t index_width, const std::vector<uint64_t>& num_components_per_slice,
    const uint64_t num_components, bool& widened) {
  const STORED_LABEL bgcolor = crackle::labels::find_bgcolor<STORED_LABEL>(all_pins, sz);
  all_pins.erase(bgcolor);

  uint64_t max_pins = 0;
  uint64_t max_depth = 0;
  uint64_t total_pins = 0;
  for (auto& [label, pins] : all_pins) {
    max_pins = std::max(static_cast<uint64_t>(pins.size()), max_pins);
    total_pins += pins.size();
    for (auto& pin : pins) max_depth = std::max(max_depth, pin.depth());
  }
  std::vector<STORED_LABEL> all_labels;
  all_labels.reserve(all_pins.size());
  for (auto& [label, pins] : all_pins) all_labels.push_back(label);
  std::sort(all_labels.begin(), all_labels.end());

  const uint8_t depth_width = crackle::lib::compute_byte_width(max_depth);
  const uint8_t cc_label_width = crackle::lib::compute_byte_width(num_components);
  const uint8_t component_width = crackle::lib::compute_byte_width(sx * sy);
  const uint8_t pin_bytes = index_width + depth_width;
  const uint8_t cc_efficient_threshold = pin_bytes / cc_label_width;

  // the fix: count what is actually written per label (pins kept as pins, CC ids of short pins)
  uint64_t max_written_count = max_pins;
  for (auto label : all_labels) {
    uint64_t n_pin = 0, n_cc = 0;
    for (auto& pin : all_pins[label]) {
      if (pin.depth() < cc_efficient_threshold) {
        n_cc += pin.ccids.size();
      } else {
        n_pin++;
      }
    }
    max_written_count = std::max({max_written_count, n_pin, n_cc});
  }
  const uint8_t upstream_width = crackle::lib::compute_byte_width(max_pins);
  const uint8_t num_pins_width = crackle::lib::compute_byte_width(max_written_count);
  widened = num_pins_width != upstream_width;

  const uint8_t combined_width = (static_cast<uint8_t>(log2(num_pins_width)) |
                                  (static_cast<uint8_t>(log2(depth_width)) << 2) |
                                  (static_cast<uint8_t>(log2(cc_label_width)) << 4));
  auto start_idx = [&](const crackle::pins::CandidatePin& p) { return p.start_idx(sx, sy); };

  std::vector<unsigned char> binary(sizeof(STORED_LABEL) + 8 + sizeof(STORED_LABEL) * all_labels.size() +
                                    (component_width * num_components_per_slice.size()) + 1 +
                                    (2 * num_pins_width * all_labels.size()) + (index_width + depth_width) * total_pins);
  int64_t i = 0;
  i += crackle::lib::itoc(bgcolor, binary, i);
  i += crackle::lib::itoc(static_cast<uint64_t>(all_labels.size()), binary, i);
  for (auto label : all_labels) i += crackle::lib::itoc(label, binary, i);
  for (auto val : num_components_per_slice) i += crackle::lib::itocd(val, binary, i, component_width);
  i += crackle::lib::itoc(combined_width, binary, i);

  for (uint64_t label = 0; label < all_labels.size(); label++) {
    auto& pins = all_pins[all_labels[label]];
    std::sort(pins.begin(), pins.end(),
              [&](crackle::pins::CandidatePin& a, crackle::pins::CandidatePin& b) { return start_idx(a) < start_idx(b); });
    std::vector<uint64_t> pin_repr, cc_repr;
    for (uint64_t j = 0; j < pins.size(); j++) {
      if (pins[j].depth() < cc_efficient_threshold) {
        cc_repr.push_back(j);
      } else {
        pin_repr.push_back(j);
      }
    }
    std::vector<uint64_t> pin_index;
    pin_index.reserve(pins.size());
    for (uint64_t j : pin_repr) pin_index.push_back(start_idx(pins[j]));
    if (pin_index.size() > 1) {
      for (uint64_t j = pin_index.size() - 1; j >= 1; j--) pin_index[j] -= pin_index[j - 1];
    }
    // a corrected width can exceed upstream's size estimate: grow the buffer when needed
    const uint64_t need = i + num_pins_width + (index_width + depth_width) * pin_repr.size();
    if (binary.size() < need) binary.resize(need);
    i += crackle::lib::itocd(pin_repr.size(), binary, i, num_pins_width);
    for (uint64_t index : pin_index) i += crackle::lib::itocd(index, binary, i, index_width);
    for (uint64_t j : pin_repr) i += crackle::lib::itocd(pins[j].depth(), binary, i, depth_width);

    std::vector<uint32_t> cc_ids;
    for (uint64_t j : cc_repr) {
      for (uint32_t ccid : pins[j].ccids) cc_ids.push_back(ccid);
    }
    std::sort(cc_ids.begin(), cc_ids.end());
    if (cc_ids.size() > 1) {
      for (uint64_t j = cc_ids.size() - 1; j >= 1; j--) cc_ids[j] -= cc_ids[j - 1];
    }
    if (binary.size() < i + num_pins_width + cc_label_width * cc_ids.size()) {
      binary.resize(i + num_pins_width + cc_label_width * cc_ids.size());
    }
    i += crackle::lib::itocd(cc_ids.size(), binary, i, num_pins_width);
    for (uint32_t ccid : cc_ids) i += crackle::lib::itocd(ccid, binary, i, cc_label_width);
  }
  binary.resize(i);
  return binary;
}

}  // namespace

template <typename LABEL>
std::vector<uint8_t> stock_pins_section_corrected(const LABEL* labels, const Dims& d, bool optimize, int stored_width,
                                                  std::vector<uint32_t>& cc_crcs, bool& widened) {
  const auto sx = static_cast<int64_t>(d.X), sy = static_cast<int64_t>(d.Y), sz = static_cast<int64_t>(d.Z);
  auto [all_pins, per_slice, n_components, crcs] = crackle::pins::compute(labels, sx, sy, sz, optimize);
  cc_crcs = std::move(crcs);
  const int64_t index_width = crackle::lib::compute_byte_width(d.V());
  switch (stored_width) {
    case 1:
      return condensed_pins_corrected<uint8_t>(all_pins, sx, sy, sz, index_width, per_slice, n_components, widened);
    case 2:
      return condensed_pins_corrected<uint16_t>(all_pins, sx, sy, sz, index_width, per_slice, n_components, widened);
    case 4:
      return condensed_pins_corrected<uint32_t>(all_pins, sx, sy, sz, index_width, per_slice, n_components, widened);
    default:
      return condensed_pins_corrected<uint64_t>(all_pins, sx, sy, sz, index_width, per_slice, n_components, widened);
  }
}

template <typename LABEL>
uint64_t pixel_pairs(const LABEL* labels, uint64_t voxels) {
  return voxels ? static_cast<uint64_t>(crackle::lib::pixel_pairs(labels, voxels)) : 0;
}

template <typename LABEL>
uint64_t max_label(const LABEL* labels, uint64_t voxels) {
  return voxels ? static_cast<uint64_t>(crackle::lib::max_label(labels, voxels)) : 0;
}

template <typename LABEL>
std::vector<uint8_t> stock_compress(const LABEL* labels, const Dims& d, bool allow_pins, int markov_order,
                                    bool optimize_pins, size_t parallel) {
  return crackle::compress<LABEL>(labels, static_cast<int64_t>(d.X), static_cast<int64_t>(d.Y),
                                  static_cast<int64_t>(d.Z), allow_pins, /*fortran_order=*/true,
                                  static_cast<uint64_t>(markov_order), optimize_pins, /*auto_bgcolor=*/true,
                                  /*manual_bgcolor=*/0, parallel);
}

std::vector<uint8_t> assemble(const HeaderFields& h, const std::vector<uint8_t>& labels_section, const Boundary& b,
                              const std::vector<uint32_t>& cc_crcs) {
  crackle::CrackleHeader header(
      /*format_version=*/crackle::CrackleHeader::current_version,
      /*label_format=*/static_cast<crackle::LabelFormat>(h.label_format),
      /*crack_format=*/static_cast<crackle::CrackFormat>(b.crack_format),
      /*is_signed=*/false,
      /*data_width=*/static_cast<uint8_t>(h.data_width),
      /*stored_data_width=*/static_cast<uint8_t>(h.stored_data_width),
      /*sx=*/static_cast<uint32_t>(h.d.X), /*sy=*/static_cast<uint32_t>(h.d.Y), /*sz=*/static_cast<uint32_t>(h.d.Z),
      /*grid_size=*/2147483648u,
      /*num_label_bytes=*/0,
      /*fortran_order=*/true,
      /*markov_model_order=*/static_cast<uint8_t>(b.markov_order),
      /*is_sorted=*/true,
      /*crc=*/0xFF,
      /*is_remapped=*/false);
  header.num_label_bytes = labels_section.size();

  const uint64_t sz = h.d.Z;
  std::vector<unsigned char> z_index(sizeof(uint32_t) * sz);
  uint64_t code_size = 0;
  int64_t i = 0;
  for (uint64_t z = 0; z < sz; z++) {
    i += crackle::lib::itoc(static_cast<uint32_t>(b.crack_codes[z].size()), z_index, i);
    code_size += b.crack_codes[z].size();
  }
  const uint32_t z_index_crc = crackle::crc::crc32c(z_index);
  z_index.resize(sizeof(uint32_t) * (sz + 1));
  crackle::lib::itoc(z_index_crc, z_index, i);

  const uint32_t labels_crc = crackle::crc::crc32c(labels_section);

  std::vector<unsigned char> out;
  out.reserve(header.header_bytes() + z_index.size() + labels_section.size() + b.stored_model.size() + code_size +
              4 + 4 * sz);
  std::vector<unsigned char> header_bytes = header.tobytes();
  out.insert(out.end(), header_bytes.begin(), header_bytes.end());
  out.insert(out.end(), z_index.begin(), z_index.end());
  out.insert(out.end(), labels_section.begin(), labels_section.end());
  if (b.markov_order > 0) out.insert(out.end(), b.stored_model.begin(), b.stored_model.end());
  for (const auto& code : b.crack_codes) out.insert(out.end(), code.begin(), code.end());
  crackle::lib::itoc_push_back(labels_crc, out);
  for (uint32_t c : cc_crcs) crackle::lib::itoc_push_back(c, out);
  return out;
}

uint32_t crc32c(const uint8_t* data, size_t n) { return crackle::crc::crc32c(data, n); }

#define CAPE_INSTANTIATE(T)                                                                                   \
  template Labeling cc_label<T>(const T*, const Dims&);                                                       \
  template Boundary boundaries<T>(const T*, const Dims&, bool, int, size_t);                                  \
  template std::vector<uint8_t> flat_section<T>(const T*, const Dims&, int, size_t, std::vector<uint32_t>&); \
  template std::vector<uint8_t> stock_pins_section<T>(const T*, const Dims&, bool, int, std::vector<uint32_t>&); \
  template std::vector<uint8_t> stock_pins_section_corrected<T>(const T*, const Dims&, bool, int,                \
                                                                std::vector<uint32_t>&, bool&);                  \
  template uint64_t pixel_pairs<T>(const T*, uint64_t);                                                       \
  template uint64_t max_label<T>(const T*, uint64_t);                                                         \
  template std::vector<uint8_t> stock_compress<T>(const T*, const Dims&, bool, int, bool, size_t);

CAPE_INSTANTIATE(uint8_t)
CAPE_INSTANTIATE(uint16_t)
CAPE_INSTANTIATE(uint32_t)
CAPE_INSTANTIATE(uint64_t)

#undef CAPE_INSTANTIATE

}  // namespace cape::bridge
