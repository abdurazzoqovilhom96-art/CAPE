# Limitations

- **Scope of optimality**: certificates hold for the restricted model (pins format, candidate
  family, background via (8), count-unconstrained LB). They do not cover the FLAT format, other
  record encodings or coupled narrow count widths.
- **Data**: only CREMI A/B/C and the Crackle repository samples; no independent human (H01) or
  MICrONS family (not authorized). CREMI A/B/C are not independent specimens; few macroblocks give
  exploratory intervals.
- **Depth regimes**: crops with Z ≤ 256 cannot exercise the width-regime mechanism.
- **Platform**: Windows native MinGW track only; the Linux/WSL canonical track was not run.
  Timing is single-thread on one P-core of a hybrid CPU; background OS activity is not fully
  excluded; turbo frequency is not fixed.
- **Small volumes**: Crackle's per-slice z-index and CRCs dominate tiny crops; a plain zstd stream
  can be smaller (seen in the 32×32×16 acceptance fixture).
- **Comparators**: CSGV/CSGV-R depend on a Volcanite + Vulkan SDK build and CLI timing (process and
  file I/O included). The PyPI Compresso reimplementation is measured, not the original VCG code.
- **Memory**: Windows peak working set of a fresh process includes interpreter and import
  overhead; values are labelled when they are only upper bounds.
- **Upstream**: the count-width corruption is reproduced on PyPI 0.53.0 and the pinned commit;
  newer upstream versions were not audited.
