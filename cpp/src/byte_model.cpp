#include "cape/byte_model.hpp"

namespace cape {

uint64_t fixed_section_bytes(const Widths& w, uint64_t num_grids) {
  return static_cast<uint64_t>(w.w_L) + 8ull + num_grids * static_cast<uint64_t>(w.w_G) + 1ull;
}

uint64_t predict_label_bytes(const Widths& w, uint64_t n_written_labels, uint64_t num_grids, uint64_t P,
                             uint64_t Q) {
  return fixed_section_bytes(w, num_grids) + n_written_labels * per_label_overhead(w) +
         P * static_cast<uint64_t>(w.w_I + w.w_D) + Q * static_cast<uint64_t>(w.w_C);
}

}  // namespace cape
