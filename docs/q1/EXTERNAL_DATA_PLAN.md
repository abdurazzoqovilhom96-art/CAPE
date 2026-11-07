# External validation data plan (Q1 task v3, section 7.1)

Written on 2026-11-07, **before** any codec ran on these sources. Compression results are not used for any selection
below. Authorization: the user approved "j0126 + hemibrain" on 2026-11-07. H01/MICrONS stay unauthorized.

## Why new data is needed
| Source on disk | Role so far | Usable as an unseen test? |
|---|---|---|
| CREMI A/B/C (Drosophila FAFB, ssTEM) | v1/v2 pilot + test, v3 development | no: development |
| Crackle repo samples (`connectomics`, `ws`; origin not documented) | smoke, width, scaling, v3 development | no: development; origin unknown |
| SNEMI3D (mouse S1, Kasthuri 2015, ATUM-SEM) | v3 holdout confirm (results seen 2026-11-06) | no: seen. Reported as "previously-seen test (amended)" |

## Source 1: j0126 zebra finch Area X (Januszewski et al. 2018, Nature Methods 15:605, doi:10.1038/s41592-018-0049-4)
- Official bucket: `https://storage.googleapis.com/j0126-nature-methods-data/GgwKmcKgrcoNxJccKuGIzRnQqfit9hnfK1ctZzNbnuU/`.
  - The HF mirror `pytc/zebrafinch-j0126` carries the same ground truth. The mirror is tagged `mit`, but the mirror's
    tag is not the data licence.
- Files: the 33 dense volumetric ground-truth files `gt_z*_y*_x*.h5`. Each has a single dataset `/main` (uint64, ZYX)
  and a bounding box encoded in the name.
  - 29 files are 150³; 4 files are 128×256×256 (ZYX).
- Acquisition: serial block-face EM, 9×9×20 nm (bucket README).
  - This is a different species (songbird), lab and modality from CREMI (fly ssTEM) and SNEMI3D (mouse ATUM-SEM).
  - The 33 volumes are spatially separated regions of ONE dataset. Statistically: one acquisition, 33 clusters.
- Licence: the bucket README states none. Recorded as "not stated in the official README". Data stays local and is never
  redistributed. Only hashes and coordinates go into the paper package.
- Integrity:
  - each file's size and md5 must equal the GCS object metadata;
  - SHA-256 is logged;
  - the file list must equal the 33 names listed in the README.
- Selection: **all 33 volumes, unmodified** (no content-based selection). Label 0 is kept as an ordinary ID.
- Download size: label files only (no images), about 0.4 GB.

## Source 2: Janelia FlyEM hemibrain v1.2 segmentation (Scheffer et al. 2020, eLife 9:e57443)
- Location: `https://storage.googleapis.com/neuroglancer-janelia-flyem-hemibrain/v1.2/segmentation/`.
  - Format: neuroglancer precomputed, sharded, compressed_segmentation, uint64.
  - Read with tensorstore 0.1.86 in a separate fetch-only venv (`.venv-fetch`), so the measured environment is unchanged.
- Acquisition: FIB-SEM, 8 nm isotropic, Drosophila central brain.
  - This is a different instrument, animal and imaging method from CREMI (ssTEM FAFB).
  - Same species as CREMI: the independence claim is "independent acquisition", not "independent species".
- Labels: proofread automated segmentation (body IDs), not manual dense ground truth.
- Licence: no primary Janelia statement was found. Secondary sources say CC-BY 4.0 (Virtual Fly Brain entries for hemibrain
  v1.0.1) or ODC-BY (a third-party neuroglancer fork). Recorded as "unverified primary licence". Used locally, never
  redistributed.
- **Pre-registered cutout rule** (scale 0, 8 nm):
  1. Box shape: X×Y×Z = 512×512×256 voxels (2^26 voxels, 512 MiB as uint64).
  2. Candidate origins come from `numpy.random.default_rng(20261107)`. Each axis is drawn uniformly from the central half of
     the volume, i.e. [size/4, 3·size/4 − box], and the origin is rounded down to a multiple of 64 (the chunk size).
  3. A candidate is accepted if it does not overlap an accepted box **and** at most 50% of its voxels are label 0.
     Label 0 is computed on the downloaded box itself.
  4. Stop after 4 accepted boxes, or after 40 candidates. With fewer than 4 boxes the source is PARTIAL; with none it is
     BLOCKED.
  5. Every candidate is logged with its origin, background fraction and the reason for acceptance or rejection.
- Statistics: 4 cutouts from ONE acquisition, so they are descriptive only. CIs over repeats reflect timing variation.
- Budget rule: corrected stock runs only on volumes ≤ 2^25 voxels (the v2.1 rule). Each cutout is 2^26 voxels, so stock is
  SKIPPED_BUDGET on hemibrain, recorded with the reason.

## Roles in the Q1 experiment
- development: CREMI, Crackle samples, scaling_v21 (Eθ tuning happens only here);
- previously-seen test: SNEMI3D (32 crops; full volume + 4 subvolumes = 1 acquisition);
- new external test: j0126 (33 volumes, primary for C1) and hemibrain (4 cutouts, descriptive).
