#include "cape/reductions.hpp"

#include <algorithm>
#include <chrono>
#include <numeric>

#include "cape/incidence.hpp"

namespace cape {

namespace {

using RClock = std::chrono::steady_clock;
inline uint64_t r_ns_since(RClock::time_point t0) {
  return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(RClock::now() - t0).count());
}

inline uint64_t mix64(uint64_t x) {
  x += 0x9e3779b97f4a7c15ull;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ull;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebull;
  return x ^ (x >> 31);
}

bool same_chain(const Candidate& a, const Candidate& b, const ChainAccess& ch) {
  if (a.len != b.len) return false;
  if (ch.colmajor) return std::equal(ch.chain(a), ch.chain(a) + a.len, ch.chain(b));
  for (uint32_t t = 0; t < a.len; t++) {
    if (ch.at(a, t) != ch.at(b, t)) return false;
  }
  return true;
}

}  // namespace

uint64_t chain_hash(const Candidate& c, const ChainAccess& ch) {
  uint64_t h = mix64(c.len);
  if (ch.colmajor) {
    const uint32_t* p = ch.chain(c);
    for (uint32_t t = 0; t < c.len; t++) h = mix64(h ^ (static_cast<uint64_t>(p[t]) * 0x632be59bd9b4e019ull));
    return h;
  }
  for (uint32_t t = 0; t < c.len; t++) h = mix64(h ^ (static_cast<uint64_t>(ch.at(c, t)) * 0x632be59bd9b4e019ull));
  return h;
}

uint64_t chain_hash_fast(const Candidate& c, const ChainAccess& ch) {
  uint64_t h = 0x243f6a8885a308d3ull;
  if (ch.colmajor) {
    const uint32_t* p = ch.chain(c);
    for (uint32_t t = 0; t < c.len; t++) h = (h + p[t]) * 0x9e3779b97f4a7c15ull;
  } else {
    for (uint32_t t = 0; t < c.len; t++) h = (h + ch.at(c, t)) * 0x9e3779b97f4a7c15ull;
  }
  return mix64(h ^ c.len);
}

std::vector<uint32_t> reduce(const std::vector<Candidate>& cands, const ChainAccess& ch, uint64_t N,
                             const ReductionConfig& cfg, ReductionStats& st, std::vector<uint32_t>* witness) {
  const uint32_t M = static_cast<uint32_t>(cands.size());
  st = ReductionStats{};
  st.input = M;
  if (witness) {
    witness->resize(M);
    std::iota(witness->begin(), witness->end(), 0u);
  }

  // 1. singleton dominance: c_p >= sum_{u in S_p} s_u
  auto t0 = RClock::now();
  std::vector<uint32_t> alive;
  alive.reserve(M);
  for (uint32_t i = 0; i < M; i++) {
    if (cfg.singleton && static_cast<uint64_t>(cands[i].len) * cfg.single_cost <= cfg.pin_cost) {
      if (witness) (*witness)[i] = kRemovedBySingletons;
    } else {
      alive.push_back(i);
    }
  }
  st.after_singleton = alive.size();
  st.singleton_ns = r_ns_since(t0);

  // 2. equal coverage: bucket by (hash, len), confirm exactly, keep the smallest start index
  if (cfg.equal && alive.size() > 1 && cfg.hash_grouping) {
    // v2 (plan P1.2): open-addressing table instead of a full sort. Every equivalence class keeps
    // its smallest-start member, exactly as the sort-based v1 path (the kept set, the witnesses
    // and the collision count are identical; only the work is linear instead of O(M log M)).
    const size_t n = alive.size();
    t0 = RClock::now();
    std::vector<uint64_t> hs(n);
    for (size_t k = 0; k < n; k++)
      hs[k] = (cfg.fast_hash ? chain_hash_fast(cands[alive[k]], ch) : chain_hash(cands[alive[k]], ch)) & cfg.hash_mask;
    st.equal_hash_ns = r_ns_since(t0);
    t0 = RClock::now();
    constexpr uint32_t kNone = 0xFFFFFFFFu;
    size_t cap = 16;
    while (cap < 2 * n) cap <<= 1;
    const size_t mask = cap - 1;
    std::vector<uint32_t> table(cap, kNone);                 // slot -> bucket
    std::vector<uint64_t> b_hash;                            // bucket key: (hash, len)
    std::vector<uint32_t> b_len, b_head;                     // bucket -> first class
    std::vector<uint32_t> g_rep, g_next;                     // class -> representative (position k), next class
    std::vector<uint32_t> group_of(n);
    for (size_t k = 0; k < n; k++) {
      const uint32_t i = alive[k];
      const uint64_t h = hs[k];
      const uint32_t len = cands[i].len;
      size_t slot = static_cast<size_t>(mix64(h ^ len)) & mask;
      uint32_t b = kNone;
      while (table[slot] != kNone) {
        const uint32_t bb = table[slot];
        if (b_hash[bb] == h && b_len[bb] == len) {
          b = bb;
          break;
        }
        slot = (slot + 1) & mask;
      }
      if (b == kNone) {
        b = static_cast<uint32_t>(b_hash.size());
        b_hash.push_back(h);
        b_len.push_back(len);
        b_head.push_back(static_cast<uint32_t>(g_rep.size()));
        table[slot] = b;
        group_of[k] = static_cast<uint32_t>(g_rep.size());
        g_rep.push_back(static_cast<uint32_t>(k));
        g_next.push_back(kNone);
        continue;
      }
      uint32_t found = kNone, last = kNone;
      for (uint32_t g = b_head[b]; g != kNone; g = g_next[g]) {
        if (same_chain(cands[alive[g_rep[g]]], cands[i], ch)) {
          found = g;
          break;
        }
        last = g;
      }
      if (found != kNone) {
        group_of[k] = found;
        const uint32_t r = alive[g_rep[found]];
        const uint64_t si = ch.start_index(cands[i]), sr = ch.start_index(cands[r]);
        if (si < sr || (si == sr && i < r)) g_rep[found] = static_cast<uint32_t>(k);
      } else {  // same (hash, len), different coverage: a resolved hash collision
        st.equal_hash_collisions++;
        group_of[k] = static_cast<uint32_t>(g_rep.size());
        g_next[last] = static_cast<uint32_t>(g_rep.size());
        g_rep.push_back(static_cast<uint32_t>(k));
        g_next.push_back(kNone);
      }
    }
    std::vector<uint32_t> kept;
    kept.reserve(g_rep.size());
    for (uint32_t k : g_rep) kept.push_back(alive[k]);
    if (witness) {
      for (size_t k = 0; k < n; k++) {
        const uint32_t r = alive[g_rep[group_of[k]]];
        if (alive[k] != r) (*witness)[alive[k]] = r;
      }
    }
    std::sort(kept.begin(), kept.end());
    alive.swap(kept);
    st.equal_sort_ns = r_ns_since(t0);
  } else if (cfg.equal && alive.size() > 1) {
    struct Keyed {
      uint64_t hash;
      uint32_t len;
      uint64_t start;
      uint32_t idx;
    };
    std::vector<Keyed> keyed;
    keyed.reserve(alive.size());
    t0 = RClock::now();
    for (uint32_t i : alive)
      keyed.push_back(Keyed{(cfg.fast_hash ? chain_hash_fast(cands[i], ch) : chain_hash(cands[i], ch)) & cfg.hash_mask,
                            cands[i].len, ch.start_index(cands[i]), i});
    st.equal_hash_ns = r_ns_since(t0);
    t0 = RClock::now();
    std::sort(keyed.begin(), keyed.end(), [](const Keyed& a, const Keyed& b) {
      if (a.hash != b.hash) return a.hash < b.hash;
      if (a.len != b.len) return a.len < b.len;
      if (a.start != b.start) return a.start < b.start;
      return a.idx < b.idx;
    });
    std::vector<uint32_t> kept;
    kept.reserve(alive.size());
    std::vector<uint32_t> reps;
    size_t g = 0;
    while (g < keyed.size()) {
      size_t e = g + 1;
      while (e < keyed.size() && keyed[e].hash == keyed[g].hash && keyed[e].len == keyed[g].len) e++;
      reps.clear();
      for (size_t k = g; k < e; k++) {
        const uint32_t i = keyed[k].idx;
        bool merged = false;
        for (uint32_t r : reps) {
          if (same_chain(cands[r], cands[i], ch)) {
            if (witness) (*witness)[i] = r;
            merged = true;
            break;
          }
        }
        if (!merged) {
          if (!reps.empty()) st.equal_hash_collisions++;
          reps.push_back(i);
          kept.push_back(i);
        }
      }
      g = e;
    }
    std::sort(kept.begin(), kept.end());
    alive.swap(kept);
    st.equal_sort_ns = r_ns_since(t0);
  }
  st.after_equal = alive.size();

  // 3. proper-subset dominance via the CC -> candidate incidence (no all-pairs scan)
  if (cfg.subset && alive.size() > 1) {
    t0 = RClock::now();
    const Incidence inc = build_cc_incidence(alive, cands, ch, N);
    st.subset_incidence_ns = r_ns_since(t0);
    t0 = RClock::now();
    std::vector<uint8_t> removed(alive.size(), 0);
    bool stop = false;
    for (uint32_t p = 0; p < alive.size() && !stop; p++) {
      const Candidate& cp = cands[alive[p]];
      const uint32_t u_first = ch.at(cp, 0);
      const uint32_t u_last = ch.at(cp, cp.len - 1);
      const uint32_t u = (inc.off[u_first + 1] - inc.off[u_first]) <= (inc.off[u_last + 1] - inc.off[u_last]) ? u_first
                                                                                                                 : u_last;
      const uint64_t zs_p = ch.z_start(cp);
      for (uint64_t k = inc.off[u]; k < inc.off[u + 1]; k++) {
        const uint32_t q = inc.idx[k];
        if (q == p) continue;
        if (++st.subset_checks > cfg.subset_check_budget) {
          st.subset_truncated = true;
          stop = true;
          break;
        }
        const Candidate& cq = cands[alive[q]];
        if (cq.len <= cp.len) continue;
        const uint64_t zs_q = ch.z_start(cq);
        if (zs_q > zs_p || zs_q + cq.len < zs_p + cp.len) continue;
        const uint32_t off = static_cast<uint32_t>(zs_p - zs_q);
        bool contains = true;
        if (ch.colmajor) {
          contains = std::equal(ch.chain(cp), ch.chain(cp) + cp.len, ch.chain(cq) + off);
        } else {
          for (uint32_t t = 0; t < cp.len; t++) {
            if (ch.at(cq, off + t) != ch.at(cp, t)) {
              contains = false;
              break;
            }
          }
        }
        if (contains) {
          removed[p] = 1;
          if (witness) (*witness)[alive[p]] = alive[q];
          break;
        }
      }
    }
    std::vector<uint32_t> kept;
    kept.reserve(alive.size());
    for (uint32_t p = 0; p < alive.size(); p++) {
      if (!removed[p]) kept.push_back(alive[p]);
    }
    alive.swap(kept);
    st.subset_scan_ns = r_ns_since(t0);
  }
  st.after_subset = alive.size();
  return alive;
}

}  // namespace cape
