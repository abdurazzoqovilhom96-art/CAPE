# Related-work matrix (spec §15)

| Candidate contribution | Closest prior work | Difference | Evidence in this project | Remaining risk |
|---|---|---|---|---|
| Format-aware pin/singleton selection as weighted set cover with exact byte costs | Crackle pins (greedy max-coverage + post-hoc short-pin conversion) [S1]; classic set cover greedy [S6] | costs derived from the stream's field widths; singletons compete inside the optimization; widths compacted from explicit records | formula (3) exact on upstream streams; panel A vs `stock_cover`, `weighted_greedy` | the model itself is textbook weighted set cover — not novel by itself |
| Depth-bounded complete window family | none known for Crackle | sufficiency theorem for width-limited regimes | §2 proof; 240 + property tests | only exercised when Z > 256 (not with CREMI) |
| Safe reductions on column chains | general dominance rules in set cover | chain-specific exact checks (hash + element-wise), acyclic witnesses, dual transfer | optimum-preservation tests, forced-collision test | general ideas are known; value depends on measured reduction ratios |
| Componentwise exact refinement | exact set cover via DP/ILP | only where components are small; budgets in transitions; certificate per component | component distribution (F05), exact fractions, no-exact ablation, CP-SAT audit | real volumes may have few small components (measured, not assumed) |
| Verifiable lower bound / certificate | dual ascent for set cover | integer witness, independent verifier, scope that excludes coupled count widths | verifier tests, oracle audit (0 contradictions so far) | bound may be loose on large components |
| Count-width correctness | upstream sizes count fields before converting short pins | `w_N` from explicit `P_ℓ, Q_ℓ`; reproducer of silent upstream corruption | `test_upstream_count_width_overflow_corrupts_silently` | an upstream bug report is the owner's decision |

Comparator coverage: Crackle flat/pins (PyPI and same-compiler vendor), Compresso (S2),
Neuroglancer compressed_segmentation (S9), zstd/LZMA/Blosc2 controls; CSGV/CSGV-R (S3–S5) only
if the Volcanite build exists — otherwise the "modern comparator" claim stays blocked.
