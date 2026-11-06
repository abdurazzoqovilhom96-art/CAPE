// _cape_native: Python bindings of the CAPE core.
#define PYBIND11_DETAILED_ERROR_MESSAGES
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <string>

#include "cape/byte_model.hpp"
#include "cape/components.hpp"
#include "cape/dual_bound.hpp"
#include "cape/encoder.hpp"
#include "cape/exact_dp.hpp"
#include "cape/greedy.hpp"
#include "cape/local_search.hpp"
#include "cape/serializer.hpp"
#include "cape/upstream_bridge.hpp"

namespace py = pybind11;
using namespace cape;

namespace {

template <typename E>
E parse_enum(const py::handle& v, const char* key, std::initializer_list<std::pair<const char*, E>> table) {
  const std::string s = v.cast<std::string>();
  for (const auto& [name, value] : table) {
    if (s == name) return value;
  }
  throw py::value_error(std::string("invalid value '") + s + "' for CAPE option " + key);
}

Options parse_options(const py::dict& d) {
  Options o;
  for (auto item : d) {
    const std::string k = py::str(item.first);
    const py::handle v = item.second;
    if (k == "markov_model_order") o.markov_model_order = v.cast<int>();
    else if (k == "format_policy")
      o.format_policy = parse_enum<FormatPolicy>(v, "format_policy",
                                                 {{"same_as_stock", FormatPolicy::SameAsStock},
                                                  {"force_pins", FormatPolicy::ForcePins},
                                                  {"min_exact", FormatPolicy::MinExact}});
    else if (k == "selector")
      o.selector = parse_enum<Selector>(v, "selector",
                                        {{"cape", Selector::Cape},
                                         {"stock_greedy", Selector::StockGreedy},
                                         {"stock_fast", Selector::StockFast},
                                         {"stock_greedy_corrected", Selector::StockGreedyCorrected}});
    else if (k == "background_policy")
      o.background_policy = parse_enum<BackgroundPolicy>(v, "background_policy",
                                                         {{"min_current_serialized_cost", BackgroundPolicy::MinCost},
                                                          {"stock", BackgroundPolicy::StockRule}});
    else if (k == "depth_policy")
      o.depth_policy = parse_enum<DepthPolicy>(v, "depth_policy",
                                               {{"full_width_first", DepthPolicy::FullWidthFirst},
                                                {"fixed_depth_width", DepthPolicy::FixedDepthWidth}});
    else if (k == "candidate_policy")
      o.candidate_policy = parse_enum<CandidatePolicy>(v, "candidate_policy",
                                                       {{"depth_bounded_complete_windows", CandidatePolicy::CompleteWindows},
                                                        {"maximal_runs_only", CandidatePolicy::MaximalRunsOnly}});
    else if (k == "reduction_impl")
      o.reduction_impl = parse_enum<ReductionImpl>(v, "reduction_impl",
                                                   {{"legacy", ReductionImpl::Legacy},
                                                    {"fast", ReductionImpl::Fast}});
    else if (k == "debug_hash_bits") o.debug_hash_bits = v.cast<int>();
    else if (k == "impl_mask") {
      const int m = v.cast<int>();
      if (m < -1 || m > kImplAll) throw py::value_error("impl_mask must be -1 or in [0, " + std::to_string(kImplAll) + "]");
      o.impl_mask = m;
    }
    else if (k == "keep_alternative") o.keep_alternative = v.cast<bool>();
    else if (k == "return_cc") o.return_cc = v.cast<bool>();
    else if (k == "certificate")
      o.certificate = parse_enum<CertificateMode>(v, "certificate",
                                                  {{"off", CertificateMode::Off},
                                                   {"regime", CertificateMode::Regime},
                                                   {"all_regimes", CertificateMode::AllRegimes}});
    else if (k == "reduce_equal") o.reduce_equal = v.cast<bool>();
    else if (k == "reduce_subset") o.reduce_subset = v.cast<bool>();
    else if (k == "reduce_singleton") o.reduce_singleton = v.cast<bool>();
    else if (k == "use_exact") o.use_exact = v.cast<bool>();
    else if (k == "use_local") o.use_local = v.cast<bool>();
    else if (k == "use_dual_gate") o.use_dual_gate = v.cast<bool>();
    else if (k == "dual_scale") o.dual_scale = v.cast<uint64_t>();
    else if (k == "exact_max_cc") o.exact_max_cc = v.cast<int>();
    else if (k == "exact_max_transitions_per_component") o.exact_max_transitions_per_component = v.cast<uint64_t>();
    else if (k == "exact_max_transitions_total") o.exact_max_transitions_total = v.cast<uint64_t>();
    else if (k == "exact_memory_mib") o.exact_memory_bytes = v.cast<uint64_t>() << 20;
    else if (k == "local_checks_per_component") o.local_checks_per_component = v.cast<uint64_t>();
    else if (k == "local_checks_total") o.local_checks_total = v.cast<uint64_t>();
    else if (k == "subset_checks_total") o.subset_checks_total = v.cast<uint64_t>();
    else if (k == "memory_cap_bytes") o.memory_cap_bytes = v.cast<uint64_t>();
    else if (k == "parallel") o.parallel = v.cast<size_t>();
    else if (k == "collect_records") o.collect_records = v.cast<bool>();
    else if (k == "export_components_max_cc") o.export_components_max_cc = v.cast<int>();
    else if (k == "export_components_limit") o.export_components_limit = v.cast<uint64_t>();
    else throw py::value_error("unknown CAPE option: " + k);
  }
  if (o.dual_scale == 0) throw py::value_error("dual_scale must be positive");
  if (o.exact_max_cc < 0 || o.exact_max_cc > 30) throw py::value_error("exact_max_cc must be in [0, 30]");
  return o;
}

py::dict diag_to_dict(const Diagnostics& dg) {
  py::dict out;
  for (const auto& [k, v] : dg.ints) out[py::str(k)] = v;
  for (const auto& [k, v] : dg.uints) out[py::str(k)] = v;
  for (const auto& [k, v] : dg.reals) out[py::str(k)] = v;
  for (const auto& [k, v] : dg.texts) out[py::str(k)] = v;
  for (const auto& [k, v] : dg.arrays) out[py::str(k)] = v;
  return out;
}

py::list records_to_list(const std::vector<LabelRecords>& recs) {
  py::list out;
  for (const auto& r : recs) {
    py::dict d;
    d["label"] = r.label_value;
    py::list pins;
    for (const auto& p : r.pins) pins.append(py::make_tuple(p.start, p.depth));
    d["pins"] = pins;
    d["singletons"] = r.singletons;
    out.append(d);
  }
  return out;
}

template <typename LABEL>
EncodeResult encode_typed(const py::array& labels, const Dims& d, const Options& o) {
  const LABEL* data = static_cast<const LABEL*>(labels.data());
  py::gil_scoped_release release;
  return encode<LABEL>(data, d, o);
}

py::tuple py_encode(const py::array& labels, const py::dict& options) {
  if (labels.ndim() != 3) throw py::value_error("_cape_native.encode: expected a 3D array shaped (x, y, z)");
  if (!(labels.flags() & py::array::f_style)) {
    throw py::value_error("_cape_native.encode: array must be Fortran-contiguous (pass canonical_zyx.T)");
  }
  if (labels.dtype().kind() != 'u') throw py::value_error("_cape_native.encode: unsigned integer labels required");
  const Options o = parse_options(options);
  const Dims d{static_cast<uint64_t>(labels.shape(0)), static_cast<uint64_t>(labels.shape(1)),
               static_cast<uint64_t>(labels.shape(2))};
  EncodeResult r;
  switch (labels.dtype().itemsize()) {
    case 1: r = encode_typed<uint8_t>(labels, d, o); break;
    case 2: r = encode_typed<uint16_t>(labels, d, o); break;
    case 4: r = encode_typed<uint32_t>(labels, d, o); break;
    case 8: r = encode_typed<uint64_t>(labels, d, o); break;
    default: throw py::value_error("unsupported itemsize");
  }
  py::dict diag = diag_to_dict(r.diag);
  if (o.collect_records) {
    diag["records"] = records_to_list(r.records);
    diag["bgcolor"] = r.bgcolor;
    diag["components_per_grid"] = r.components_per_grid;
  }
  if (o.export_components_max_cc > 0) {
    py::list comps;
    for (const auto& e : r.components) {
      py::dict c;
      c["label_index"] = e.label_index;
      c["n"] = e.n;
      c["pin_cost"] = e.pin_cost;
      c["single_cost"] = e.single_cost;
      c["ub"] = e.ub;
      c["lb"] = e.lb;
      c["status"] = e.status;
      c["sets"] = e.sets;
      comps.append(c);
    }
    diag["components_export"] = comps;
  }
  if (o.return_cc && !r.cc.empty()) {
    py::array_t<uint32_t> cc({static_cast<py::ssize_t>(d.Z), static_cast<py::ssize_t>(d.Y), static_cast<py::ssize_t>(d.X)});
    std::copy(r.cc.begin(), r.cc.end(), cc.mutable_data());
    diag["cc_volume"] = cc;
  }
  if (o.keep_alternative && !r.alt_bytes.empty()) {
    diag["alternative_stream"] = py::bytes(reinterpret_cast<const char*>(r.alt_bytes.data()), r.alt_bytes.size());
  }
  return py::make_tuple(py::bytes(reinterpret_cast<const char*>(r.bytes.data()), r.bytes.size()), diag);
}

Widths parse_widths(const py::dict& w) {
  Widths out;
  out.w_L = w["w_L"].cast<int>();
  out.w_I = w["w_I"].cast<int>();
  out.w_G = w["w_G"].cast<int>();
  out.w_N = w["w_N"].cast<int>();
  out.w_D = w["w_D"].cast<int>();
  out.w_C = w["w_C"].cast<int>();
  return out;
}

py::bytes py_serialize(uint64_t bgcolor, const py::list& labels, const std::vector<uint64_t>& comps, const py::dict& widths) {
  std::vector<LabelRecords> recs;
  for (auto item : labels) {
    py::dict d = item.cast<py::dict>();
    LabelRecords r;
    r.label_value = d["label"].cast<uint64_t>();
    for (auto p : d["pins"].cast<py::list>()) {
      auto t = p.cast<py::tuple>();
      r.pins.push_back(PinRecord{t[0].cast<uint64_t>(), t[1].cast<uint64_t>()});
    }
    r.singletons = d["singletons"].cast<std::vector<uint32_t>>();
    recs.push_back(std::move(r));
  }
  const std::vector<uint8_t> out = serialize_pins_section(bgcolor, recs, comps, parse_widths(widths));
  return py::bytes(reinterpret_cast<const char*>(out.data()), out.size());
}

py::dict py_solve_abstract(uint32_t n, const std::vector<std::vector<uint32_t>>& sets, uint64_t pin_cost,
                           uint64_t single_cost, const py::dict& options) {
  const Options o = parse_options(options);
  const LocalModel m = make_abstract_model(n, sets, pin_cost, single_cost);
  py::dict out;
  const Selection g = greedy(m);
  out["greedy_cost"] = g.cost;
  out["greedy_pins"] = g.pins;
  out["greedy_singles"] = g.singles;
  out["greedy_is_cover"] = is_cover(m, g);
  const DualResult dr = dual_ascent(m, o.dual_scale);
  out["dual_a"] = dr.a;
  out["dual_lb"] = dr.lb;
  out["dual_feasible"] = dual_feasible(m, dr, o.dual_scale);
  DpLimits lim;
  lim.max_cc = o.exact_max_cc;
  lim.per_component = o.exact_max_transitions_per_component;
  lim.memory_bytes = o.exact_memory_bytes;
  lim.sparse_states = (o.impl() & kImplSparseDp) != 0;
  uint64_t remaining = o.exact_max_transitions_total;
  const DpResult dp = exact_dp(m, lim, remaining);
  out["dp_outcome"] = static_cast<int>(dp.outcome);
  out["dp_transitions"] = dp.transitions;
  if (dp.outcome == DpOutcome::Solved) {
    out["dp_cost"] = dp.sel.cost;
    out["dp_pins"] = dp.sel.pins;
    out["dp_singles"] = dp.sel.singles;
    out["dp_is_cover"] = is_cover(m, dp.sel);
  }
  uint64_t local_remaining = o.local_checks_total;
  LocalStats ls;
  const Selection loc = local_search(m, g, o.local_checks_per_component, local_remaining, ls);
  out["local_cost"] = loc.cost;
  out["local_is_cover"] = is_cover(m, loc);
  out["local_checks"] = ls.checks;
  return out;
}

}  // namespace

PYBIND11_MODULE(_cape_native, m) {
  m.doc() = "CAPE-Pins native core (Crackle-compatible componentwise adaptive pin encoder)";
  m.attr("UPSTREAM_SHA") = bridge::kUpstreamSha;
  m.def("crc32c", [](const py::bytes& b) {
    const std::string s = b;
    return bridge::crc32c(reinterpret_cast<const uint8_t*>(s.data()), s.size());
  }, py::arg("data"), "CRC-32C (Castagnoli) of a bytes object, the checksum Crackle streams use");
  m.def("encode", &py_encode, py::arg("labels_xyz_f"), py::arg("options") = py::dict(),
        "Encode an F-contiguous (x,y,z) unsigned label array. Returns (stream bytes, diagnostics).");
  m.def("serialize_pins_section", &py_serialize, py::arg("bgcolor"), py::arg("labels"),
        py::arg("components_per_grid"), py::arg("widths"));
  m.def("predict_label_bytes",
        [](const py::dict& w, uint64_t n_written, uint64_t num_grids, uint64_t P, uint64_t Q) {
          return predict_label_bytes(parse_widths(w), n_written, num_grids, P, Q);
        },
        py::arg("widths"), py::arg("n_written_labels"), py::arg("num_grids"), py::arg("P"), py::arg("Q"));
  m.def("solve_abstract", &py_solve_abstract, py::arg("n"), py::arg("sets"), py::arg("pin_cost"),
        py::arg("single_cost"), py::arg("options") = py::dict(),
        "Run greedy, dual, exact DP and local search on an abstract set-cover model (tests).");

  py::register_exception<MemoryCapExceeded>(m, "MemoryCapExceeded");
  py::register_exception<UnsupportedInput>(m, "UnsupportedInput");
  py::register_exception<CapeError>(m, "CapeError");
}
