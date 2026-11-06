# CAPE v3 AUDIT (avtomatik, `scripts/audit_v3.py`)

Yaratilgan: 2026-11-06T12:49:05+00:00. Har bir raqam `results/<run>/05_raw_metrics/run.sqlite` dagi OK qatorlardan qayta hisoblangan; hisobotlardan ko'chirilmagan.

## 1. Oldingi da'volar qayta hisoblandi

| ID | Da'vo | Manba | Qayta hisoblangan | Aytilgan | Birlik | Holat | Izoh |
|---|---|---|---|---|---|---|---|
| C1 | CREMI v2 test: CAPE-FAST smaller than corrected stock | V2_YAKUNIY_HISOBOT_UZ.md | 0.107091 | 0.1071 | % bytes | **MATCH** | n=24 smaller/equal/larger=23/1/0 |
| C2 | CREMI v2 test: CAPE-FAST encode speed-up vs corrected stock ('geometric 5.63x') | V2_YAKUNIY_HISOBOT_UZ.md (table: 'stock'dan tez x') | 5.631201 | 5.63 | x | **MATCH** | geometric over samples = 5.631; ratio of summed medians = 5.879; ratio of mean medians = 5.879. The stated 5.63 matches the geometric mean over samples |
| C3 | Refine on the v2 test: bytes saved vs SAFE | V2_YAKUNIY_HISOBOT_UZ.md | 42 | 42 | B | **MATCH** | saving 0.0132% |
| C4 | Refine on the v2 test: encode time multiplier | V2_YAKUNIY_HISOBOT_UZ.md | 2.72867 | 2.73 | x | **MATCH** | 1/geo = 2.729; sum ratio = 2.451 |
| C5 | Scaling (crops <= 2^25 voxels): CAPE-FAST smaller than corrected stock | user summary / V21_HISOBOT_UZ.md | 0.639685 | 0.64 | % bytes | **MATCH** | n=19 (seen development crops, nested) |
| C6 | Scaling: CAPE-FAST encode speed-up vs corrected stock | user summary | 5.108691 | 5.1 | x | **MATCH** | geometric; summed-median ratio 15.95 |
| C7 | Depth regimes on some Z=512 crops: full search ~0.64-0.69% smaller than FAST | user summary | 0.693731 | 0.69 | % bytes (max over Z=512 crops) | **MATCH** | scale_crackle_connectomics_128x128x512: 0.694% (time x1.50); scale_crackle_connectomics_256x256x512: 0.684% (time x1.55); scale_crackle_connectomics_512x512x512: 0.639% (time x1.68); scale_crackle_connectomics_64x64x512: 0.159% (time x1.47); scale_crackle_ws_512x512x512: 0.000% (time x1.68); crackle_connectomics_x256_y256_z0_256x256x512: 0.000% (time x1.56); crackle_ws_x0_y0_z0_256x256x512: 0.000% (time x1.61) |

## 2. Sertifikat va lossless

- Sertifikat qatorlari: 4902; yaroqsiz (`lb_bytes > ub_bytes` yoki dual feasible emas): **12**.
  - v1_width / cape_fixed_depth_width / crackle_connectomics_x256_y256_z0_256x256x512: 3 qator
  - v1_width / cape_fixed_depth_width / crackle_ws_x0_y0_z0_256x256x512: 3 qator
  - v2_width / cape_fixed_depth_width / crackle_connectomics_x256_y256_z0_256x256x512: 3 qator
  - v2_width / cape_fixed_depth_width / crackle_ws_x0_y0_z0_256x256x512: 3 qator
- FAILED_LOSSLESS qatorlari audit qilingan run'larda (run -> metod -> soni): yo`q. (Upstream F2 xatosi faqat smoke run'dagi adversarial namunada ko'rinadi; u ro'yxatdagi run'larga kirmaydi.)
- FAST qatorlarida w_D siqilishi: 4 / 29 namunada yozilgan w_D regime w_D dan kichik (sertifikat nuqsonining sababi, `wD_compaction.csv`).

## 3. Model auditi

- **byte model:** B_label = w_L + 8 + (K-1) w_L + Z w_G + 1 + 2 (K-1) w_N + P (w_I + w_D) + Q w_C; predict_label_bytes equals the serializer length on every written stream (checked inside the encoder, error otherwise)
- **selection-dependent global terms:** w_N (count width) = width of the largest per-label record count; w_D = width of the deepest chosen pin (compaction); background = argmax of the per-label cost. None of them is hidden in a constant: the LB uses w_N = 1 (valid for every count width) and min over backgrounds (formula 8)
- **w_D compaction defect (v2.1):** with a fixed depth width the stream may compact w_D below the regime width; the regime LB (pins priced w_I + w_D_regime) then does not bound the written stream. v2.1 FAST with certificate=regime reported lb_bytes > ub_bytes on such inputs (rows marked certificate_valid = False by the worker, never hidden). Fixed in v3 by adding the scaled full-width dual bound for every narrower width
- **decomposition:** components are solved independently only inside one fixed regime and one background; the background is chosen after pass 1 and written labels' U can only decrease
- **raw vs zstd:** the dual bound and every exactness statement are about the raw labels section; zstd sizes are measured, never bounded

## 4. Faktor nomlari

- Bitlar (`types.hpp`): `{"Layout": "1", "Runs": "2", "HashFn": "4", "Table": "8", "SparseDp": "16", "AdjDedup": "32", "Csr": "64", "EagerGreedy": "128", "FusedScan": "256", "BatchedCC": "512"}`
- tests/test_impl_mask.py iterates impl_mask 0..31 = the five bits L(1) R(2) H(4) T(8) S(16); depth policy D is not an impl bit
- scripts/speedup_attribution.py: 2^5 over L,H,T,S,D where L means layout+one-pass runs together (R folded into L; a separate 'FAST without R' variant is reported); D = depth regimes off (may change bytes)
- v3: A=32 C=64 G=128 F=256 B=512 (types.hpp); 1023 = every implementation bit

## 5. SNEMI3D holati va mustaqillik

- SNEMI3D ishlatilgan run'lar: yo`q -> v3 uchun hali siqilmagan: tasdiqlovchi holdout bo`la oladi.
- SNEMI3D <-> Crackle namunalari overlap tekshiruvi: **PARTIAL_CHECK**; no translated cut-out found on the shared voxel grid. Eng yaxshi moslik: {"score": 0.09621012955904007, "snemi_z": 7, "crackle": "connectomics", "crackle_z": 73}; SNEMI chegara zichligi ~0.050.
- Cheklov: translation only, same voxel grid, sampled Crackle slices; rescaled / rotated / re-segmented versions of the same tissue are NOT excluded (Crackle sample provenance is undocumented)

## 6. Inventar

- Joriy source hash: `1c7f2104dd337ac54a3b2f29a0af31db7a4f9805f4113ebd56bc4e67a5d9e2ed`; muzlatilgan v2.1 binari sha256 `39dca94b1eeb1c59c98b1dcb117e2f46c3b4ddf6b3539dd067c2a4f40a4ff2cb`, v2.1 source hash `36652d2cd1c31689d42219387a99a792e7ee9f6f3719b4f3d989b2ce992bbd61`.
- Vendor Crackle mavjud: True; tuzatilgan stock patch: cpp/src/upstream_bridge.cpp::condensed_pins_corrected (count-width fix only).
- Oracle: cape/oracle.py (CP-SAT); verifier: cape/certificate_verify.py (independent).
- To'xtagan v2.1 run: `20261106T111350Z_development_e91c32fe` - SUPERSEDED: died at 307/400 tasks, source hash changed after INIT; kept on disk, not used in any v3 table.

| run | holat | stage | config | source hash |
|---|---|---|---|---|
| 20261105T091120Z_smoke_abb0baf9 | FAILED | smoke | smoke.yaml | 2a546d14c007 |
| 20261105T093354Z_smoke_1af40c74 | COMPLETE | smoke | smoke.yaml | 526cbc0e6fb1 |
| 20261105T111651Z_pilot_34435262 | FAILED | pilot | pilot.yaml | 4a7443a44f35 |
| 20261105T112549Z_pilot_5fc4a006 | COMPLETE | pilot | pilot.yaml | d52ab63e9a9a |
| 20261105T122347Z_all_d1a76eb7 | COMPLETE | all | benchmark.yaml | d52ab63e9a9a |
| 20261105T145305Z_development_c1d12b3e | COMPLETE | development | width_sensitivity.yaml | d52ab63e9a9a |
| 20261106T041741Z_pilot_ca467036 | COMPLETE | pilot | pilot_v2.yaml | 6da737b5641a |
| 20261106T044558Z_all_83c337ae | COMPLETE | all | test_v2_frozen.yaml | d68ac322c3cf |
| 20261106T062540Z_development_0227806a | COMPLETE | development | width_v2.yaml | 608046032ac3 |
| 20261106T091815Z_development_73f40dd8 | COMPLETE | development | scaling_v21.yaml | 540a95bc5709 |
| 20261106T100701Z_development_9be56574 | COMPLETE | development | scaling_v21_stock.yaml | 540a95bc5709 |
| 20261106T110439Z_development_8fdf0a60 | COMPLETE | development | equal_infra_test_v21.yaml | 602ba41d6c5e |
| 20261106T111350Z_development_e91c32fe | RUNNING | development | equal_infra_scaling_v21.yaml | ee0bb3b46cbe |

Fayllar: `audit_v3.json`, `claims_recheck.csv`, `certificate_rows.csv`, `wD_compaction.csv`, `data_audit.csv`, `proof_test_matrix.csv`.
