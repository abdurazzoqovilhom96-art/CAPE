// _crackle_vendor: Python bindings to the pinned upstream Crackle C++ sources
// (vendor/crackle @ 14b39b196a14b3b1ba7d1cd34f350c324308000f).
//
// Purpose: the stock Crackle baseline compiled with exactly the same compiler and
// flags as CAPE (fair timing, spec section 20), plus read-only access to the stock
// pin selection (method `stock_cover`, spec section 17.1).
//
// The compress/decompress glue mirrors upstream src/fastcrackle.cpp
// (BSD-3-Clause, William Silversmith / Seung Lab). Upstream files are NOT modified.
// The module name differs from the PyPI wheel's `fastcrackle` so both can be
// imported in one process (spec section 24: separate import names).

#define PYBIND11_DETAILED_ERROR_MESSAGES
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "crackle.hpp"

namespace py = pybind11;

namespace {

using ssize_t = py::ssize_t;

constexpr const char* kVendorSha = "14b39b196a14b3b1ba7d1cd34f350c324308000f";

struct Dims {
  uint64_t sx, sy, sz;
};

// Upstream expects x-fastest (Fortran) voxel order. We require a 3D F-contiguous
// array so that no hidden copy happens inside the timed region.
Dims require_fortran_3d(const py::array& labels) {
  if (labels.ndim() != 3) {
    throw std::invalid_argument("_crackle_vendor: expected a 3D array shaped (x, y, z)");
  }
  if (!(labels.flags() & py::array::f_style)) {
    throw std::invalid_argument("_crackle_vendor: array must be Fortran-contiguous (pass canonical_zyx.T)");
  }
  return Dims{static_cast<uint64_t>(labels.shape(0)), static_cast<uint64_t>(labels.shape(1)),
              static_cast<uint64_t>(labels.shape(2))};
}

void require_unsigned(const py::array& labels) {
  if (labels.dtype().kind() != 'u') {
    throw std::invalid_argument("_crackle_vendor: only unsigned integer label volumes are in scope");
  }
}

template <typename LABEL>
py::bytes compress_typed(const py::array& labels, const Dims d, const bool allow_pins,
                         const uint64_t markov_model_order, const bool optimize_pins,
                         const bool auto_bgcolor, const int64_t manual_bgcolor,
                         const size_t parallel) {
  const LABEL* data = static_cast<const LABEL*>(labels.data());
  std::vector<unsigned char> buf;
  {
    py::gil_scoped_release release;
    buf = crackle::compress<LABEL>(data, d.sx, d.sy, d.sz, allow_pins,
                                   /*fortran_order=*/true, markov_model_order, optimize_pins,
                                   auto_bgcolor, manual_bgcolor, parallel);
  }
  return py::bytes(reinterpret_cast<const char*>(buf.data()), buf.size());
}

py::bytes compress(const py::array& labels, const bool allow_pins, const uint64_t markov_model_order,
                   const bool optimize_pins, const bool auto_bgcolor, const int64_t manual_bgcolor,
                   const size_t parallel) {
  require_unsigned(labels);
  const Dims d = require_fortran_3d(labels);
  switch (labels.dtype().itemsize()) {
    case 1: return compress_typed<uint8_t>(labels, d, allow_pins, markov_model_order, optimize_pins, auto_bgcolor, manual_bgcolor, parallel);
    case 2: return compress_typed<uint16_t>(labels, d, allow_pins, markov_model_order, optimize_pins, auto_bgcolor, manual_bgcolor, parallel);
    case 4: return compress_typed<uint32_t>(labels, d, allow_pins, markov_model_order, optimize_pins, auto_bgcolor, manual_bgcolor, parallel);
    case 8: return compress_typed<uint64_t>(labels, d, allow_pins, markov_model_order, optimize_pins, auto_bgcolor, manual_bgcolor, parallel);
    default: throw std::invalid_argument("_crackle_vendor: unsupported itemsize");
  }
}

template <typename LABEL>
py::array decompress_typed(const crackle::CrackleHeader& head, const uint8_t* buffer,
                           const uint64_t num_bytes, const size_t parallel) {
  const uint64_t sx = head.sx, sy = head.sy, sz = head.sz;
  const ssize_t w = static_cast<ssize_t>(sizeof(LABEL));
  py::array_t<LABEL> arr;
  if (head.fortran_order) {
    arr = py::array_t<LABEL>({static_cast<ssize_t>(sx), static_cast<ssize_t>(sy), static_cast<ssize_t>(sz)},
                             {w, static_cast<ssize_t>(sx) * w, static_cast<ssize_t>(sx * sy) * w});
  } else {
    arr = py::array_t<LABEL>({static_cast<ssize_t>(sx), static_cast<ssize_t>(sy), static_cast<ssize_t>(sz)});
  }
  if (sx * sy * sz == 0) {
    return arr;
  }
  LABEL* out = arr.mutable_data();
  {
    py::gil_scoped_release release;
    crackle::decompress<LABEL, LABEL>(buffer, num_bytes, out, /*z_start=*/0, /*z_end=*/-1, parallel,
                                      std::nullopt);
  }
  return arr;
}

py::array decompress(const py::bytes& payload, const size_t parallel) {
  const std::string_view view(payload);
  const auto* data = reinterpret_cast<const uint8_t*>(view.data());
  if (view.size() < crackle::CrackleHeader::header_size_v0) {
    throw std::invalid_argument("_crackle_vendor: buffer too small for a Crackle header");
  }
  const crackle::CrackleHeader head(data);
  switch (head.data_width) {
    case 1: return decompress_typed<uint8_t>(head, data, view.size(), parallel);
    case 2: return decompress_typed<uint16_t>(head, data, view.size(), parallel);
    case 4: return decompress_typed<uint32_t>(head, data, view.size(), parallel);
    default: return decompress_typed<uint64_t>(head, data, view.size(), parallel);
  }
}

py::dict header_info(const py::bytes& payload) {
  const std::string_view view(payload);
  const auto* data = reinterpret_cast<const uint8_t*>(view.data());
  if (view.size() < crackle::CrackleHeader::header_size_v0) {
    throw std::invalid_argument("_crackle_vendor: buffer too small for a Crackle header");
  }
  const crackle::CrackleHeader h(data);
  py::dict out;
  out["format_version"] = static_cast<int>(h.format_version);
  out["label_format"] = static_cast<int>(h.label_format);
  out["crack_format"] = static_cast<int>(h.crack_format);
  out["is_signed"] = h.is_signed;
  out["data_width"] = static_cast<int>(h.data_width);
  out["stored_data_width"] = static_cast<int>(h.stored_data_width);
  out["sx"] = h.sx;
  out["sy"] = h.sy;
  out["sz"] = h.sz;
  out["grid_size"] = h.grid_size;
  out["num_label_bytes"] = h.num_label_bytes;
  out["fortran_order"] = h.fortran_order;
  out["markov_model_order"] = static_cast<int>(h.markov_model_order);
  out["is_sorted"] = h.is_sorted;
  out["is_remapped"] = h.is_remapped;
  out["header_bytes"] = h.header_bytes();
  out["grid_index_bytes"] = h.grid_index_bytes();
  out["pin_index_width"] = h.pin_index_width();
  out["num_grids"] = h.num_grids();
  out["markov_model_bytes"] = h.markov_model_bytes();
  return out;
}

// Upstream label-format decision (crackle.hpp compress_helper): pins are used only when
// sz > 1, pins are allowed, the dtype is unsigned and pixel_pairs >= voxels / 2.
template <typename LABEL>
py::dict format_decision_typed(const py::array& labels, const Dims d, const bool allow_pins) {
  const LABEL* data = static_cast<const LABEL*>(labels.data());
  const int64_t voxels = static_cast<int64_t>(d.sx * d.sy * d.sz);
  int64_t pairs = 0;
  if (voxels > 0) {
    pairs = static_cast<int64_t>(crackle::lib::pixel_pairs(data, voxels));
  }
  const bool pins_possible = d.sz > 1 && allow_pins;
  py::dict out;
  out["pixel_pairs"] = pairs;
  out["voxels"] = voxels;
  out["pins_possible"] = pins_possible;
  out["label_format"] = static_cast<int>((pins_possible && pairs >= voxels / 2)
                                             ? crackle::LabelFormat::PINS_VARIABLE_WIDTH
                                             : crackle::LabelFormat::FLAT);
  out["crack_format"] = static_cast<int>((pairs >= voxels / 2) ? crackle::CrackFormat::IMPERMISSIBLE
                                                               : crackle::CrackFormat::PERMISSIBLE);
  out["max_label"] = static_cast<uint64_t>(voxels > 0 ? crackle::lib::max_label(data, voxels) : 0);
  return out;
}

py::dict format_decision(const py::array& labels, const bool allow_pins) {
  require_unsigned(labels);
  const Dims d = require_fortran_3d(labels);
  switch (labels.dtype().itemsize()) {
    case 1: return format_decision_typed<uint8_t>(labels, d, allow_pins);
    case 2: return format_decision_typed<uint16_t>(labels, d, allow_pins);
    case 4: return format_decision_typed<uint32_t>(labels, d, allow_pins);
    case 8: return format_decision_typed<uint64_t>(labels, d, allow_pins);
    default: throw std::invalid_argument("_crackle_vendor: unsupported itemsize");
  }
}

template <typename LABEL>
py::tuple connected_components_typed(const py::array& labels, const Dims d) {
  const LABEL* data = static_cast<const LABEL*>(labels.data());
  const ssize_t w = static_cast<ssize_t>(sizeof(uint32_t));
  py::array_t<uint32_t> cc({static_cast<ssize_t>(d.sx), static_cast<ssize_t>(d.sy), static_cast<ssize_t>(d.sz)},
                           {w, static_cast<ssize_t>(d.sx) * w, static_cast<ssize_t>(d.sx * d.sy) * w});
  std::vector<uint64_t> per_slice(d.sz);
  uint64_t N = 0;
  if (d.sx * d.sy * d.sz > 0) {
    py::gil_scoped_release release;
    crackle::cc3d::connected_components<LABEL, uint32_t>(data, d.sx, d.sy, d.sz, per_slice,
                                                        cc.mutable_data(), N);
  }
  return py::make_tuple(cc, per_slice, N);
}

py::tuple connected_components(const py::array& labels) {
  require_unsigned(labels);
  const Dims d = require_fortran_3d(labels);
  switch (labels.dtype().itemsize()) {
    case 1: return connected_components_typed<uint8_t>(labels, d);
    case 2: return connected_components_typed<uint16_t>(labels, d);
    case 4: return connected_components_typed<uint32_t>(labels, d);
    case 8: return connected_components_typed<uint64_t>(labels, d);
    default: throw std::invalid_argument("_crackle_vendor: unsupported itemsize");
  }
}

// Stock pin selection (crackle::pins::compute): per label, the chosen candidate pins
// after upstream greedy (+ shrink_pin_to_fit when optimize=true). Each pin carries the
// CC ids it newly covered; upstream's serializer turns short pins into CC lists.
template <typename LABEL>
py::tuple pins_compute_typed(const py::array& labels, const Dims d, const bool optimize) {
  const LABEL* data = static_cast<const LABEL*>(labels.data());
  std::unordered_map<uint64_t, std::vector<crackle::pins::CandidatePin>> all_pins;
  std::vector<uint64_t> per_slice;
  uint64_t N = 0;
  std::vector<uint32_t> crcs;
  {
    py::gil_scoped_release release;
    auto result = crackle::pins::compute<LABEL>(data, d.sx, d.sy, d.sz, optimize);
    all_pins = std::move(std::get<0>(result));
    per_slice = std::move(std::get<1>(result));
    N = std::get<2>(result);
    crcs = std::move(std::get<3>(result));
  }
  py::dict per_label;
  for (auto& [label, pins] : all_pins) {
    const ssize_t n = static_cast<ssize_t>(pins.size());
    py::array_t<uint32_t> x(n), y(n), zs(n), ze(n);
    py::array_t<uint64_t> offsets(n + 1);
    uint64_t total = 0;
    for (const auto& p : pins) total += p.ccids.size();
    py::array_t<uint32_t> ccids(static_cast<ssize_t>(total));
    auto xm = x.mutable_unchecked<1>();
    auto ym = y.mutable_unchecked<1>();
    auto zsm = zs.mutable_unchecked<1>();
    auto zem = ze.mutable_unchecked<1>();
    auto om = offsets.mutable_unchecked<1>();
    auto cm = ccids.mutable_unchecked<1>();
    uint64_t k = 0;
    om(0) = 0;
    for (ssize_t i = 0; i < n; i++) {
      const auto& p = pins[static_cast<size_t>(i)];
      xm(i) = p.x;
      ym(i) = p.y;
      zsm(i) = p.z_s;
      zem(i) = p.z_e;
      std::vector<uint32_t> sorted(p.ccids.begin(), p.ccids.end());
      std::sort(sorted.begin(), sorted.end());
      for (uint32_t c : sorted) cm(static_cast<ssize_t>(k++)) = c;
      om(i + 1) = k;
    }
    py::dict rec;
    rec["x"] = x;
    rec["y"] = y;
    rec["z_s"] = zs;
    rec["z_e"] = ze;
    rec["ccid_offsets"] = offsets;
    rec["ccids"] = ccids;
    per_label[py::int_(label)] = rec;
  }
  return py::make_tuple(per_label, per_slice, N, crcs);
}

py::tuple pins_compute(const py::array& labels, const bool optimize) {
  require_unsigned(labels);
  const Dims d = require_fortran_3d(labels);
  switch (labels.dtype().itemsize()) {
    case 1: return pins_compute_typed<uint8_t>(labels, d, optimize);
    case 2: return pins_compute_typed<uint16_t>(labels, d, optimize);
    case 4: return pins_compute_typed<uint32_t>(labels, d, optimize);
    case 8: return pins_compute_typed<uint64_t>(labels, d, optimize);
    default: throw std::invalid_argument("_crackle_vendor: unsupported itemsize");
  }
}

uint64_t background_color(const py::bytes& payload) {
  std::string_view view(payload);
  std::vector<unsigned char> copy(view.begin(), view.end());
  return crackle::labels::background_color(std::span<unsigned char>(copy.data(), copy.size()));
}

uint32_t crc32c(const py::bytes& payload) {
  const std::string_view view(payload);
  return crackle::crc::crc32c(reinterpret_cast<const uint8_t*>(view.data()), view.size());
}

uint8_t crc8(const py::bytes& payload) {
  const std::string_view view(payload);
  return crackle::crc::crc8(reinterpret_cast<const uint8_t*>(view.data()), view.size());
}

}  // namespace

// The same glue also builds the optional `_crackle_head` module (upstream HEAD, F2 re-check only).
#ifndef CRACKLE_MODULE_NAME
#define CRACKLE_MODULE_NAME _crackle_vendor
#endif
PYBIND11_MODULE(CRACKLE_MODULE_NAME, m) {
  m.doc() = "Pinned upstream Crackle (vendor build, same compiler as CAPE)";
  m.attr("VENDOR_SHA") = kVendorSha;
  m.def("compress", &compress, py::arg("labels_xyz_f"), py::arg("allow_pins") = false,
        py::arg("markov_model_order") = 0, py::arg("optimize_pins") = false,
        py::arg("auto_bgcolor") = true, py::arg("manual_bgcolor") = 0, py::arg("parallel") = 1,
        "Upstream crackle::compress on an F-contiguous (x,y,z) unsigned array.");
  m.def("decompress", &decompress, py::arg("payload"), py::arg("parallel") = 1,
        "Upstream crackle::decompress; returns an (x,y,z) array in the stream's memory order.");
  m.def("header_info", &header_info, py::arg("payload"));
  m.def("format_decision", &format_decision, py::arg("labels_xyz_f"), py::arg("allow_pins"),
        "Upstream pins/flat and crack-format decision rule, evaluated without encoding.");
  m.def("connected_components", &connected_components, py::arg("labels_xyz_f"),
        "Upstream per-slice 2D 4-connected CC labeling with global ids (uint32).");
  m.def("pins_compute", &pins_compute, py::arg("labels_xyz_f"), py::arg("optimize"),
        "Upstream stock pin selection (crackle::pins::compute).");
  m.def("background_color", &background_color, py::arg("payload"));
  m.def("crc32c", &crc32c, py::arg("payload"));
  m.def("crc8", &crc8, py::arg("payload"));
}
