# Data sources

| Dataset | Role | Access / authorization (2026-11-05) | License handling |
|---|---|---|---|
| Synthetic fixtures (`cape/synthetic.py`) | correctness, adversarial cases (spec §22) | generated | never in real result tables |
| Crackle repository samples (`connectomics.npy.cpso.gz` 512³ uint32, 2524 labels; `ws.npy.cpso.gz` 512³ uint64 watershed, 134 907 labels) at commit 14b39b1 | smoke / development | with the pinned source | data terms not stated → not redistributed |
| CREMI A/B/C `volumes/labels/neuron_ids` (cremi.org) | A = development, B/C = held-out compression test | download **authorized**. On 2026-11-05 the official host was unreachable (TCP 80/443 timeout); with the user's approval the files came from the Hugging Face mirror `pytc/tutorial` (`cremi/orig/sample_[ABC]_20160501.hdf`) and each matched the mirror's published LFS SHA-256: A `4c563d1b…510d`, B `887e8552…48b8`, C `2874496f…7052`. Equality with the official files could not be checked while cremi.org was down; manifests record the mirror as the source | cremi.org terms; not redistributed |
| H01 c3 segmentation | independent human test family | **not authorized** — `fetch_data.py` refuses | — |
| MICrONS static snapshot | external validation | **not authorized** | — |
| User organelle labels | sparse negative control | not provided | — |

## Crops (spec §18)
- Deterministic macroblocks: the source is tiled into non-overlapping crop-sized cells and `n`
  cells are drawn with seed 20261105 (+ a per-volume offset) **before** any codec runs; the
  coordinate table is `data/manifests/crop_table_cremi.csv`.
- Pilot crop XYZ (256,256,64); nested scale crop (128,128,64) at the same macroblock origin and
  therefore in the same split. CREMI has Z = 125, so (256,256,128), (512,512,128) and
  (512,512,256) are `NOT_APPLICABLE` (never padded).
- Every manifest row records URL, version, license, citation, HDF5 key, axes, dtype, canonical
  shape, half-open source bbox, spacing, original file SHA-256, normalized voxel SHA-256 and the
  selection rule; splits are kept per macroblock (`dataset_manifest.check_integrity`).
- CREMI "held-out" means our compression test split, not the challenge's hidden test; samples
  A/B/C are not assumed to be biologically independent specimens.
