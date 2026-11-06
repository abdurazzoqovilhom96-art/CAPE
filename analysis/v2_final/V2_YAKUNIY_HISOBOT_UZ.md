# CAPE-Pins v2 — yakuniy hisobot

Yaratildi: 2026-11-06T08:43:29.813+00:00 (avtomatik, `scripts/v2_report.py`). Barcha raqamlar run'larning xom `results.csv` / `memory.csv` fayllaridan qayta hisoblangan. v1 raqamlari faqat taqqoslash uchun keltirilgan, ular qayta o'lchanmagan (v1 run'larining audit qilingan qiymatlari).

## 0. Bosqichlar holati

| Qadam | Holat | Run | Izoh |
|---|---|---|---|
| tests | DONE | - | 1766 passed, 12 deselected in 22.47s |
| pilot | DONE | results\20261106T041741Z_pilot_ca467036 | - |
| freeze | DONE | - | analysis/v2_freeze/freeze.json, configs/test_v2_frozen.yaml |
| test | DONE | results\20261106T044558Z_all_83c337ae | - |
| width | DONE | results\20261106T062540Z_development_0227806a | - |
| ceiling | DONE | - | analysis/v2_ceiling_pilot, analysis/v2_ceiling_test |
| audit | DONE | - | analysis/v2_audit |
| report | RUNNING | - | analysis/v2_final/V2_YAKUNIY_HISOBOT_UZ.md |

- `pilot`: `results\20261106T041741Z_pilot_ca467036` — holat COMPLETE, 1860 o'lchov, OK bo'lmagan qator: 0.
- `test`: `results\20261106T044558Z_all_83c337ae` — holat COMPLETE, 6840 o'lchov, OK bo'lmagan qator: 0.
- `width`: `results\20261106T062540Z_development_0227806a` — holat COMPLETE, 240 o'lchov, OK bo'lmagan qator: 0.

**Mustaqil test oilasi: BLOCKED.** H01/MICrONS kabi boshqa acquisition yuklanmagan (foydalanuvchi qarori). `test` run'i CREMI B/C volume'larining hech qachon o'lchanmagan z 64–123 qatlamlaridagi croplarda bajarilgan: voksel kesishmasi yo'q, lekin volume'lar o'sha — bu mustaqil test EMAS, faqat volume ichida umumlashuv.

## 1. Nima qayta yaratildi (ishlaydigan kod)

- `reduction_impl: fast` (default): column-major CC zanjirlari, hash-jadval dedup, faqat erishiladigan holatlarni ko'radigan exact DP, bitta pass'li run qurish. v1 kodi `reduction_impl: legacy` sifatida saqlangan; 540 ta golden v1 bitstream bayt-bayt bir xil (`tests/test_golden_v1.py`, `tests/test_reduction_fast.py`).
- FAST / CERTIFIED: `cape_fast_*` (depth-regime qidiruvi o'chirilgan, sertifikat hisoblanmaydi) va `cape_certified_*` (FAST bilan bayt-bayt bir xil stream + barcha depth regime'lar bo'yicha cheklangan-model LB; vaqti alohida o'lchanadi).
- Tuzatilgan stock: `crackle_pins_opt_corrected_*` — upstream tanlovi/foni/serializeri, faqat F2 count kengligi tuzatilgan; stock to'g'ri ishlagan har joyda bayt-bayt bir xil. Upstream HEAD `3426263` da ham F2 tasdiqlandi.
- SAFE-ARCHIVE: `safe_archive_*` — bitta native chaqiruvda flat va CAPE-FAST stream'lari, bir xil zstd bilan o'raladi, kichigi saqlanadi (engineering baseline, hissa emas).
- Refinement: `safe_refine_e{8,24,64}_*` — `cape/refine.py`: unpin va anchor harakatlari, har biri to'liq fayl (header, indeks, CRC'lar bilan) + zstd orqali baholanadi, faqat qat'iy kichrayish qabul qilinadi, S0 self-check. Dekoder — o'zgartirilmagan stock Crackle dekoderi (encoder xotirasiga tayanmaydi).
- Testlar: 1766 passed, 12 deselected in 22.47s (+ 12/12 acceptance).

## 2. Asosiy ilmiy savol: refinement SAFE'dan qo'shimcha foyda beradimi?

SAFE+refine va SAFE-ARCHIVE bir xil zstd darajasi va Markov tartibida solishtirildi; ikkalasida ham encode vaqtiga barcha nomzodlarni yaratish va tanlash xarajati kiradi; har qator stock dekoder bilan voksel bo'yicha tekshirilgan.

**Freeze (pilotdan, testdan oldin):** byudjet e=24 — smallest budget with gain >= 0.9 x max gain (10 B). Pilot yutuqlari (bayt): {'8': 2, '24': 10, '64': 10}; ablation: {'safe_refine_unpin_e24_m0_zstd9': 10, 'safe_refine_anchor_e24_m0_zstd9': 0}.

### 2.1 Test (ko'rilmagan croplar, muzlatilgan sozlamalar)

| Yangi | Baza | n | klaster | kichik | teng | katta | tejalgan B | tejash % | nisbat 95% CI | encode vaqti x | +ms (median) | decode vaqti x |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| safe_refine_e24_m0_zstd9 | safe_archive_m0_zstd9 | 24 | 12 | 10 | 14 | 0 | 42 | 0.0132 | [0.99979, 0.99994] | 2.73 | 48.8 | 1.004 |
| safe_refine_e24_m0_zstd3 | safe_archive_m0_zstd3 | 24 | 12 | 13 | 11 | 0 | 80 | 0.0244 | [0.99961, 0.99987] | 2.54 | 41.3 | 1.002 |
| safe_refine_e24_m5_zstd9 | safe_archive_m5_zstd9 | 24 | 12 | 5 | 19 | 0 | 21 | 0.0070 | [0.99985, 0.99999] | 2.44 | 44.5 | 0.997 |
| safe_refine_e24_m5_zstd3 | safe_archive_m5_zstd3 | 24 | 12 | 10 | 14 | 0 | 162 | 0.0542 | [0.99907, 0.99976] | 2.39 | 40.4 | 1.001 |

### 2.2 Pilot ablation (CREMI A, development)

| Yangi | Baza | n | klaster | kichik | teng | katta | tejalgan B | tejash % | nisbat 95% CI | encode vaqti x | +ms (median) | decode vaqti x |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| safe_refine_e8_m0_zstd9 | safe_archive_m0_zstd9 | 12 | 6 | 1 | 11 | 0 | 2 | 0.0007 | [0.99998, 1.00000] | 3.21 | 64.3 | 1.013 |
| safe_refine_e24_m0_zstd9 | safe_archive_m0_zstd9 | 12 | 6 | 2 | 10 | 0 | 10 | 0.0037 | [0.99989, 1.00000] | 6.61 | 164.5 | 0.998 |
| safe_refine_e64_m0_zstd9 | safe_archive_m0_zstd9 | 12 | 6 | 2 | 10 | 0 | 10 | 0.0037 | [0.99989, 1.00000] | 10.65 | 330.7 | 1.004 |
| safe_refine_unpin_e24_m0_zstd9 | safe_archive_m0_zstd9 | 12 | 6 | 2 | 10 | 0 | 10 | 0.0037 | [0.99989, 1.00000] | 6.65 | 163.0 | 1.002 |
| safe_refine_anchor_e24_m0_zstd9 | safe_archive_m0_zstd9 | 12 | 6 | 0 | 12 | 0 | 0 | 0.0000 | [1.00000, 1.00000] | 1.68 | 17.0 | 1.005 |
| safe_refine_e24_m0_zstd3 | safe_archive_m0_zstd3 | 12 | 6 | 2 | 10 | 0 | 9 | 0.0033 | [0.99991, 1.00000] | 6.48 | 159.8 | 1.004 |

### 2.3 Refinement ichki statistikasi

| Usul | namuna | saqlangan format | baholashlar | unpin qabul | unpin nomzod | anchor qabul | anchor nomzod | refine ms (med) | pins stream'da tejash B |
|---|---|---|---|---|---|---|---|---|---|
| safe_archive_m0_zstd3 | 24 | {'FLAT': 9, 'PINS_VARIABLE_WIDTH': 15} | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 |
| safe_archive_m0_zstd9 | 24 | {'FLAT': 15, 'PINS_VARIABLE_WIDTH': 9} | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 |
| safe_archive_m5_zstd3 | 24 | {'FLAT': 13, 'PINS_VARIABLE_WIDTH': 11} | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 |
| safe_archive_m5_zstd9 | 24 | {'FLAT': 18, 'PINS_VARIABLE_WIDTH': 6} | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 |
| safe_refine_anchor_e24_m0_zstd9 | 12 | {'PINS_VARIABLE_WIDTH': 2, 'FLAT': 10} | 6 | 0 | 0 | 1 | 4 | 13.8 | 1 |
| safe_refine_e24_m0_zstd3 | 24 | {'FLAT': 8, 'PINS_VARIABLE_WIDTH': 16} | 568 | 210 | 2085 | 0 | 0 | 39.3 | 132 |
| safe_refine_e24_m0_zstd9 | 24 | {'FLAT': 13, 'PINS_VARIABLE_WIDTH': 11} | 568 | 206 | 2085 | 0 | 0 | 45.5 | 144 |
| safe_refine_e24_m5_zstd3 | 24 | {'FLAT': 12, 'PINS_VARIABLE_WIDTH': 12} | 570 | 340 | 2085 | 0 | 0 | 36.9 | 252 |
| safe_refine_e24_m5_zstd9 | 24 | {'FLAT': 17, 'PINS_VARIABLE_WIDTH': 7} | 570 | 219 | 2085 | 0 | 0 | 40.6 | 112 |
| safe_refine_e64_m0_zstd9 | 12 | {'PINS_VARIABLE_WIDTH': 2, 'FLAT': 10} | 539 | 33 | 497 | 0 | 0 | 327.5 | 55 |
| safe_refine_e8_m0_zstd9 | 12 | {'PINS_VARIABLE_WIDTH': 2, 'FLAT': 10} | 96 | 26 | 497 | 0 | 0 | 61.3 | 42 |
| safe_refine_unpin_e24_m0_zstd9 | 12 | {'PINS_VARIABLE_WIDTH': 2, 'FLAT': 10} | 288 | 33 | 497 | 0 | 0 | 160.1 | 55 |

Izoh: refinement faqat pins stream'ni o'zgartiradi; saqlanadigan fayl min(zstd(flat), zstd(refined pins)). Flat yutgan namunalarda pins stream'dagi tejash saqlanadigan faylga o'tmaydi.

### 2.4 SAFE-ARCHIVE va bir xil sozlamadagi flat+zstd (engineering ta'siri)

| Run | Yangi | Baza | n | klaster | kichik | teng | katta | tejalgan B | tejash % | nisbat 95% CI |
|---|---|---|---|---|---|---|---|---|---|---|
| results\20261106T041741Z_pilot_ca467036 | safe_archive_m0_zstd3 | crackle_flat_m0+zstd3 | 12 | 6 | 2 | 10 | 0 | 396 | 0.1437 | [0.99589, 1.00000] |
| results\20261106T041741Z_pilot_ca467036 | safe_archive_m0_zstd9 | crackle_flat_m0+zstd9 | 12 | 6 | 2 | 10 | 0 | 238 | 0.0878 | [0.99748, 1.00000] |
| results\20261106T044558Z_all_83c337ae | safe_archive_m0_zstd3 | crackle_flat_m0+zstd3 | 24 | 12 | 15 | 9 | 0 | 1397 | 0.4235 | [0.99437, 0.99725] |
| results\20261106T044558Z_all_83c337ae | safe_archive_m0_zstd9 | crackle_flat_m0+zstd9 | 24 | 12 | 9 | 15 | 0 | 555 | 0.1740 | [0.99721, 0.99930] |
| results\20261106T044558Z_all_83c337ae | safe_archive_m5_zstd3 | crackle_flat_m5+zstd3 | 24 | 12 | 11 | 13 | 0 | 873 | 0.2913 | [0.99538, 0.99878] |
| results\20261106T044558Z_all_83c337ae | safe_archive_m5_zstd9 | crackle_flat_m5+zstd9 | 24 | 12 | 6 | 18 | 0 | 489 | 0.1634 | [0.99715, 0.99957] |


## 3. Raw track (Crackle-v1 mos, zstd'siz)

Run: `results\20261106T044558Z_all_83c337ae`; nisbat va tezlashuv `crackle_pins_opt_corrected_m0` ga nisbatan.

| Usul | n | jami bayt | nisbat | encode ms | encode tezl. x | decode ms | peak RSS MiB (med) | max |
|---|---|---|---|---|---|---|---|---|
| cape_fast_m0 | 24 | 534485 | 0.99893 | 31.18 | 5.63 | 7.05 | 81.6 | 116.8 |
| cape_certified_m0 | 24 | 534485 | 0.99893 | 31.28 | 5.65 | 7.01 | 81.4 | 116.8 |
| cape_m0 | 24 | 534485 | 0.99893 | 30.75 | 5.66 | 6.99 | 81.6 | 116.6 |
| cape_m0_legacy | 24 | 534485 | 0.99893 | 57.61 | 3.18 | 7.04 | 87.2 | 122.6 |
| crackle_pins_opt_corrected_m0 | 24 | 535058 | 1.00000 | 165.56 | 1.00 | 6.99 | 133.5 | 244.3 |
| crackle_pins_opt_m0 | 24 | 535058 | 1.00000 | 186.29 | 0.91 | 7.05 | 137.2 | 251.1 |
| crackle_vendor_pins_opt_m0 | 24 | 535058 | 1.00000 | 169.22 | 1.00 | 5.65 | 130.1 | 240.1 |
| crackle_flat_m0 | 24 | 535558 | 1.00093 | 10.32 | 16.83 | 6.80 | 74.0 | 97.1 |
| cape_fast_m5 | 24 | 384135 | 0.71793 | 34.07 | 5.02 | 7.49 | 81.7 | 116.8 |
| crackle_pins_opt_m5 | 24 | 384708 | 0.71900 | 186.85 | 0.92 | 7.45 | 136.4 | 251.2 |
| crackle_flat_m5 | 24 | 385208 | 0.71994 | 11.41 | 14.74 | 7.40 | 74.0 | 96.6 |

### Juftliklar

| Yangi | Baza | n | klaster | kichik | teng | katta | tejalgan B | tejash % | nisbat 95% CI | encode vaqti x | +ms (median) | decode vaqti x |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_fast_m0 | crackle_pins_opt_corrected_m0 | 24 | 12 | 23 | 1 | 0 | 573 | 0.1071 | [0.99875, 0.99914] | 0.18 | -134.9 | 1.001 |
| cape_fast_m0 | crackle_pins_opt_m0 | 24 | 12 | 23 | 1 | 0 | 573 | 0.1071 | [0.99875, 0.99914] | 0.16 | -154.3 | 0.996 |
| cape_m0 | crackle_pins_opt_m0 | 24 | 12 | 23 | 1 | 0 | 573 | 0.1071 | [0.99875, 0.99914] | 0.16 | -154.4 | 0.992 |
| cape_fast_m0 | cape_m0 | 24 | 12 | 0 | 24 | 0 | 0 | 0.0000 | [1.00000, 1.00000] | 1.01 | 0.1 | 1.004 |
| cape_m0 | cape_m0_legacy | 24 | 12 | 0 | 24 | 0 | 0 | 0.0000 | [1.00000, 1.00000] | 0.56 | -26.0 | 0.994 |
| cape_certified_m0 | cape_fast_m0 | 24 | 12 | 0 | 24 | 0 | 0 | 0.0000 | [1.00000, 1.00000] | 1.00 | -0.1 | 0.999 |
| crackle_pins_opt_corrected_m0 | crackle_pins_opt_m0 | 24 | 12 | 0 | 24 | 0 | 0 | 0.0000 | [1.00000, 1.00000] | 0.91 | -10.1 | 0.995 |
| cape_fast_m0 | crackle_flat_m0 | 24 | 12 | 12 | 2 | 10 | 1073 | 0.2004 | [0.99559, 1.00047] | 2.99 | 20.9 | 1.035 |
| cape_fast_m5 | crackle_pins_opt_m5 | 24 | 12 | 23 | 1 | 0 | 573 | 0.1489 | [0.99825, 0.99881] | 0.18 | -152.9 | 1.000 |

## 4. Archive track (zstd 9)

Nisbat `crackle_flat_m0+zstd9` ga nisbatan.

| Usul | n | jami bayt | nisbat | encode ms | encode tezl. x | decode ms | peak RSS MiB (med) | max |
|---|---|---|---|---|---|---|---|---|
| safe_refine_e24_m0_zstd9 | 24 | 318450 | 0.99813 | 83.68 | 0.11 | 6.87 | 91.2 | 131.7 |
| safe_archive_m0_zstd9 | 24 | 318492 | 0.99826 | 34.88 | 0.31 | 6.89 | 81.5 | 116.7 |
| crackle_flat_m0+zstd9 | 24 | 319047 | 1.00000 | 10.75 | 1.00 | 6.87 | - | - |
| cape_fast_m0+zstd9 | 24 | 318839 | 0.99935 | 31.78 | 0.34 | 7.14 | - | - |
| cape_m0+zstd9 | 24 | 318839 | 0.99935 | 31.27 | 0.35 | 7.03 | - | - |
| crackle_pins_opt_m0+zstd9 | 24 | 319269 | 1.00070 | 181.27 | 0.06 | 7.04 | - | - |
| crackle_pins_opt_corrected_m0+zstd9 | 24 | 319269 | 1.00070 | 170.63 | 0.06 | 7.01 | - | - |
| safe_refine_e24_m5_zstd9 | 24 | 298746 | 0.93637 | 81.11 | 0.12 | 7.43 | 91.2 | 131.9 |
| safe_archive_m5_zstd9 | 24 | 298767 | 0.93644 | 36.86 | 0.28 | 7.39 | 81.6 | 116.7 |
| crackle_flat_m5+zstd9 | 24 | 299256 | 0.93797 | 11.76 | 0.90 | 7.43 | - | - |
| cape_fast_m5+zstd9 | 24 | 299288 | 0.93807 | 34.20 | 0.31 | 7.63 | - | - |

Namuna bo'yicha eng kichik fayl (Markov 0): {'safe_refine_e24_m0_zstd9': 24, 'safe_archive_m0_zstd9': 14, 'crackle_flat_m0+zstd9': 13, 'cape_fast_m0+zstd9': 1, 'cape_m0+zstd9': 1}

## 5. Scale paneli (width, ko'rilgan Crackle croplari, Z=512)

| Usul | n | jami bayt | nisbat | encode ms | encode tezl. x | decode ms | peak RSS MiB (med) | max |
|---|---|---|---|---|---|---|---|---|
| cape_fast_m0 | 4 | 8791299 | 0.99267 | 1252.43 | 29.22 | 246.58 | 698.7 | 999.1 |
| cape_certified_m0 | 4 | 8791299 | 0.99267 | 1554.42 | 23.99 | 246.53 | 701.6 | 999.2 |
| cape_m0 | 4 | 8791287 | 0.99267 | 1582.69 | 23.18 | 245.42 | 701.9 | 999.1 |
| cape_m0_legacy | 4 | 8791287 | 0.99267 | 3498.71 | 9.72 | 246.49 | 750.2 | 1069.7 |
| crackle_pins_opt_corrected_m0 | 4 | 8856190 | 1.00000 | 38069.88 | 1.00 | 255.88 | 1248.6 | 1999.8 |
| crackle_pins_opt_m0 | 4 | 8856190 | 1.00000 | 46673.51 | 0.86 | 264.84 | 1303.3 | 2078.7 |
| crackle_flat_m0 | 4 | 9903553 | 1.11826 | 329.90 | 115.36 | 143.09 | 424.6 | 554.5 |

| Yangi | Baza | n | klaster | kichik | teng | katta | tejalgan B | tejash % | nisbat 95% CI | encode vaqti x | +ms (median) | decode vaqti x |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_m0 | cape_m0_legacy | 4 | 4 | 0 | 4 | 0 | 0 | 0.0000 | [1.00000, 1.00000] | 0.42 | -1916.0 | 1.000 |
| cape_fast_m0 | cape_m0 | 4 | 4 | 0 | 3 | 1 | -12 | -0.0001 | [1.00000, 1.00000] | 0.79 | -243.4 | 1.003 |
| cape_certified_m0 | cape_fast_m0 | 4 | 4 | 0 | 4 | 0 | 0 | 0.0000 | [1.00000, 1.00000] | 1.22 | 198.7 | 0.998 |
| cape_fast_m0 | crackle_pins_opt_corrected_m0 | 4 | 4 | 4 | 0 | 0 | 64891 | 0.7327 | [0.99135, 0.99357] | 0.03 | -37236.7 | 0.978 |
| crackle_pins_opt_corrected_m0 | crackle_pins_opt_m0 | 4 | 4 | 0 | 4 | 0 | 0 | 0.0000 | [1.00000, 1.00000] | 0.86 | -8603.6 | 0.982 |
| safe_refine_e24_m0_zstd9 | safe_archive_m0_zstd9 | 4 | 4 | 4 | 0 | 0 | 438 | 0.0067 | [0.99988, 0.99999] | 3.94 | 2306.0 | 0.989 |
| safe_archive_m0_zstd9 | crackle_flat_m0+zstd9 | 4 | 4 | 4 | 0 | 0 | 386312 | 5.5755 | [0.92830, 0.95759] | 4.03 | 1050.1 | 2.407 |

## 6. v1 bilan bitstream mosligi (run'lararo)

| Usul | v1 run | n | bir xil bitstream | encode tezl. x (run'lararo) |
|---|---|---|---|---|
| cape_m0 | results/20261105T112549Z_pilot_5fc4a006 | 12 | 12 | 1.76 |
| cape_m0 | results/20261105T145305Z_development_c1d12b3e | 4 | 4 | 2.44 |
| crackle_pins_opt_m0 | results/20261105T112549Z_pilot_5fc4a006 | 12 | 12 | 1.00 |

## 7. Archive ceiling (label bo'limining siqilgan fayldagi ulushi)

- `pilot`: median ulush 17.31% (gate >= 3%: o`tdi).
- `test`: median ulush 7.48% (gate >= 3%: o`tdi).

## 8. Grafiklar

- `figures/V2_F1_refine_gain_vs_time.png` (manba: `plot_data/V2_F1_refine_gain_vs_time.csv`)
- `figures/V2_F2_archive_bytes_vs_time.png` (manba: `plot_data/V2_F2_archive_bytes_vs_time.csv`)
- `figures/V2_F3_legacy_vs_fast_encode.png` (manba: `plot_data/V2_F3_legacy_vs_fast_encode.csv`)
- `figures/V2_F4_pilot_refine_ablation.png` (manba: `plot_data/V2_F4_pilot_refine_ablation.csv`)

## 9. Javoblar

**Refinement qo'shimcha foydasi (test, Markov 0, zstd 9):** 42 B (0.0132% SAFE baytidan), 10/24 namunada kichik, 0 ta katta. Nisbat 95% CI [0.99979, 0.99994] — 1 dan past, ya`ni foyda statistik jihatdan barqaror (CI 12 klaster, 2 volume ichida shartli). Narxi: encode vaqti x2.73 (median +48.8 ms), decode x1.004.

**Yutgan va yutqazgan joylar (o'lchangan):**

- Hajm, raw: CAPE-FAST tuzatilgan stock'ga nisbatan 0.1071% tejaydi (23 kichik / 1 teng / 0 katta), encode vaqti x0.178 (1 dan kichik = tezroq).
- CAPE-FAST va flat (zstd'siz): hajm 0.2004% tejash, encode vaqti x2.99 — flat tezroq bo'lsa bu yutqazish.
- Implementatsiya: bir xil bitstream (24/24 teng bayt), v2 fast encode x0.561 (legacy vaqtiga nisbatan).
- CERTIFIED: stream bayti FAST bilan teng (24/24), vaqt ustamasi x0.997.
- Archive track (zstd 9) g'oliblari namunalar bo'yicha: {'safe_refine_e24_m0_zstd9': 24, 'safe_archive_m0_zstd9': 14, 'crackle_flat_m0+zstd9': 13, 'cape_fast_m0+zstd9': 1, 'cape_m0+zstd9': 1}.
- Peak RSS (median MiB): cape_fast_m0 82, cape_certified_m0 81, cape_m0 82, cape_m0_legacy 87, crackle_pins_opt_corrected_m0 133, crackle_pins_opt_m0 137, crackle_vendor_pins_opt_m0 130, crackle_flat_m0 74, cape_fast_m5 82, crackle_pins_opt_m5 136, crackle_flat_m5 74.

**Tajriba bilan tasdiqlangan xulosalar:** faqat yuqoridagi jadvallarda CI yoki bayt-bayt tenglik bilan ko'rsatilganlari. Ko'rilgan ma'lumotdagi (pilot, width) raqamlar development/exploratory.

**Saqlash / o'chirish / qayta ishlash (o'lchovlarga asoslangan qoida):**

- SAQLASH: `reduction_impl: fast` — baytlar bir xil, vaqt kamaygan.
- O'CHIRISH (standartda): depth-regime qidiruvi — Z=512 da FAST va to'liq qidiruv farqi -0.0001%, FAST vaqti x0.793.
- QAYTA ISHLASH yoki standartdan chiqarish: refinement — tejash 0.0132%, encode x2.73.
- O'CHIRISH yoki QAYTA LOYIHALASH: anchor harakati — testda birorta ham qabul qilinmadi.
- SAQLASH: SAFE-ARCHIVE engineering himoya sifatida (o'sha sozlamadagi flat'dan hech qachon katta emas), lekin ilmiy hissa sifatida emas.
- SAQLASH: tuzatilgan stock baseline; F2 reproducer (upstream'ga xabar berish — loyiha egasining qarori).

**Q1 uchun hali yetishmayotgan dalillar:**

- Mustaqil acquisition / volume oilasi (BLOCKED: H01/MICrONS yuklanmagan); hozirgi CI 2 volume ichida.
- Kattaroq ta'sir: label bo'limi faylning kichik qismi; crack-code (boundary) qismiga tegadigan usul yo'q.
- Entropy-aware set cover / serialization bo'yicha prior-art tekshiruvi qilinmagan.
- Linux track, ROI/random-access va GPU raqiblar bilan vazifaga mos taqqoslash yo'q.
- To'liq factorial ablation (weighted cost × reductions × solver × wrapper) yo'q.

