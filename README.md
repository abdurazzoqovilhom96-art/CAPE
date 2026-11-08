# CAPE — efficient pin selection for Crackle compression of 3D neuron segmentations

CAPE is an encoder for the **PINS label format of [Crackle](https://github.com/seung-lab/crackle)**, the lossless
codec for dense 3D segmentation labels. It writes **ordinary Crackle v1 streams**: the unmodified upstream decoder
(`pip install crackle-codec`) reads them, so files written by CAPE can be used wherever Crackle files are used.
CAPE changes only *which* pin and singleton records are written to the label section, and how fast that choice is
made; the boundary (crack-code) section is byte-identical to upstream Crackle (checked on all 69 test volumes).

*Status: research code (version 0.3.0.dev0). A manuscript — "CAPE: Efficient Pin Selection with Optimality Bounds for
Crackle Compression of 3D Neuron Segmentations" — is in preparation and has not been peer reviewed.*
O'zbekcha: [README_UZ.md](README_UZ.md).

## Use it

```python
import numpy as np, crackle
import cape.api as cape

labels = np.load("segmentation.npy")     # 2D/3D unsigned integer labels, indexed like crackle: [x, y, z]
stream = cape.compress(labels)           # bytes: a standard Crackle v1 stream
assert np.array_equal(crackle.decompress(stream), labels)      # unmodified upstream decoder

stream, info = cape.compress_with_info(labels, bounds=True)    # same bytes + a lower bound on the label section
print(info["label_bytes"], info["label_lb_bytes"], info["label_gap_pct_of_label_section"])
```

Command line (the input is a `.npy` array; `--zyx` if it is stored as `[z, y, x]`):

```
python -m cape.api labels.npy labels.ckl --bounds        # prints sizes, the bound and a lossless check as JSON
python examples/quickstart.py [labels.npy]               # CAPE vs upstream Crackle flat/pins on one volume
```

`cape.compress` runs the encoder that was evaluated in the final experiment (method `cape_q1_fast_m0`, one thread).
Two checks tie the public API to the published numbers:

* `tests/test_public_api.py` — byte identity with the evaluated method built from the frozen configs, lossless round
  trip through the upstream decoder for uint8/16/32/64 and C/Fortran order, and validity of the bound;
* `tools/verify_public_api_streams.py` — on the 69 test volumes (j0126 33, SNEMI3D 32, hemibrain 4) the API writes
  **exactly the recorded streams** of the final run (SHA-256 identical, 69/69) and every stream decodes losslessly.

## Install

Requirements: CPython 3.12, a C++20 compiler (g++), git; CMake and Ninja come from the hashed lock file.

```
# Windows (MinGW-w64 g++)                     # Linux (g++)
py -3.12 scripts\bootstrap.py                  python3.12 scripts/bootstrap.py
.venv\Scripts\python -m pytest tests -m "not acceptance"        .venv/bin/python -m pytest tests -m "not acceptance"
```

`scripts/bootstrap.py` creates `.venv`, installs `requirements.lock` with `--require-hashes`, fetches the pinned
upstream sources (`sources.lock.json`: Crackle at commit 14b39b1) and builds the native modules
(`scripts/build_native.py`).

| Platform | What was checked |
|---|---|
| Windows 11, MinGW-w64 g++ 16.2, Python 3.12 | all measurements of the paper; test suite without the acceptance tests: 2,762 passed, 7 skipped |
| Linux (Debian, g++ 14.2, Python 3.12, clean Docker container `python:3.12`) | `bootstrap.py` builds and passes `doctor`; `tests/test_public_api.py` 10/10; the API wrote the 69 recorded test streams **byte for byte** (SHA-256) and losslessly. Research test suite: 2,269 passed; 132 errors are tests that load the Windows-only frozen snapshot binaries; 36 failures (SAFE-archive/refine and forced-hash-collision debug tests) are **not yet diagnosed**. All measurements were made on Windows. |

## Results at a glance

Final run `q1_20261107T072741Z`: one machine (Windows 11, Intel i7-13700F, MinGW g++ 16.2), **one thread**, 7 timed
repeats per volume, fresh process per memory row. Per volume the median over repeats, then the geometric mean over
volumes. Memory is the encode-inclusive peak of the whole process (including the Python interpreter and the input
array), not an algorithm-only figure. All streams were decoded with the upstream decoder and compared voxel by voxel.

* **j0126** (zebra finch, 33 dense ground-truth volumes): new external test, primary evidence.
* **SNEMI3D** (mouse cortex, 32 crops): seen while developing earlier CAPE versions — supporting evidence only.
* **hemibrain v1.2** (fly, 4 cutouts of 512×512×256): descriptive; upstream `pins_opt` was not run on volumes above
  2^25 voxels (pre-registered budget rule).

**CAPE vs upstream Crackle pin encoders** — CAPE was smaller, faster *and* had a lower peak on **every** volume:

| data | CAPE vs | smaller file | faster | lower peak | size change (pooled) | speed-up (geo) | peak ratio (geo) |
|---|---|---|---|---|---|---|---|
| j0126 | upstream `pins_opt` (vendor build, unmodified) | 33/33 | 33/33 | 33/33 | −0.122% | 7.09× | 0.417 |
| j0126 | upstream `pins_opt` (PyPI crackle-codec 0.53.0) | 33/33 | 33/33 | 33/33 | −0.122% | 8.13× | 0.399 |
| j0126 | upstream `pins_fast` (PyPI) | 33/33 | 33/33 | 33/33 | −1.725% | 4.07× | 0.409 |
| SNEMI3D | upstream `pins_opt` (vendor build, unmodified) | 32/32 | 32/32 | 32/32 | −0.120% | 14.10× | 0.383 |
| SNEMI3D | upstream `pins_fast` (PyPI) | 32/32 | 32/32 | 32/32 | −1.258% | 6.78× | 0.385 |
| hemibrain | upstream `pins_fast` (PyPI) | 4/4 | 4/4 | 4/4 | −2.201% | 3.28× | 0.514 |

**The trade-off against Crackle without pins (flat)** — CAPE files are smaller, but encoding is about 2× slower:

| data | smaller file | size change (pooled) | speed-up (geo) | peak ratio (geo) |
|---|---|---|---|---|
| j0126 | 33/33 | −3.091% | 0.50× | 1.224 |
| SNEMI3D | 32/32 | −5.400% | 0.54× | 1.259 |
| hemibrain | 4/4 | −8.269% | 0.43× | 1.395 |

![Size vs encode time on j0126](maqola%20uchun/figures/F03_size_time_pareto_j0126.png)

### What CAPE speeds up, and why the label section matters

| data | label section, share of the file (CAPE) | crack-code section | encode time beyond flat: upstream `pins_opt` | upstream `pins_fast` | CAPE |
|---|---|---|---|---|---|
| j0126 | 1.8% | 96.3% | 93% | 88% | 50% |
| SNEMI3D | 2.3% | 96.0% | 96% | 92% | 46% |
| hemibrain | 6.0% | 93.8% | not run | 87% | 57% |

The label section is a few percent of the bytes, but choosing its pins is most of the encode time of the upstream pin
encoders ("time beyond flat" = 1 − T_flat / T_method, geometric means). CAPE's speed comes from its infrastructure —
connected components, runs, candidate generation and safe reductions — not from the optimizer:

| CAPE phase (share of native encode time) | boundaries | 2D components | runs | candidates | reductions | solver (greedy, exact DP, local search, bound) |
|---|---|---|---|---|---|---|
| j0126 | 30.2% | 20.2% | 10.5% | 9.7% | 24.5% | 5.6% |
| hemibrain | 21.8% | 22.9% | 6.0% | 4.4% | 32.4% | 20.4% |

A weighted greedy on the same infrastructure is about as fast (0.99× on j0126, 1.00× SNEMI3D, 0.89× hemibrain) and its
files are only 0.034–0.106% larger; the exact/local search buys that small difference.

### Optimality bounds

With `bounds=True` the encoder also computes an integer dual lower bound on the label section (pins format, the
evaluated candidate family and safe reductions; minimum over all backgrounds, count widths and depth regimes). The
stream is the same and the time ratio is 1.00 (1.004 j0126, 0.998 SNEMI3D, 1.008 hemibrain). The bound says how far
the written label section can be, at most, from the best one in that model:

| data | gap, % of the label section: median / max | same gap, % of the whole file: median / max |
|---|---|---|
| j0126 | 2.17% / 9.28% | 0.041% / 0.347% |
| SNEMI3D | 1.19% / 2.76% | 0.024% / 0.057% |
| hemibrain | 9.40% / 11.50% | 0.550% / 0.719% |

These are upper bounds on the true gap, valid only for the stated model; they say nothing about the crack-code
section or about files wrapped in zstd.

### Limitations

* One machine and one thread; other platforms and multi-threaded encoding were not benchmarked.
* The primary evidence is one new acquisition (j0126); SNEMI3D was seen before; hemibrain has 4 cutouts.
* With a zstd-3 wrapper, CAPE files were larger than upstream `pins_opt`+zstd-3 on 3/33 j0126 and 1/32 SNEMI3D volumes.
* The size gain over the upstream pin encoders is small (0.12–2.2%); the contribution is time and memory at no size
  cost, plus the bound. CAPE is not a new codec and does not change the crack-code section.

Every number above is recomputed from the raw rows by `python tools/readme_claims.py --streams`.
Full tables, figures, statistics (cluster bootstrap, Holm), audits and negative results:
[`maqola uchun/`](maqola%20uchun/) (final package, validated) and
[`maqola uchun 2/`](maqola%20uchun%202/) (a follow-up study: a column-generation prototype that did **not** pass its
pre-registered gate, and the dominance theorem showing that wider pin-candidate families cannot lower the optimum).

## Reproduce

Datasets are not redistributed. The frozen manifests in `data/manifests/` give the source URL, coordinates, license
and a voxel SHA-256 for every evaluated volume.

```
python scripts/fetch_snemi3d.py                                   # SNEMI3D (Zenodo 10.5281/zenodo.7142003)
python scripts/fetch_external_q1.py --j0126 --hemibrain           # in a fetch venv with numpy, h5py, tensorstore
python scripts/materialize_from_manifest.py data/manifests/q1_external_j0126.jsonl \
       data/manifests/q1_external_hemibrain.jsonl data/manifests/confirm_snemi3d.jsonl   # checks every voxel hash
python tools/verify_public_api_streams.py                         # API == recorded streams, lossless
python tools/q1_pipeline.py --mode render --run-id q1_20261107T072741Z --output "maqola uchun"   # needs results/
python tools/q1_pipeline.py --mode full --fresh-run               # the whole experiment (about 8–11 h, one machine)
```

On the author's machine `materialize_from_manifest.py --check-only` rebuilt all 74 volumes of these four manifests
(including the SNEMI3D scale track) with identical voxel hashes. Details, hashes of every binary and seeds:
[`maqola uchun/reproducibility/REPRODUCE.md`](maqola%20uchun/reproducibility/REPRODUCE.md).

## Repository map

| Path | Content |
|---|---|
| `cape/api.py` | public API and command line |
| `cpp/` | native encoder (runs, candidates, reductions, components, greedy, exact DP, local search, dual bound, serializer, upstream bridge) |
| `cape/` | Python pipeline: adapters for all compared codecs, runner/worker, statistics, figures |
| `configs/`, `data/manifests/` | frozen experiment configs and dataset manifests |
| `tests/` | unit, property and acceptance tests (`-m acceptance` for T1–T12) |
| `tools/` | Q1 pipeline, analysis, package generator and validators |
| `snapshots/` | frozen v2.1 and v3 binaries (Windows) used for byte-identity comparisons |
| `maqola uchun/`, `maqola uchun 2/` | generated result packages (tables, figures, raw rows, mathematics) |
| `analysis/`, `audit/`, `docs/` | earlier versions' reports, audits, design notes |

## License and citation

CAPE is released under the [BSD 3-Clause License](LICENSE). Compiled third-party headers keep their own licenses
([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)); upstream sources are fetched at pinned commits and are not part of
this repository. To cite CAPE, see [CITATION.cff](CITATION.cff).
