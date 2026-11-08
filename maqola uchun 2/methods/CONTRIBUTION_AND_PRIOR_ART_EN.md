# Contribution and prior art

| Item | Status | Note |
|---|---|---|
| Dominance completeness of CompleteWindows | small theoretical element (proved, source-audited, checked T1) | closes the "wider interval family" direction |
| Exact window pricing by prefix sums | known technique | O(R) per run; checked T2 |
| Column generation for set cover (LP duality) | classical | bounded prototype only |
| Integer dual certificate | already in CAPE (cpp/src/dual_bound.cpp) | prototype uses the same scale |
| Projection-based negative/positive verdict | protocol design | favourable to CG on purpose |

Novelty would require a new theorem from the CAPE format, an implicit algorithm different from known methods, or a
proven complexity improvement. None of these is claimed.
