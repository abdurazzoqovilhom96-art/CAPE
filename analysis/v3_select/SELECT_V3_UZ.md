# CAPE v3 SELECT (avtomatik, `scripts/pilot_select_v3.py`)

Faza 2; development run'lar: `{"core": "results/20261106T131304Z_development_2238806f", "scale": "results/20261106T141028Z_development_bdc5fcbd", "quality": "results/20261106T151919Z_development_31cbc70e", "tracks": "results/20261106T161236Z_development_12de6862"}`. Gate'lar `configs/v3_development.yaml` da development o'lchovlaridan OLDIN yozilgan (git commit `81069d6`). SNEMI3D ga qaralmagan.

## 1. To'g'rilik

- Byte-preserving variantlar muzlatilgan v2.1 bilan solishtirildi: 732 katak, farq: **0**.
- OK bo'lmagan kataklar: 0 (yo`q).

## 2. FAST gate (leave-one-out: hamma bitlar vs shu modulsiz; core + scale, klaster bootstrap)

| Modul | Bit | Hukm | S_T (LOO) | 95% CI | peak nisbati | >10% sekin namunalar | yolg'iz bit S_T (v3 off ga) | MEMORY profil |
|---|---|---|---|---|---|---|---|---|
| M1a | 32 | **PASS** | 1.261 | [1.236, 1.298] | 0.937 | - | 1.230 | yo`q |
| M1b | 64 | **FAIL** | 1.009 | [0.997, 1.019] | 1.000 | - | 1.012 | yo`q |
| M2 | 128 | **FAIL** | 1.002 | [0.991, 1.010] | 1.000 | - | 1.005 | yo`q |
| M5a | 256 | **FAIL_INCONCLUSIVE_AFTER_RERUN** | 1.026 | [1.020, 1.035] | 1.000 | - | NA | yo`q |
| M5b | 512 | **PASS** | 1.127 | [1.085, 1.165] | 1.000 | - | 1.103 | yo`q |

- Tanlangan FAST impl_mask: **575**; MEMORY profil mask: None.
- Hamma v3 bitlari vs muzlatilgan v2.1: S_T 1.414 [1.388, 1.432], baytlar bir xil: True, peak nisbati 0.928.
- Build drift (v3 binari, v3 bitlari o'chiq vs muzlatilgan v2.1): S_T 0.995 [0.991, 1.001].

## 3. QUALITY komponentlari (Z>256 guruhi; FAST = cape_v3_all_m0)

- Depth regimes: guruhda tejash 0.1154%, vaqt nisbati 1.599; butun panel: 0.1137%.
- M3a regime gate: baytlar bir xil True; tekshirilgan/prune qilingan regime 7/0; vaqt nisbati 0.994 -> **KEEP (output-identical, faster)**.
- M3b reduced-cost: guruhda 0.0118% (vaqt 1.028); butun panel 0.0117%; regimes ustiga 0.0118%.

| M4 nuqta | R | pool | urinish | guruh tejash % | vaqt nisbati | katta namunalar |
|---|---|---|---|---|---|---|
| cape_v3_rep_r16_p128_a1_m0 | 16 | 128 | 1 | 0.0071 | 1.038 | 0 |
| cape_v3_rep_r16_p128_a4_m0 | 16 | 128 | 4 | 0.0126 | 1.086 | 0 |
| cape_v3_rep_r16_p512_a1_m0 | 16 | 512 | 1 | 0.0071 | 1.063 | 0 |
| cape_v3_rep_r16_p512_a4_m0 | 16 | 512 | 4 | 0.0126 | 1.111 | 0 |
| cape_v3_rep_r24_p128_a1_m0 | 24 | 128 | 1 | 0.0143 | 1.066 | 0 |
| cape_v3_rep_r24_p128_a4_m0 | 24 | 128 | 4 | 0.0196 | 1.126 | 0 |
| cape_v3_rep_r24_p512_a1_m0 | 24 | 512 | 1 | 0.0143 | 1.066 | 0 |
| cape_v3_rep_r24_p512_a4_m0 | 24 | 512 | 4 | 0.0196 | 1.144 | 0 |
| cape_v3_rep_r30_p128_a1_m0 | 30 | 128 | 1 | 0.0179 | 1.081 | 0 |
| cape_v3_rep_r30_p128_a4_m0 | 30 | 128 | 4 | 0.0228 | 1.184 | 0 |
| cape_v3_rep_r30_p512_a1_m0 | 30 | 512 | 1 | 0.0179 | 1.071 | 0 |
| cape_v3_rep_r30_p512_a4_m0 | 30 | 512 | 4 | 0.0228 | 1.190 | 0 |

- M4 qarori: **grid point cape_v3_rep_r30_p128_a4_m0** (qoida: largest group raw saving among grid points within the QUALITY time gate; ties -> smaller budget (R, then pool, then attempts); none within the gate -> M4 stays experimental).
- QUALITY kompozit opsiyalari: `{"rc_fixing": true, "regime_gate": true, "repair": true, "repair_max_r": 30, "repair_max_pool": 128, "repair_attempts": 4}` (o'lchov: `configs/v3_dev_quality_check.yaml`).

## 4. QUALITY gate (faza 2: kompozit vs tanlangan FAST)

- Guruhda tejash 0.1397% (chegara >= 0.10%), vaqt nisbati 1.741 (chegara <= 1.5), butun panelda katta namuna: 0 -> **no QUALITY default: the composite stays exploratory (reported, not a v3 mode)**.

## 5. Matched solver / kafolat / arxiv / tashqi (development, 3 repeat)

| Yangi | Baza | n | tejash % | 95% CI | S_T | 95% CI | kichik/teng/katta |
|---|---|---|---|---|---|---|---|
| cape_v3_all_m0 | v3_weighted_greedy_fast_m0 | 36 | 0.0267 | [0.0203, 0.0347] | 0.998 | [0.988, 1.009] | 33/3/0 |
| cape_v3_all_m0 | v3_greedy_local_fast_m0 | 36 | 0.0040 | [0.0019, 0.0067] | 0.993 | [0.981, 1.007] | 15/21/0 |
| cape_v3_all_m0 | v3_exact_only_fast_m0 | 36 | 0.0169 | [0.0118, 0.0226] | 1.000 | [0.984, 1.018] | 27/9/0 |
| v3_greedy_local_b4_fast_m0 | v3_greedy_local_fast_m0 | 36 | 0.0000 | [0.0000, 0.0000] | 0.985 | [0.974, 0.997] | 0/36/0 |
| v3_weighted_greedy_rc_m0 | v3_weighted_greedy_fast_m0 | 36 | 0.0210 | [0.0141, 0.0288] | 0.995 | [0.983, 1.009] | 28/8/0 |
| cape_v3_rc_m0 | cape_v3_all_m0 | 36 | 0.0022 | [0.0011, 0.0033] | 1.001 | [0.989, 1.012] | 11/25/0 |
| cape_v3_all_m0 | v3_cape_noreduce_fast_m0 | 36 | 0.0109 | [0.0070, 0.0151] | 34.885 | [27.584, 43.973] | 25/11/0 |
| v3_weighted_greedy_fast_m0 | v3_weighted_greedy_noreduce_fast_m0 | 36 | 0.0005 | [0.0000, 0.0016] | 9.033 | [8.412, 9.703] | 1/35/0 |
| cape_v3_all_m0 | crackle_pins_opt_corrected_m0 | 36 | 0.0850 | [0.0677, 0.1042] | 7.847 | [7.572, 8.160] | 35/1/0 |
| cape_v3_all_m0 | crackle_flat_m0 | 36 | 0.3961 | [0.0365, 0.8343] | 0.498 | [0.484, 0.512] | 20/2/14 |
| cape_v3_all_m0 | crackle_pins_fast_m0 | 36 | 1.7104 | [1.4935, 1.9402] | 6.758 | [6.534, 6.980] | 36/0/0 |
| cape_v3_all_m0 | cape_v21_fast_m0 | 36 | 0.0000 | [0.0000, 0.0000] | 1.404 | [1.383, 1.428] | 0/36/0 |
| safe_v3_archive_m0_zstd9 | safe_stock_m0_zstd9 | 36 | 0.0419 | [0.0191, 0.0686] | 6.799 | [6.527, 7.081] | 10/26/0 |
| safe_v3_archive_m0_zstd9 | crackle_flat_m0+zstd9 | 36 | 0.1344 | [0.0465, 0.2325] | 0.429 | [0.420, 0.439] | 11/25/0 |
| safe_v3_archive_m0_zstd3 | safe_stock_m0_zstd3 | 36 | 0.0968 | [0.0521, 0.1457] | 6.756 | [6.543, 6.985] | 16/19/1 |
| cape_v3_all_m5 | cape_v21_fast_m5 | 36 | 0.0000 | [0.0000, 0.0000] | 1.347 | [1.324, 1.373] | 0/36/0 |
- v3_cape_certified_m0: UB/LB gap median 0.0198%, max 0.0786%, yaroqsiz 0.
- v3_cape_certified_rc_m0: UB/LB gap median 0.0000%, max 0.0357%, yaroqsiz 0.
- v3_weighted_greedy_certified_m0: UB/LB gap median 0.0744%, max 0.1257%, yaroqsiz 0.

Fayllar: `selected_methods.json`, `fast_gate_per_sample.csv`, `m4_grid.csv`, `tracks_pairs.csv`, `certificate_gaps_dev.csv`, `status_by_method.csv`, `quality_check_per_sample.csv`.
