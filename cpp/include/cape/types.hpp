// CAPE-Pins core types (spec sections 4-13, 26).
#pragma once

#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace cape {

// crackle::lib::compute_byte_width
inline int byte_width(uint64_t x) {
  if (x <= 0xFFull) return 1;
  if (x <= 0xFFFFull) return 2;
  if (x <= 0xFFFFFFFFull) return 4;
  return 8;
}

inline uint64_t width_capacity(int width) {
  return width >= 8 ? std::numeric_limits<uint64_t>::max() : ((uint64_t{1} << (8 * width)) - 1);
}

struct Dims {
  uint64_t X = 0, Y = 0, Z = 0;
  uint64_t XY() const { return X * Y; }
  uint64_t V() const { return X * Y * Z; }
};

// Field widths of the PINS_VARIABLE_WIDTH labels section (docs/format_audit.md section 3).
struct Widths {
  int w_L = 1;  // stored label width
  int w_I = 1;  // pin start index (fixed: width(V))
  int w_G = 1;  // per-slice component count (fixed: width(X*Y))
  int w_N = 1;  // per-label pin / CC counts
  int w_D = 1;  // pin depth
  int w_C = 1;  // CC id delta
};

enum class FormatPolicy : int { SameAsStock = 0, ForcePins = 1, MinExact = 2 };
// Who chooses the records inside the pins format: CAPE, or upstream's own selection and
// serializer (crackle::pins::compute + encode_condensed_pins) for the stock_cover method.
enum class Selector : int { Cape = 0, StockGreedy = 1, StockFast = 2, StockGreedyCorrected = 3 };
enum class BackgroundPolicy : int { MinCost = 0, StockRule = 1 };
enum class DepthPolicy : int { FullWidthFirst = 0, FixedDepthWidth = 1 };
enum class CandidatePolicy : int { CompleteWindows = 0, MaximalRunsOnly = 1 };
// v2 (plan P1.2): how candidate CC chains are read. Legacy = strided z-major reads of the CC volume
// (v1, sort-based dedup); Fast = one blocked transpose (contiguous chains) + hash-table dedup.
// Both produce identical kept sets and identical bitstreams (tests/test_golden_v1.py).
enum class ReductionImpl : int { Legacy = 0, Fast = 1 };
// v2 FAST / CERTIFIED split (plan P1.3). Off: no bound is reported (the dual ascent still runs
// internally because it prunes work). Regime: LB over the regimes the stream search evaluated
// (v1 behaviour). AllRegimes: additionally a dual-only LB for every depth regime the stream
// search skipped, so a fixed-depth (FAST) stream gets a bound over all regimes without
// changing a byte of it.
enum class CertificateMode : int { Off = 0, Regime = 1, AllRegimes = 2 };

// v2.1 speed-up attribution: the v1 -> v2 implementation changes as independent switches. Every
// combination produces the identical bitstream (tests/test_impl_mask.py); only work and memory differ.
//   L (layout):    column-major chain buffer via one blocked transpose; the z-major CC volume is released
//   R (runs):      runs in one pass over that buffer (needs L; without R the two-pass v1 runs are used)
//   H (hash fn):   multiply-add chain hash instead of a mix64 per element
//   T (table):     open-addressing equal-coverage grouping instead of a full sort   [algorithmic]
//   S (sparse DP): exact DP over reachable states only (n > 12)                     [algorithmic]
enum ImplBit : int { kImplLayout = 1, kImplRuns = 2, kImplHashFn = 4, kImplTable = 8, kImplSparseDp = 16 };
constexpr int kImplAll = kImplLayout | kImplRuns | kImplHashFn | kImplTable | kImplSparseDp;

struct Options {
  int markov_model_order = 0;
  FormatPolicy format_policy = FormatPolicy::SameAsStock;
  Selector selector = Selector::Cape;
  BackgroundPolicy background_policy = BackgroundPolicy::MinCost;
  DepthPolicy depth_policy = DepthPolicy::FullWidthFirst;
  CandidatePolicy candidate_policy = CandidatePolicy::CompleteWindows;
  ReductionImpl reduction_impl = ReductionImpl::Fast;
  int impl_mask = -1;  // v2.1: -1 = derived from reduction_impl (legacy 0, fast kImplAll); else ImplBit flags
  int impl() const { return impl_mask >= 0 ? (impl_mask & kImplAll) : (reduction_impl == ReductionImpl::Fast ? kImplAll : 0); }
  int debug_hash_bits = 64;  // tests only: keep this many low hash bits (forces equal-coverage collisions)
  bool reduce_equal = true;      // ablation no_dedup
  bool reduce_subset = true;     // ablation no_dominance (with reduce_singleton)
  bool reduce_singleton = true;
  bool use_exact = true;         // ablation no_exact
  bool use_local = true;         // ablation no_local
  bool use_dual_gate = true;     // ablation no_dual_gate
  uint64_t dual_scale = uint64_t{1} << 20;
  int exact_max_cc = 20;
  uint64_t exact_max_transitions_per_component = 50'000'000ull;
  uint64_t exact_max_transitions_total = 200'000'000ull;
  uint64_t exact_memory_bytes = uint64_t{64} << 20;
  uint64_t local_checks_per_component = 10'000ull;
  uint64_t local_checks_total = 1'000'000ull;
  uint64_t subset_checks_total = 200'000'000ull;
  uint64_t memory_cap_bytes = 0;  // 0 = no cap (the worker still enforces the process cap)
  size_t parallel = 1;            // upstream crack-code threads; the CAPE solver is single-threaded
  bool collect_records = false;   // return explicit records (tests / certificates)
  CertificateMode certificate = CertificateMode::Regime;
  bool return_cc = false;         // v2 refinement: also return the CC volume (uint32, z-major)
  bool keep_alternative = false;  // v2 SAFE-ARCHIVE: also return the losing flat/pins stream (one shared boundary pass)
  int export_components_max_cc = 0;      // >0: export written components with <= this many CCs (oracle audit)
  uint64_t export_components_limit = 0;  // maximum number of exported components
};

class CapeError : public std::runtime_error {
 public:
  using std::runtime_error::runtime_error;
};
class MemoryCapExceeded : public CapeError {
 public:
  using CapeError::CapeError;
};
class UnsupportedInput : public CapeError {
 public:
  using CapeError::CapeError;
};

// Maximal same-label z-run of one column. `label` is the dense label index.
struct Run {
  uint32_t col;  // x + X*y
  uint32_t z0;
  uint32_t len;
  uint32_t label;
};

// Candidate pin: a window [run.z0 + off, run.z0 + off + len) of a run.
struct Candidate {
  uint32_t run;
  uint32_t off;
  uint32_t len;
};

enum class SolveStatus : uint8_t { Trivial = 0, LbTight = 1, ExactDp = 2, Heuristic = 3 };

}  // namespace cape
