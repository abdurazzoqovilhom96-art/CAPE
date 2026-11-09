# paper_evidence: numbers, figure data and checks behind the CAPE manuscript

This folder holds the scripts and generated evidence from which every number, table entry and figure of the CAPE
manuscript (in preparation) is computed. The manuscript text itself is not part of the repository.

Nothing here changes the evaluated encoder:
- the evaluated source is the freeze commit `0608c60` (final run `q1_20261107T072741Z`);
- the folder is outside `cape.provenance.SOURCE_GLOBS`, so the source hash is unchanged.

## Contents

| Path | Content |
|---|---|
| `scripts/compute_evidence.py` | recomputes all reported values from the raw rows of the final run (`maqola uchun/raw_results/`) and cross-checks them against `maqola uchun/supplementary/analysis.json` (geometric means within 0.2%) → `evidence/numbers.json`, `evidence/evidence_ledger.csv`, `figure_data/*.csv` |
| `scripts/exact_optimum.py` | exact optimum of the serialized PINS label section for all 69 test volumes with CP-SAT (no timing) → `evidence/exact_optimum.json`, log `evidence/logs/exact_optimum_run.txt` |
| `scripts/cluster_sensitivity.py` | j0126 bootstrap with the two spatially overlapping volume pairs merged → `evidence/cluster_sensitivity.json` |
| `scripts/test_revision_math.py` | synthetic checks T1–T6 of the serialized model against an independent CP-SAT optimum (pytest) → `evidence/logs/revision_math_tests.*`; synthetic, not biological evidence |
| `scripts/verify_crack_identity.py` | crack-code section of every CAPE stream against upstream Crackle flat encoding → `evidence/logs/crack_code_identity.txt` |
| `scripts/make_figures.py` | figures from `figure_data/` and `evidence/numbers.json` → `figures/` (not tracked) |
| `evidence/` | generated numbers, ledger, exact optima, logs of the reproducibility checks |
| `figure_data/` | per-volume data behind the figures |

## Run

Use the repository environment (`python scripts/bootstrap.py`). The commands below are run from the repository root,
with the virtual-environment Python on Windows (`.venv\Scripts\python`) or Linux (`.venv/bin/python`).

```
python paper_evidence/scripts/exact_optimum.py j0126 snemi hemibrain   # about 3 minutes
python paper_evidence/scripts/compute_evidence.py
python paper_evidence/scripts/cluster_sensitivity.py
python paper_evidence/scripts/test_revision_math.py               # writes the logs (about 10 s)
python -m pytest paper_evidence/scripts/test_revision_math.py     # the same checks as pytest tests
python paper_evidence/scripts/make_figures.py
```

Re-running these scripts on the same inputs reproduces the committed files. The only difference is the runtime field
of the synthetic-test log.

## Inputs

- **Raw rows of the final run.** `maqola uchun/raw_results/`, in this repository.
- **Materialized test volumes.** Needed by `exact_optimum.py` and `verify_crack_identity.py`: j0126, SNEMI3D and
  hemibrain, rebuilt from their public sources with `scripts/materialize_from_manifest.py` and the frozen manifests in
  `data/manifests/`. The volumes themselves are not redistributed.
- **Local run folders.** The stream-section shares and the earlier CP-SAT component audit in `compute_evidence.py`
  read the run folders under `results/`, which are not in the repository. Without them these two entries cannot be
  recomputed; everything else can.

## Notes

**Exact optimum (`exact_optimum.py`).**
- Every volume is re-encoded with the evaluated configuration and component export. The stream is checked against the
  SHA-256 recorded in the final run.
- Every exported component is solved by CP-SAT, and only `OPTIMAL` is accepted.
- CAPE's background label is proven optimal by a dual bound of that label.
- Where the optimum needs a 2-byte count width, the offending label is re-solved with both counts capped at 255. This
  uses candidates built directly from the volume: all maximal runs, without singleton dominance.
- Result: all 69 optima are exact, with `L ≤ OPT ≤ U`.

**Scope of the evidence.**
- All timings come from one machine and one thread.
- SNEMI3D was seen during earlier development; hemibrain has four volumes. Both are descriptive.
- The synthetic tests are checks of the mathematics, not measurements on biological data.
