# CAPE v3: yakuniy tahlil (avtomatik, `scripts/report_v3.py`)

Yaratilgan: 2026-11-06T22:01:03+00:00. Har bir raqam xom run fayllaridan. Holdout = SNEMI3D (bitta volume, v3 freeze'dan oldin hech qachon siqilmagan). CREMI va Crackle namunalari v3 uchun development. "10/10 tahlil" = to'liq tekshiriladigan tahlil; algoritm balli yoki jurnal qabuli emas.

## 0. Nima o'zgardi (v2.1 -> v3)

- FAST: tanlangan impl_mask **575** (qabul qilingan modullar: M1a, M5b); barcha byte-preserving o'zgarishlar muzlatilgan v2.1 binari bilan baytma-bayt teng.
- MEMORY profil: None; QUALITY: no QUALITY default: the composite stays exploratory (reported, not a v3 mode).
- Sertifikat tuzatildi: fixed-depth Regime sertifikati endi w_D siqilishini ham chegaralaydi (v2.1 da 12 ta yaroqsiz qator bor edi, `analysis/v3_audit`).
- Audit: oldingi 7 da'vodan 7 tasi xom ma'lumotdan aynan qayta hisoblandi.

## 1. Asosiy oila (oldindan ro'yxatga olingan, Holm)

| ID | metric | new | base | effect | estimate | 95% CI | p | p Holm | n | clusters |
|---|---|---|---|---|---|---|---|---|---|---|
| H1 | encode time | cape_v3_fast_m0 | cape_v21_fast_m0 | S_T | 1.343 | [1.330, 1.357] | 0.0001 | 0.0003 | 32 | 16 |
| H2a | total bytes | cape_v3_fast_m0 | crackle_pins_opt_corrected_m0 | G_B % | 0.1199 | [0.1121, 0.1276] | 0.0001 | 0.0003 | 32 | 16 |
| H2b | encode time | cape_v3_fast_m0 | crackle_pins_opt_corrected_m0 | S_T | 12.902 | [11.781, 13.993] | 0.0001 | 0.0003 | 32 | 16 |

Freeze source hash bilan moslik: **True** ({"confirm_primary": "d07368c771ee3d31b8fd89b802e049b3396a7241fc0e79c7ca9964ca9a2ef294", "confirm_scale": "d07368c771ee3d31b8fd89b802e049b3396a7241fc0e79c7ca9964ca9a2ef294", "confirm_scale_stock": "d07368c771ee3d31b8fd89b802e049b3396a7241fc0e79c7ca9964ca9a2ef294"}).

## 2. SNEMI3D asosiy jadval

| method | n | bytes | /stock | bpv | enc ms | x stock | dec ms | peak MiB | statuses |
|---|---|---|---|---|---|---|---|---|---|
| blosc2_bshuffle_zstd5 | 32 | 6669421 | 4.72201 | 0.6360 | 742.7 | 14.97 | 90.1 | 69 | OK:224 |
| cape_v21_fast_m0 | 32 | 1410718 | 0.99880 | 0.1345 | 1126.9 | 9.61 | 198.2 | 63 | OK:224 |
| cape_v21_fast_m0+zstd3 | 32 | 908778 | 0.64342 | 0.0867 | 1139.8 | 9.50 | 200.0 | NA | OK:224 |
| cape_v21_fast_m0+zstd9 | 32 | 876472 | 0.62055 | 0.0836 | 1158.6 | 9.35 | 201.1 | NA | OK:224 |
| cape_v21_fast_m5 | 32 | 992201 | 0.70249 | 0.0946 | 1228.1 | 8.51 | 238.2 | 63 | OK:224 |
| cape_v3_certified_m0 | 32 | 1410718 | 0.99880 | 0.1345 | 836.4 | 12.82 | 197.2 | 57 | OK:224 |
| cape_v3_fast_m0 | 32 | 1410718 | 0.99880 | 0.1345 | 828.4 | 12.90 | 197.0 | 57 | OK:224 |
| cape_v3_fast_m0+zstd3 | 32 | 908778 | 0.64342 | 0.0867 | 842.1 | 12.71 | 199.2 | NA | OK:224 |
| cape_v3_fast_m0+zstd9 | 32 | 876472 | 0.62055 | 0.0836 | 863.4 | 12.44 | 198.7 | NA | OK:224 |
| cape_v3_fast_m5 | 32 | 992201 | 0.70249 | 0.0946 | 938.2 | 10.97 | 237.2 | 57 | OK:224 |
| compresso_native | 32 | 7417732 | 5.25182 | 0.7074 | 642.0 | 16.43 | 377.1 | 57 | OK:224 |
| compresso_native+zstd3 | 32 | 2352859 | 1.66584 | 0.2244 | 674.4 | 15.61 | 384.4 | NA | OK:224 |
| compresso_native+zstd9 | 32 | 2136589 | 1.51272 | 0.2038 | 790.9 | 13.05 | 383.9 | NA | OK:224 |
| crackle_flat_m0 | 32 | 1491247 | 1.05582 | 0.1422 | 392.8 | 25.92 | 191.6 | 46 | OK:224 |
| crackle_flat_m0+zstd3 | 32 | 939227 | 0.66498 | 0.0896 | 401.2 | 25.33 | 193.3 | NA | OK:224 |
| crackle_flat_m0+zstd9 | 32 | 903737 | 0.63985 | 0.0862 | 424.8 | 24.09 | 194.3 | NA | OK:224 |
| crackle_flat_m5 | 32 | 1072730 | 0.75950 | 0.1023 | 478.4 | 21.16 | 231.5 | 46 | OK:224 |
| crackle_flat_m5+zstd3 | 32 | 830740 | 0.58817 | 0.0792 | 485.6 | 20.81 | 233.3 | NA | OK:224 |
| crackle_flat_m5+zstd9 | 32 | 829603 | 0.58737 | 0.0791 | 492.7 | 20.48 | 232.7 | NA | OK:224 |
| crackle_pins_fast_m0 | 32 | 1428688 | 1.01152 | 0.1363 | 5507.7 | 2.03 | 199.5 | 134 | OK:224 |
| crackle_pins_fast_m0+zstd3 | 32 | 923403 | 0.65378 | 0.0881 | 5524.8 | 2.02 | 201.0 | NA | OK:224 |
| crackle_pins_fast_m0+zstd9 | 32 | 891101 | 0.63091 | 0.0850 | 5480.4 | 2.03 | 201.1 | NA | OK:224 |
| crackle_pins_opt_corrected_m0 | 32 | 1412412 |  | 0.1347 | 13838.3 |  | 196.7 | 135 | OK:224 |
| crackle_pins_opt_corrected_m0+zstd3 | 32 | 910513 | 0.64465 | 0.0868 | 13899.5 | 1.00 | 198.4 | NA | OK:224 |
| crackle_pins_opt_corrected_m0+zstd9 | 32 | 877956 | 0.62160 | 0.0837 | 13915.0 | 0.99 | 198.7 | NA | OK:224 |
| crackle_pins_opt_corrected_m5 | 32 | 993895 | 0.70369 | 0.0948 | 13917.0 | 0.98 | 237.1 | 136 | OK:224 |
| crackle_pins_opt_corrected_m5+zstd3 | 32 | 805268 | 0.57014 | 0.0768 | 13980.8 | 0.98 | 237.8 | NA | OK:224 |
| crackle_pins_opt_corrected_m5+zstd9 | 32 | 804309 | 0.56946 | 0.0767 | 13970.1 | 0.98 | 237.7 | NA | OK:224 |
| crackle_pins_opt_m0 | 32 | 1412412 | 1.00000 | 0.1347 | 15792.6 | 0.87 | 197.0 | 141 | OK:224 |
| crackle_pins_opt_m0+zstd3 | 32 | 910513 | 0.64465 | 0.0868 | 15841.7 | 0.87 | 198.1 | NA | OK:224 |
| crackle_pins_opt_m0+zstd9 | 32 | 877956 | 0.62160 | 0.0837 | 15864.1 | 0.87 | 198.2 | NA | OK:224 |
| crackle_vendor_pins_opt_m0 | 32 | 1412412 | 1.00000 | 0.1347 | 13843.0 | 1.00 | 141.8 | 132 | OK:224 |
| lzma6_raw | 32 | 2880736 | 2.03959 | 0.2747 | 10641.4 | 0.99 | 280.0 | 98 | OK:224 |
| neuroglancer_b8 | 0 |  |  |  |  |  |  |  | UNSUPPORTED_DTYPE:224 |
| neuroglancer_b8+zstd3 | 0 |  |  |  |  |  |  |  | UNSUPPORTED_DTYPE:224 |
| neuroglancer_b8+zstd9 | 0 |  |  |  |  |  |  |  | UNSUPPORTED_DTYPE:224 |
| raw | 32 | 167773312 | 118.78497 | 16.0001 | 52.3 | 199.40 | 22.7 | 46 | OK:224 |
| safe_stock_m0_zstd3 | 32 | 910513 | 0.64465 | 0.0868 | 13936.6 | 0.99 | 198.3 | 135 | OK:224 |
| safe_stock_m0_zstd9 | 32 | 877956 | 0.62160 | 0.0837 | 13981.8 | 0.98 | 198.9 | 135 | OK:224 |
| safe_v3_fast_m0_zstd3 | 32 | 908778 | 0.64342 | 0.0867 | 968.4 | 10.98 | 199.2 | 57 | OK:224 |
| safe_v3_fast_m0_zstd9 | 32 | 876472 | 0.62055 | 0.0836 | 1011.1 | 10.56 | 199.4 | 57 | OK:224 |
| v3_fast_greedy_local_m0 | 32 | 1410756 | 0.99883 | 0.1345 | 831.2 | 12.88 | 197.1 | 57 | OK:224 |
| v3_fast_weighted_greedy_certified_m0 | 32 | 1411202 | 0.99914 | 0.1346 | 828.6 | 12.91 | 197.1 | 57 | OK:224 |
| v3_fast_weighted_greedy_m0 | 32 | 1411202 | 0.99914 | 0.1346 | 831.1 | 12.89 | 197.0 | 57 | OK:224 |
| zstd9 | 32 | 3792786 | 2.68533 | 0.3617 | 642.0 | 15.83 | 88.1 | 47 | OK:224 |

## 3. Ikkilamchi taqqoslashlar

| new | base | n | saving % | 95% CI | S_T | 95% CI | S_D | s/e/l | peak | >10% slower |
|---|---|---|---|---|---|---|---|---|---|---|
| cape_v3_fast_m0 | crackle_flat_m0 | 32 | 5.4001 | [5.0453, 5.7356] | 0.498 | [0.481, 0.519] | 0.964 | 32/0/0 | 1.218 | 32 |
| cape_v3_fast_m0 | crackle_pins_opt_m0 | 32 | 0.1199 | [0.1121, 0.1276] | 14.836 | [13.591, 16.043] | 1.002 | 32/0/0 | 0.414 | 0 |
| cape_v3_fast_m0 | crackle_pins_fast_m0 | 32 | 1.2578 | [1.1986, 1.3162] | 6.358 | [6.251, 6.457] | 1.014 | 32/0/0 | 0.439 | 0 |
| cape_v3_fast_m0 | crackle_vendor_pins_opt_m0 | 32 | 0.1199 | [0.1121, 0.1276] | 12.869 | [11.811, 13.896] | 0.721 | 32/0/0 | 0.443 | 0 |
| cape_v3_fast_m0 | v3_fast_weighted_greedy_m0 | 32 | 0.0343 | [0.0296, 0.0396] | 1.001 | [0.995, 1.007] | 1.000 | 32/0/0 | 1.001 | 0 |
| cape_v3_fast_m0 | v3_fast_greedy_local_m0 | 32 | 0.0027 | [0.0019, 0.0034] | 1.002 | [0.999, 1.005] | 1.001 | 19/13/0 | 1.001 | 0 |
| safe_v3_fast_m0_zstd9 | safe_stock_m0_zstd9 | 32 | 0.1690 | [0.1597, 0.1790] | 10.729 | [9.812, 11.622] | 1.000 | 32/0/0 | 0.431 | 0 |
| safe_v3_fast_m0_zstd9 | crackle_flat_m0+zstd9 | 32 | 3.0169 | [2.8964, 3.1360] | 0.438 | [0.425, 0.455] | 0.965 | 32/0/0 | NA | 32 |
| safe_stock_m0_zstd9 | crackle_flat_m0+zstd9 | 32 | 2.8527 | [2.7309, 2.9741] | 0.041 | [0.037, 0.046] | 0.965 | 32/0/0 | NA | 32 |
| cape_v3_fast_m0+zstd9 | crackle_pins_opt_corrected_m0+zstd9 | 32 | 0.1690 | [0.1597, 0.1790] | 12.549 | [11.518, 13.558] | 1.003 | 32/0/0 | NA | 0 |
| cape_v3_fast_m0+zstd9 | crackle_flat_m0+zstd9 | 32 | 3.0169 | [2.8964, 3.1360] | 0.516 | [0.499, 0.537] | 0.968 | 32/0/0 | NA | 32 |
| safe_v3_fast_m0_zstd3 | safe_stock_m0_zstd3 | 32 | 0.1906 | [0.1586, 0.2225] | 11.134 | [10.166, 12.081] | 0.999 | 31/0/1 | 0.431 | 0 |
| cape_v3_fast_m0+zstd3 | crackle_flat_m0+zstd3 | 32 | 3.2419 | [3.1325, 3.3544] | 0.502 | [0.485, 0.523] | 0.962 | 32/0/0 | NA | 32 |
| cape_v3_fast_m5 | cape_v21_fast_m5 | 32 | 0.0000 | [0.0000, 0.0000] | 1.289 | [1.276, 1.302] | 1.003 | 0/32/0 | 0.899 | 0 |
| cape_v3_fast_m5 | crackle_pins_opt_corrected_m5 | 32 | 0.1704 | [0.1593, 0.1814] | 11.139 | [10.122, 12.121] | 1.003 | 32/0/0 | 0.431 | 0 |
| cape_v3_certified_m0 | cape_v3_fast_m0 | 32 | 0.0000 | [0.0000, 0.0000] | 0.994 | [0.991, 0.997] | 0.999 | 0/32/0 | 1.000 | 0 |

## 4. Masshtab treki (to'liq volume + kvadrantlar)

| new | base | n | saving % | 95% CI | S_T | 95% CI | S_D | s/e/l | peak | >10% slower |
|---|---|---|---|---|---|---|---|---|---|---|
| cape_v3_fast_m0 | cape_v21_fast_m0 | 5 | 0.0000 | [0.0000, 0.0000] | 1.460 | [1.413, 1.509] | 1.004 | 0/5/0 | 0.725 | 0 |
| cape_v3_fast_m0 | crackle_pins_opt_corrected_m0 | 4 | 0.0976 | [0.0889, 0.1078] | 53.962 | [43.162, 67.463] | 0.993 | 4/0/0 | 0.221 | 0 |
| cape_v3_fast_m0 | crackle_flat_m0 | 5 | 7.4023 | [4.6802, 9.1285] | 0.395 | [0.387, 0.403] | 0.989 | 5/0/0 | 1.904 | 5 |
| cape_v3_fast_m0 | v3_fast_weighted_greedy_m0 | 5 | 0.0368 | [0.0257, 0.0435] | 0.993 | [0.974, 1.010] | 0.999 | 5/0/0 | 1.000 | 0 |
| safe_v3_fast_m0_zstd9 | safe_stock_m0_zstd9 | 4 | -0.0034 | [-0.2548, 0.1751] | 44.935 | [35.972, 56.131] | 0.987 | 3/0/1 | 0.221 | 0 |

Kesishmaydigan 4 kvadrant jami (stock'ga): tejash 0.0976%, S_T 53.962; v2.1 ga S_T 1.440.

## 5. Development qarorlari

| module | verdict | LOO S_T | 95% CI | peak ratio | single bit S_T | MEMORY |
|---|---|---|---|---|---|---|
| M1a | PASS | 1.261 | [1.236, 1.298] | 0.937 | 1.230 | False |
| M1b | FAIL | 1.009 | [0.997, 1.019] | 1.000 | 1.012 | False |
| M2 | FAIL | 1.002 | [0.991, 1.010] | 1.000 | 1.005 | False |
| M5a | FAIL_INCONCLUSIVE_AFTER_RERUN | 1.026 | [1.020, 1.035] | 1.000 | NA | False |
| M5b | PASS | 1.127 | [1.085, 1.165] | 1.000 | 1.103 | False |

Batafsil: `analysis/v3_select/SELECT_V3_UZ.md`.

## 6. O'nta majburiy savol

| Savol | Holat | Javob |
|---|---|---|
| 1. To'g'rilik | **PASS** | CAPE/v3 qatorlarida FAILED_LOSSLESS: 0; v3 sertifikatlari yaroqsiz: 0; confirm run'lari freeze source hash bilan mos: True. OK bo'lmagan holatlar (barcha usullar): {'UNSUPPORTED_DTYPE': 672}. Jadval: `tables/status_by_run.csv`, `tables/certificates_confirm.csv`. |
| 2. v3 ning o'z foydasi (v2.1 ga nisbatan) | **PASS** | SNEMI3D 32 crop: S_T 1.343 [1.330, 1.357], Holm p 0.0003; baytlar bir xil: True; peak nisbati 0.897. Masshtab treki: S_T 1.460 (n=5, bitta volume). `primary_family.csv`, Fig.1. |
| 3. Tashqi raqib (tuzatilgan stock, flat) | **PASS** | Tuzatilgan stock'ga: tejash 0.1199% (CI [0.1121, 0.1276]), S_T 12.902 [11.781, 13.993]; regressiyalar (bayt): 0. Flat va boshqalar: `tables/secondary_confirm.*`. |
| 4. Algoritmik hissa (matched greedy / local) | **PASS** | Bir xil v3 infratuzilmasida CAPE vs optimallashtirilgan weighted greedy: tejash 0.0343% [0.0296, 0.0396], vaqt S_T 1.001 (<1 = CAPE sekinroq). Fig.3. |
| 5. M1-M5 hissasi | **PASS** | M1a: PASS (LOO S_T 1.261 [1.236, 1.298], peak 0.937); M1b: FAIL (LOO S_T 1.009 [0.997, 1.019], peak 1.000); M2: FAIL (LOO S_T 1.002 [0.991, 1.010], peak 1.000); M5a: FAIL_INCONCLUSIVE_AFTER_RERUN (LOO S_T 1.026 [1.020, 1.035], peak 1.000); M5b: PASS (LOO S_T 1.127 [1.085, 1.165], peak 1.000). M3a: KEEP (output-identical, faster); M4: grid point cape_v3_rep_r30_p128_a4_m0; QUALITY: no QUALITY default: the composite stays exploratory (reported, not a v3 mode). |
| 6. Kafolat | **PASS** | v3 sertifikat qatorlari: 69, yaroqsiz 0; oracle: {"components_audited": 200, "cpsat_optimal": 200, "contradictions": 0}. Doira: nomzod oilasi, xavfsiz reduksiyalar, barcha depth regime'lar, w_N>=1, barcha background'lar; global Crackle optimumi emas; zstd uchun bound yo'q. Fig.10. |
| 7. Umumlashuv | **PARTIAL** | Mustaqil manba: faqat SNEMI3D (bitta acquisition, 16 klaster). CREMI va Crackle namunalari v3 uchun development. Shuning uchun natija shu volume'ga shartli; yangi mustaqil holdout (2+ volume) kerak. H01/MICrONS ruxsatsiz. |
| 8. Masshtab va regressiyalar | **FAIL** | >10% sekin namunalar: yo`q; OK bo'lmagan holatlar: {'UNSUPPORTED_DTYPE': 672}. Masshtab treki (to'liq volume + 4 kvadrant): `tables/scale_track.*`, Fig.4, Fig.9. Stock byudjet qoidasi (v2.1, <= 2^25 voksel): snemi3d_v3_full_1024x1024x100 uchun stock SKIPPED_BUDGET (sababi `data/manifests/confirm_snemi3d_v3_scale_skipped.json`). |
| 9. Yangilik | **PARTIAL** | Hash, CSR, lazy/eager greedy, sparse DP, dual bound, reduced-cost fixing, LNS va min-selector umumiy vositalar. M2 g'oyasi Crackle issue #19 (2024-07, 2025-01 yopilgan) bilan bir xil. Yangilikka nomzod: Crackle 2D 4-bog'lanish qoidasidan kelib chiqadigan qo'shni-ustun dedup isboti (M1a) va formatga bog'langan sertifikatdagi w_D siqilish tuzatishi; prior-art auditi to'liq emas (`docs/V3_NOVELTY_MATRIX.md`). |
| 10. Reproduksiya va qaror | **PASS** | `run_v3.cmd --stage all --resume`; freeze `analysis/v3_freeze/freeze.json`; paket stage'i checksumlarni yozadi. Maqolaga: claim ledger'dagi SUPPORTED/CONDITIONAL da'volar doirasi bilan; qolganlari olib tashlanadi. |

## 7. Claim ledger

| ID | Da'vo | Track | Holat | Doira | Cheklov |
|---|---|---|---|---|---|
| L1 | v3 FAST writes byte-identical streams to the frozen v2.1 FAST on every measured input | raw | **SUPPORTED** | dev 36+25 crops, SNEMI3D 32 crops + scale track | implementation equivalence only |
| L2 | v3 FAST encodes 1.34x faster than v2.1 FAST (geo, SNEMI3D) | raw | **CONDITIONAL** | SNEMI3D one volume, 32 crops / 16 clusters, 1 CPU thread | single acquisition; Windows/MinGW i7-13700F |
| L3 | v3 FAST is 0.120% smaller than corrected stock pins | raw | **CONDITIONAL** | SNEMI3D one volume | label section only differs; boundary identical |
| L4 | v3 FAST encodes 12.90x faster than corrected stock pins | raw | **CONDITIONAL** | SNEMI3D one volume | stock = pinned upstream + count-width fix, same compiler |
| L5 | CAPE solver is smaller than an optimized weighted greedy on the same infrastructure | matched | **CONDITIONAL** | SNEMI3D one volume | gain size in table; time cost listed |
| L6 | v3 certificates are valid (LB <= written stream) incl. w_D compaction | guarantee | **SUPPORTED** | restricted model | not a global optimum; raw only |
| L7 | a QUALITY mode gives >= 0.1% raw saving within 1.5x FAST time | quality | **UNSUPPORTED** | dev Z>256 group (pre-registered) | development data only |
| L8 | the regime gate (M3a) saves time | quality | **CONDITIONAL** | dev | scaled-dual bound is weak |
| L9 | the v3 mechanisms are new algorithms | novelty | **UNSUPPORTED** | - | general tools; M2 = Crackle issue #19 idea |
| L10 | results generalize beyond the tested volumes | generalization | **UNSUPPORTED** | - | one independent acquisition |
| L11 | Q1 10/10 | - | **UNSUPPORTED** | - | never derived automatically; not claimed |
| M-M1a | M1a speeds up v3 FAST (leave-one-out S_T 1.261) | raw (dev) | **CONDITIONAL** | development crops (seen) | development only; nested scaling crops cluster by source |
| M-M1b | M1b speeds up v3 FAST (leave-one-out S_T 1.009) | raw (dev) | **UNSUPPORTED** | development crops (seen) | development only; nested scaling crops cluster by source |
| M-M2 | M2 speeds up v3 FAST (leave-one-out S_T 1.002) | raw (dev) | **UNSUPPORTED** | development crops (seen) | development only; nested scaling crops cluster by source |
| M-M5a | M5a speeds up v3 FAST (leave-one-out S_T 1.026) | raw (dev) | **UNSUPPORTED** | development crops (seen) | development only; nested scaling crops cluster by source |
| M-M5b | M5b speeds up v3 FAST (leave-one-out S_T 1.127) | raw (dev) | **CONDITIONAL** | development crops (seen) | development only; nested scaling crops cluster by source |

## 8. Grafiklar

- `figures/V3_F1_v3_vs_v21_speed.png` - OK: Fig.1 SNEMI3D confirm (1 source volume; 32 crops, 16 macroblock clusters) + scale track (5 volumes, same acquisition). Metric: median-of-repeats encode time ratio per sample. Geo S_T = 1.343 95% cluster-bootstrap CI [1.330, 1.357] (conditional on this volume).
- `figures/V3_F2_size_time_pareto.png` - OK: Fig.2 SNEMI3D confirm, 32 crops, every method incl. wrappers; raw and zstd-wrapped rows together (wrapper in the name). No CI (totals).
- `figures/V3_F3_matched_budget_quality.png` - OK: Fig.3 Matched solvers on the same v3 infrastructure (same runs, candidates, reductions, components, format rule). Dev: CREMI 36 crops, 3 repeats; confirm: SNEMI3D 32 crops. Negative = smaller than weighted greedy.
- `figures/V3_F4_memory_vs_n.png` - OK: Fig.4 Peak OS working set of one encode+decode in a fresh process (platform definition: Windows peak working set incl. the input array). Dev scale crops are nested (descriptive); confirm = SNEMI3D.
- `figures/V3_F5_stage_time.png` - OK: Fig.5 Stage times inside one encode (native timers) for the four largest dev scaling crops, frozen v2.1 vs v3 all bits. Development data (seen), descriptive.
- `figures/V3_F6_dual_pruning.png` - OK: Fig.6 M3a regime gate (base: depth regimes) and M3b reduced-cost fixing (base: FAST) on the dev QUALITY panel (Z>256 group + CREMI A, 3 repeats). Development only.
- `figures/V3_F7_fast_vs_regimes.png` - OK: Fig.7 Full depth-regime search vs FAST per dev crop (QUALITY panel). Dashed: the pre-registered 1.5x time gate. Development only.
- `figures/V3_F8_safe_archive.png` - OK: Fig.8 Archive track on SNEMI3D confirm (32 crops): SAFE-CAPE = min(zstd9(flat), zstd9(v3 FAST)); SAFE-stock = min(zstd9(flat), zstd9(corrected stock)); all headers counted.
- `figures/V3_F9_regressions.png` - OK: Fig.9 Every SNEMI3D confirm crop: ratios above the red line are regressions (listed by name in the tables).
- `figures/V3_F10_certificate_gap.png` - OK: Fig.10 Restricted-model certificate gap on SNEMI3D (candidate family, safe reductions, all depth regimes, w_N>=1, all backgrounds). CP-SAT oracle: 200 components, optimal 200, contradictions 0.

## 9. Cheklovlar (halol)

- Mustaqil holdout bitta volume (SNEMI3D); CI shu volume ichida shartli, fazoviy bog'liqlik klaster bilan to'liq yo'qolmaydi.
- Vaqtlar: bitta P-core, bitta thread, Windows/MinGW, i7-13700F; boshqa platformada farq qilishi mumkin.
- Nested scaling crop'lar tavsifiy; empirik T~V^a Big-O isboti emas.
- Sertifikat faqat cheklangan model ichida; zstd uchun bound yo'q.
- H01/MICrONS ishlatilmagan (ruxsat yo'q); tibbiy label xaritalari bu bosqichga kirmagan.
