# CAPE-Pins v2.1 hisobot: Z=512, tezlashuv sabablari, masshtab, to'liq vaqtlar, SNEMI3D

Bu hisobot avtomatik yaratilgan (`scripts/v21_report.py`). Har bir raqam xom run fayllaridan qayta hisoblangan. v2.1 da **yangi mexanizm qo'shilmagan**: faqat o'lchovlar va tayyorgarlik. Refinement **EKSPERIMENTAL** rejimda (standart pipeline'da yo'q).

## 0. Qadamlar holati

| Qadam | Holat | Izoh |
|---|---|---|
| check_v2 | DONE | v2 width run results\20261106T062540Z_development_0227806a |
| build | DONE | build/native_build.json |
| tests | DONE | 1841 passed, 12 deselected in 33.13s |
| snemi_prepare | DONE | data/manifests/confirm_snemi3d.jsonl (frozen; no compression run on it) |
| attribution | DONE | analysis/v21_speedup |
| scaling_prep | DONE | data/manifests/scaling_v21*.jsonl |
| scaling | DONE | results\20261106T091815Z_development_73f40dd8 |
| scaling_stock | DONE | results\20261106T100701Z_development_9be56574 |
| audit | DONE | analysis/v21_audit |
| report | DONE (shu fayl) | analysis/v21_final/V21_HISOBOT_UZ.md |

## 1. Z=512 (width) sinovi

Run: `results\20261106T062540Z_development_0227806a` - holat **COMPLETE**, OK bo'lmagan qatorlar: 0 / 240. Ma'lumot: 4 ta ko'rilgan Crackle crop (2 ta Z=512), 2 manba fayl - **tadqiqot (exploratory)**, CI yo'q.
### Raw stream (nisbat = tuzatilgan stock'ga nisbatan)
| Usul | n | jami bayt | nisbat | encode ms | stock'dan tez x | decode ms | peak RSS MiB |
|---|---|---|---|---|---|---|---|
| cape_fast_m0 | 4 | 8791299 | 0.99267 | 1252.4 | 29.22 | 246.6 | 698.7 |
| cape_certified_m0 | 4 | 8791299 | 0.99267 | 1554.4 | 23.99 | 246.5 | 701.6 |
| cape_m0 | 4 | 8791287 | 0.99267 | 1582.7 | 23.18 | 245.4 | 701.9 |
| cape_m0_legacy | 4 | 8791287 | 0.99267 | 3498.7 | 9.72 | 246.5 | 750.2 |
| crackle_pins_opt_corrected_m0 | 4 | 8856190 | 1.00000 | 38069.9 | 1.00 | 255.9 | 1248.6 |
| crackle_pins_opt_m0 | 4 | 8856190 | 1.00000 | 46673.5 | 0.86 | 264.8 | 1303.3 |
| crackle_flat_m0 | 4 | 9903553 | 1.11826 | 329.9 | 115.36 | 143.1 | 424.6 |

### Arxiv (nisbat = flat + zstd9 ga nisbatan)
| Usul | n | jami bayt | nisbat | encode ms | decode ms | peak RSS MiB |
|---|---|---|---|---|---|---|
| cape_fast_m0+zstd9 | 4 | 6542468 | 0.94425 | 1300.1 | 248.2 | - |
| crackle_flat_m0+zstd9 | 4 | 6928780 | 1.00000 | 358.0 | 145.8 | - |
| crackle_pins_opt_corrected_m0+zstd9 | 4 | 6574894 | 0.94893 | 38066.2 | 258.6 | - |
| safe_archive_m0_zstd9 | 4 | 6542468 | 0.94425 | 1434.3 | 253.6 | 700.3 |
| safe_refine_e24_m0_zstd9 | 4 | 6542030 | 0.94418 | 3833.5 | 247.7 | 828.7 |

### Juft taqqoslashlar
| Yangi | Baza | n | kichik | teng | katta | tejalgan B | tejash % | encode vaqti x | +ms |
|---|---|---|---|---|---|---|---|---|---|
| cape_fast_m0 | crackle_pins_opt_corrected_m0 | 4 | 4 | 0 | 0 | 64891 | 0.7327 | 0.034 | -37236.7 |
| cape_fast_m0 | cape_m0 | 4 | 0 | 3 | 1 | -12 | -0.0001 | 0.793 | -243.4 |
| cape_m0 | cape_m0_legacy | 4 | 0 | 4 | 0 | 0 | 0.0000 | 0.419 | -1916.0 |
| cape_certified_m0 | cape_fast_m0 | 4 | 0 | 4 | 0 | 0 | 0.0000 | 1.218 | 198.7 |
| safe_archive_m0_zstd9 | crackle_flat_m0+zstd9 | 4 | 4 | 0 | 0 | 386312 | 5.5755 | 4.035 | 1050.1 |
| safe_refine_e24_m0_zstd9 | safe_archive_m0_zstd9 | 4 | 4 | 0 | 0 | 438 | 0.0067 | 3.944 | 2306.0 |

### Namunalar bo'yicha (bayt va encode soniya)
| sample | FAST_B | FAST_s | regimes_B | regimes_s | v1_B | v1_s | stock_c_B | stock_c_s |
|---|---|---|---|---|---|---|---|---|
| connectomics_x0_y0_z256_512x512x256 | 2385348 | 1.923 | 2385348 | 1.882 | 2385348 | 3.759 | 2405459 | 217.354 |
| connectomics_x0_y0_z384_512x512x128 | 1128156 | 0.843 | 1128156 | 0.869 | 1128156 | 1.716 | 1136904 | 39.258 |
| connectomics_x256_y256_z0_256x256x512 | 1071856 | 0.823 | 1071856 | 1.284 | 1071856 | 3.238 | 1081581 | 36.882 |
| ws_x0_y0_z0_256x256x512 | 4205939 | 1.662 | 4205927 | 2.670 | 4205927 | 8.674 | 4232246 | 5.142 |

## 2. v1 → v2 tezlashuvi: bosqichlar va alohida o'zgarishlar

v2 da **yangi qisqartirish qoidasi yo'q** (singleton / equal / subset v1 bilan bir xil). O'zgarishlar: L = column-major joylashuv + bir pass'li runs, H = arzon hash (ikkalasi **kod optimallashtirish**); T = hash-jadval guruhlash, S = erishiladigan holatli DP (ikkalasi **algoritmik**, natija bir xil); D = depth regime'larni o'chirish (**qidiruv fazosi / FAST qarori**, bayt o'zgarishi mumkin).

Namunalar: 16 (development: CREMI A pilot + Crackle width). Har kombinatsiya baytlari mos: **True** (nomuvofiq: 0); decode voksel bo'yicha aniq: **True**. Shapley qoldig'i max |1.11e-16|.

### Shapley: v1 legacy → v2 FAST tezlashuvining omillarga bo'linishi (geo-o'rtacha)
| Guruh | Omil | O'zgarish | Sinf | tezlashuv x | ulush % | 95% CI (x) | n | klaster |
|---|---|---|---|---|---|---|---|---|
| crackle_samples | L | column-major layout + one-pass runs | code | 1.437 | 32.4 | [1.284, 1.631] | 4 | 4 |
| crackle_samples | H | multiply-add chain hash | code | 1.044 | 3.9 | [1.023, 1.059] | 4 | 4 |
| crackle_samples | T | hash-table equal-coverage grouping | algorithmic | 1.295 | 23.1 | [1.264, 1.327] | 4 | 4 |
| crackle_samples | S | reachable-state exact DP | algorithmic | 1.193 | 15.8 | [1.027, 1.602] | 4 | 4 |
| crackle_samples | D | depth regimes off (FAST) | search_space | 1.320 | 24.8 | [1.000, 1.742] | 4 | 4 |
| crackle_samples | total | v1 -> v2 FAST | total | 3.059 | 100.0 | [2.037, 4.592] | 4 | 4 |
| cremi_A | L | column-major layout + one-pass runs | code | 1.249 | 39.4 | [1.237, 1.261] | 12 | 6 |
| cremi_A | H | multiply-add chain hash | code | 1.095 | 16.1 | [1.090, 1.101] | 12 | 6 |
| cremi_A | T | hash-table equal-coverage grouping | algorithmic | 1.235 | 37.4 | [1.214, 1.259] | 12 | 6 |
| cremi_A | S | reachable-state exact DP | algorithmic | 1.038 | 6.6 | [0.999, 1.109] | 12 | 6 |
| cremi_A | D | depth regimes off (FAST) | search_space | 1.003 | 0.5 | [0.998, 1.008] | 12 | 6 |
| cremi_A | total | v1 -> v2 FAST | total | 1.759 | 100.0 | [1.671, 1.864] | 12 | 6 |

### Sinflar bo'yicha: kod optimallashtirish / algoritmik / qidiruv fazosi (FAST qarori)
| Guruh | Sinf | tezlashuv x | ulush % |
|---|---|---|---|
| crackle_samples | code | 1.501 | 36.3 |
| crackle_samples | algorithmic | 1.544 | 38.9 |
| crackle_samples | search_space | 1.320 | 24.8 |
| cremi_A | code | 1.368 | 55.5 |
| cremi_A | algorithmic | 1.282 | 44.0 |
| cremi_A | search_space | 1.003 | 0.5 |

### Kontrastlar (median tezlashuv x): legacy'ga bittasini qo'shish / FAST'dan bittasini olish / Shapley
| Guruh | Omil | legacy + omil | FAST − omil | Shapley |
|---|---|---|---|---|
| crackle_samples | D | 1.364 | 1.245 | 1.313 |
| crackle_samples | H | 1.064 | 1.031 | 1.051 |
| crackle_samples | L | 1.315 | 1.515 | 1.418 |
| crackle_samples | S | 1.019 | 1.043 | 1.030 |
| crackle_samples | T | 1.157 | 1.459 | 1.301 |
| cremi_A | D | 1.016 | 1.002 | 1.003 |
| cremi_A | H | 1.092 | 1.151 | 1.102 |
| cremi_A | L | 1.135 | 1.387 | 1.242 |
| cremi_A | S | 1.018 | 1.002 | 1.006 |
| cremi_A | T | 1.113 | 1.371 | 1.220 |

### Har omil qaysi bosqichni o'zgartirdi (median tejalgan ms, eng katta 3 ta; + = tezroq)
| Guruh | Omil | Bosqichlar |
|---|---|---|
| crackle_samples | L | reduction_equal_hash +332.22 ms; reduction_equal_sort +166.54 ms; reduction_subset_incidence +95.22 ms |
| crackle_samples | H | reduction_equal_hash +55.71 ms; reduction_equal_sort +0.47 ms; reduction_subset_incidence -0.27 ms |
| crackle_samples | T | reduction_equal_sort +391.29 ms; reduction_equal_hash +17.29 ms; reduction_subset_incidence -0.87 ms |
| crackle_samples | S | dp +55.91 ms; reduction_equal_sort -0.22 ms; local +0.15 ms |
| crackle_samples | D | reduction_equal_sort +0.15 ms; runs -0.15 ms; scan -0.11 ms |
| cremi_A | L | reduction_equal_hash +5.80 ms; transpose -3.43 ms; reduction_equal_sort +3.17 ms |
| cremi_A | H | reduction_equal_hash +3.05 ms; boundary +0.02 ms; reduction_equal_sort -0.01 ms |
| cremi_A | T | reduction_equal_sort +3.82 ms; reduction_equal_hash +0.23 ms; reduction_subset_incidence -0.04 ms |
| cremi_A | S | scan -0.02 ms; reduction_equal_sort +0.01 ms; boundary +0.01 ms |
| cremi_A | D | reduction_equal_sort -0.01 ms; cc +0.01 ms; runs +0.00 ms |

### Namunalar bo'yicha encode vaqti (median, ms)
| Namuna | v1 aniq | legacy | v2 impl + regimes | FAST, R'siz | v2 FAST | jami x |
|---|---|---|---|---|---|---|
| connectomics_x0_y0_z256_512x512x256 | 3662.6 | 3652.7 | 1818.1 | 1829.1 | 1824.0 | 2.00 |
| connectomics_x0_y0_z384_512x512x128 | 1678.2 | 1681.2 | 801.9 | 832.8 | 811.0 | 2.07 |
| connectomics_x256_y256_z0_256x256x512 | 3191.9 | 3196.3 | 1240.1 | 802.0 | 797.8 | 4.01 |
| ws_x0_y0_z0_256x256x512 | 8622.3 | 8629.5 | 2593.0 | 1603.3 | 1639.6 | 5.26 |
| cremi_A_x0_y768_z0_128x128x64 | 18.1 | 18.2 | 12.1 | 12.6 | 12.3 | 1.48 |
| cremi_A_x0_y768_z0_256x256x64 | 98.3 | 102.2 | 54.1 | 57.8 | 51.1 | 2.00 |
| cremi_A_x256_y0_z0_128x128x64 | 17.3 | 17.7 | 11.7 | 12.1 | 11.9 | 1.49 |
| cremi_A_x256_y0_z0_256x256x64 | 93.4 | 95.1 | 50.8 | 52.3 | 50.9 | 1.87 |
| cremi_A_x512_y0_z0_128x128x64 | 15.0 | 15.3 | 9.9 | 10.2 | 9.8 | 1.56 |
| cremi_A_x512_y0_z0_256x256x64 | 92.7 | 89.8 | 45.8 | 51.1 | 44.5 | 2.02 |
| cremi_A_x512_y512_z0_128x128x64 | 21.5 | 21.6 | 10.9 | 11.0 | 10.8 | 2.00 |
| cremi_A_x512_y512_z0_256x256x64 | 94.1 | 93.8 | 50.0 | 52.5 | 47.5 | 1.98 |
| cremi_A_x768_y0_z0_128x128x64 | 16.2 | 17.0 | 10.7 | 11.2 | 10.8 | 1.57 |
| cremi_A_x768_y0_z0_256x256x64 | 93.7 | 95.5 | 48.7 | 51.0 | 45.2 | 2.11 |
| cremi_A_x768_y512_z0_128x128x64 | 17.0 | 16.5 | 11.3 | 11.9 | 11.8 | 1.40 |
| cremi_A_x768_y512_z0_256x256x64 | 94.8 | 95.7 | 51.0 | 53.8 | 51.8 | 1.85 |

### Xotira (yangi jarayon, OS peak working set; extra = encode paytidagi o'sish)
| Namuna | Kombinatsiya | kirish MiB | peak MiB | encode extra MiB |
|---|---|---|---|---|
| connectomics_x0_y0_z256_512x512x256 | ----- | 256 | 1070 | 778 |
| connectomics_x0_y0_z256_512x512x256 | L---- | 256 | 1070 | 778 |
| connectomics_x0_y0_z256_512x512x256 | LHTSD | 256 | 999 | 708 |
| connectomics_x0_y0_z256_512x512x256 | ----D | 256 | 1070 | 778 |
| connectomics_x0_y0_z256_512x512x256 | LHTS- | 256 | 1000 | 708 |
| connectomics_x0_y0_z384_512x512x128 | ----- | 128 | 536 | 372 |
| connectomics_x0_y0_z384_512x512x128 | L---- | 128 | 536 | 373 |
| connectomics_x0_y0_z384_512x512x128 | LHTSD | 128 | 505 | 342 |
| connectomics_x0_y0_z384_512x512x128 | ----D | 128 | 536 | 373 |
| connectomics_x0_y0_z384_512x512x128 | LHTS- | 128 | 505 | 342 |
| connectomics_x256_y256_z0_256x256x512 | ----- | 128 | 510 | 347 |
| connectomics_x256_y256_z0_256x256x512 | L---- | 128 | 510 | 346 |
| connectomics_x256_y256_z0_256x256x512 | LHTSD | 128 | 487 | 324 |
| connectomics_x256_y256_z0_256x256x512 | ----D | 128 | 509 | 346 |
| connectomics_x256_y256_z0_256x256x512 | LHTS- | 128 | 488 | 325 |
| ws_x0_y0_z0_256x256x512 | ----- | 256 | 964 | 673 |
| ws_x0_y0_z0_256x256x512 | L---- | 256 | 964 | 673 |
| ws_x0_y0_z0_256x256x512 | LHTSD | 256 | 892 | 601 |
| ws_x0_y0_z0_256x256x512 | ----D | 256 | 957 | 666 |
| ws_x0_y0_z0_256x256x512 | LHTS- | 256 | 898 | 606 |

Grafiklar: `analysis/v21_speedup/figures/V21_S1_shapley.png`, `V21_S2_stage_profile.png` (plot data `analysis/v21_speedup/plot_data/`).

## 3. Katta hajmlarda bog'liqlik: vaqt, xotira, nomzodlar, eng yirik komponent

Runlar: `results\20261106T091815Z_development_73f40dd8` (holat COMPLETE, OK bo'lmagan 0/600); stock: `results\20261106T100701Z_development_9be56574` (holat COMPLETE). Crop'lar ko'rilgan development manbalardan, origin'dan nested - qiyaliklar **tavsifiy**, mustaqil dalil emas.

Muammo o'lchami CAPE-FAST o'lchov qatorlaridan (`run.sqlite`; v1 legacy bilan bir xil, chunki baytlar va qisqartirish qoidalari bir xil): `nomzod` = qisqartirishdan oldingi nomzodlar (runs), `qolgan` = singleton/equal/subset dan keyingi nomzodlar, `incidence` = qolgan nomzod-CC bog'lanishlari, `komp.` = mustaqil komponentlar, `max komp.` = eng yirik komponentdagi CC soni; `reduksiya`/`yechish` = FAST ichidagi qisqartirish va pass1+pass2 vaqti (bitta o'lchov).

| Namuna | V | nomzod | qolgan | incidence | komp. | max komp. CC | reduksiya ms | yechish ms | FAST ms | v1 ms | regimes ms | SAFE ms | refine ms | flat ms | stock ms | FAST peak MiB | v1 peak | stock peak | kirish MiB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cremi_A_128x128x125 | 2048000 | 212650 | 157 | 3775 | 662 | 125 | 6.7 | 0.28 | 24.5 | 40.1 | 24.0 | 28.4 | 214.3 | 8.8 | 127.0 | 68 | 77 | 116 | 16 |
| cremi_A_256x256x125 | 8192000 | 804894 | 431 | 10547 | 1882 | 217 | 32.8 | 0.71 | 114.0 | 244.7 | 112.5 | 125.9 | 669.9 | 37.8 | 591.5 | 168 | 170 | 344 | 62 |
| cremi_A_512x512x125 | 32768000 | 3457192 | 1698 | 42486 | 8146 | 267 | 175.7 | 2.42 | 483.3 | 1157.5 | 479.8 | 533.8 | 2888.2 | 158.6 | 2587.7 | 571 | 578 | 1207 | 250 |
| cremi_A_1024x1024x125 | 131072000 | 14324342 | 6591 | 161428 | 28272 | 1478 | 841.9 | 9.78 | 2176.8 | 4832.7 | 2127.4 | 2425.7 | 10706.6 | 685.2 | - | 2197 | 2239 | - | 1000 |
| cremi_A_1250x1250x125 | 195312500 | 22381767 | 10166 | 222374 | 39391 | 1547 | 1354.4 | 15.13 | 3113.1 | 5499.0 | 3087.0 | 3491.7 | 15411.8 | 1036.1 | - | 3398 | 3458 | - | 1490 |
| crackle_connectomics_64x64x64 | 262144 | 4440 | 1 | 64 | 75 | 64 | 0.3 | 0.00 | 1.6 | 2.2 | 1.7 | 2.0 | 3.0 | 0.9 | 2.7 | 38 | 38 | 42 | 1 |
| crackle_connectomics_64x64x128 | 524288 | 4440 | 1 | 128 | 75 | 128 | 0.5 | 0.01 | 2.9 | 4.0 | 2.9 | 3.5 | 4.7 | 1.6 | 4.3 | 41 | 40 | 49 | 2 |
| crackle_connectomics_128x128x64 | 1048576 | 17858 | 10 | 221 | 250 | 67 | 1.2 | 0.03 | 6.1 | 11.0 | 6.1 | 7.1 | 9.3 | 3.0 | 16.4 | 47 | 45 | 64 | 4 |
| crackle_connectomics_64x64x256 | 1048576 | 15923 | 102 | 2041 | 313 | 257 | 1.3 | 0.32 | 6.9 | 12.8 | 6.8 | 8.1 | 27.2 | 3.4 | 16.1 | 47 | 45 | 60 | 4 |
| crackle_connectomics_128x128x128 | 2097152 | 18162 | 20 | 443 | 350 | 131 | 2.0 | 0.06 | 12.0 | 22.7 | 12.3 | 14.3 | 17.7 | 5.6 | 44.2 | 59 | 53 | 91 | 8 |
| crackle_connectomics_64x64x512 | 2097152 | 172018 | 2012 | 19816 | 4478 | 257 | 7.6 | 1.62 | 27.2 | 112.8 | 40.1 | 33.7 | 188.0 | 11.5 | 137.1 | 60 | 69 | 90 | 8 |
| crackle_connectomics_128x128x256 | 4194304 | 56753 | 379 | 6548 | 1363 | 286 | 5.9 | 0.89 | 31.8 | 61.5 | 31.6 | 35.7 | 78.8 | 12.5 | 116.0 | 84 | 81 | 136 | 16 |
| crackle_connectomics_256x256x64 | 4194304 | 202853 | 1390 | 11366 | 3846 | 149 | 10.7 | 1.22 | 39.1 | 72.7 | 37.9 | 43.0 | 123.4 | 14.9 | 183.7 | 84 | 80 | 149 | 16 |
| crackle_connectomics_128x128x512 | 8388608 | 655370 | 6292 | 64863 | 16022 | 318 | 40.1 | 6.44 | 127.9 | 589.1 | 191.7 | 151.1 | 472.7 | 42.7 | 1301.6 | 134 | 137 | 249 | 32 |
| crackle_connectomics_256x256x128 | 8388608 | 224078 | 1767 | 15473 | 5265 | 163 | 16.7 | 1.62 | 77.9 | 165.8 | 79.5 | 89.0 | 187.3 | 29.7 | 351.4 | 133 | 113 | 256 | 32 |
| crackle_connectomics_256x256x256 | 16777216 | 467828 | 4590 | 46767 | 11790 | 346 | 47.5 | 5.48 | 179.1 | 505.3 | 173.4 | 195.9 | 430.2 | 60.7 | 1032.1 | 229 | 190 | 435 | 64 |
| crackle_connectomics_512x512x64 | 16777216 | 1793395 | 26866 | 158990 | 29200 | 703 | 116.3 | 22.17 | 304.2 | 652.7 | 328.6 | 376.1 | 968.1 | 93.5 | 7456.3 | 259 | 270 | 475 | 64 |
| crackle_connectomics_256x256x512 | 33554432 | 2678197 | 42535 | 295863 | 44713 | 1085 | 252.3 | 46.71 | 642.0 | 3470.2 | 993.0 | 709.4 | 1721.0 | 170.4 | 19476.6 | 444 | 458 | 872 | 128 |
| crackle_connectomics_512x512x128 | 33554432 | 2818981 | 46712 | 294764 | 48636 | 1222 | 235.2 | 45.23 | 617.2 | 1324.4 | 615.6 | 700.6 | 1664.2 | 173.3 | 22414.1 | 448 | 459 | 908 | 128 |
| crackle_connectomics_512x512x256 | 67108864 | 4590554 | 79687 | 543426 | 82362 | 1856 | 447.6 | 96.34 | 1178.1 | 2861.1 | 1195.4 | 1320.4 | 2975.8 | 321.6 | - | 809 | 819 | - | 256 |
| crackle_connectomics_512x512x512 | 134217728 | 13200033 | 217470 | 1496959 | 222298 | 10369 | 1388.1 | 539.78 | 3431.5 | 14723.4 | 5761.3 | 3775.2 | 8782.7 | 741.0 | - | 1771 | 1855 | - | 512 |
| crackle_ws_128x128x128 | 2097152 | 632171 | 8809 | 52258 | 4342 | 213 | 20.1 | 5.57 | 65.3 | 192.8 | 66.2 | 80.6 | 1730.1 | 24.2 | 240.0 | 88 | 91 | 154 | 16 |
| crackle_ws_256x256x256 | 16777216 | 4705618 | 105462 | 609590 | 19815 | 374 | 306.1 | 91.84 | 796.0 | 2283.5 | 785.3 | 919.4 | 13993.7 | 232.1 | 2026.4 | 459 | 490 | 764 | 128 |
| crackle_ws_512x512x256 | 67108864 | 18353773 | 402569 | 2365516 | 71500 | 954 | 1283.0 | 401.82 | 3243.2 | 8978.7 | 3248.3 | 3755.8 | 52109.3 | 907.4 | - | 1709 | 1829 | - | 512 |
| crackle_ws_512x512x512 | 134217728 | 38104234 | 820833 | 4708491 | 146986 | 954 | 3033.5 | 839.82 | 7091.8 | 35764.1 | 11881.3 | 8177.3 | 110508.7 | 1875.5 | - | 3426 | 3707 | - | 1024 |

### Log-log qiyaliklar (y ∝ x^qiyalik; 1 = chiziqli)
| Manba | Usul | y | x | qiyalik | R² | n |
|---|---|---|---|---|---|---|
| CREMI A | fast | encode ms | V | 1.07 | 1.000 | 5 |
| CREMI A | fast | encode ms | nomzod | 1.04 | 0.999 | 5 |
| CREMI A | fast | encode ms | qolgan nomzod | 1.14 | 0.994 | 5 |
| CREMI A | fast | peak RSS | V | 0.87 | 0.994 | 5 |
| CREMI A | legacy | encode ms | V | 1.09 | 0.993 | 5 |
| CREMI A | legacy | encode ms | nomzod | 1.06 | 0.990 | 5 |
| CREMI A | legacy | encode ms | qolgan nomzod | 1.17 | 0.980 | 5 |
| CREMI A | legacy | peak RSS | V | 0.85 | 0.989 | 5 |
| CREMI A | regimes | encode ms | V | 1.07 | 1.000 | 5 |
| CREMI A | regimes | encode ms | nomzod | 1.04 | 0.999 | 5 |
| CREMI A | regimes | encode ms | qolgan nomzod | 1.15 | 0.994 | 5 |
| CREMI A | regimes | peak RSS | V | 0.87 | 0.993 | 5 |
| CREMI A | safe | encode ms | V | 1.06 | 1.000 | 5 |
| CREMI A | safe | encode ms | nomzod | 1.04 | 0.999 | 5 |
| CREMI A | safe | encode ms | qolgan nomzod | 1.14 | 0.996 | 5 |
| CREMI A | safe | peak RSS | V | 0.87 | 0.994 | 5 |
| CREMI A | refine | encode ms | V | 0.95 | 0.999 | 5 |
| CREMI A | refine | encode ms | nomzod | 0.93 | 0.999 | 5 |
| CREMI A | refine | encode ms | qolgan nomzod | 1.03 | 0.999 | 5 |
| CREMI A | refine | peak RSS | V | 0.89 | 0.995 | 5 |
| CREMI A | flat | encode ms | V | 1.05 | 1.000 | 5 |
| CREMI A | flat | encode ms | nomzod | 1.02 | 1.000 | 5 |
| CREMI A | flat | encode ms | qolgan nomzod | 1.12 | 0.996 | 5 |
| CREMI A | flat | peak RSS | V | 0.85 | 0.994 | 5 |
| CREMI A | stock | encode ms | V | 1.09 | 1.000 | 3 |
| CREMI A | stock | encode ms | nomzod | 1.08 | 0.999 | 3 |
| CREMI A | stock | encode ms | qolgan nomzod | 1.26 | 0.990 | 3 |
| CREMI A | stock | peak RSS | V | 0.85 | 0.998 | 3 |
| CREMI A | fast | pass1+pass2 ms | max komp. CC | 1.41 | 0.931 | 5 |
| CREMI A | fast | reduksiya ms | nomzod | 1.14 | 1.000 | 5 |
| CREMI A | - | nomzod | V | 1.02 | 1.000 | 5 |
| CREMI A | - | max komp. CC | V | 0.58 | 0.902 | 5 |
| Crackle connectomics | fast | encode ms | V | 1.25 | 0.989 | 16 |
| Crackle connectomics | fast | encode ms | nomzod | 0.88 | 0.977 | 16 |
| Crackle connectomics | fast | encode ms | qolgan nomzod | 0.55 | 0.930 | 16 |
| Crackle connectomics | fast | peak RSS | V | 0.63 | 0.933 | 16 |
| Crackle connectomics | legacy | encode ms | V | 1.40 | 0.963 | 16 |
| Crackle connectomics | legacy | encode ms | nomzod | 1.00 | 0.974 | 16 |
| Crackle connectomics | legacy | encode ms | qolgan nomzod | 0.63 | 0.937 | 16 |
| Crackle connectomics | legacy | peak RSS | V | 0.64 | 0.922 | 16 |
| Crackle connectomics | regimes | encode ms | V | 1.30 | 0.975 | 16 |
| Crackle connectomics | regimes | encode ms | nomzod | 0.92 | 0.978 | 16 |
| Crackle connectomics | regimes | encode ms | qolgan nomzod | 0.58 | 0.929 | 16 |
| Crackle connectomics | regimes | peak RSS | V | 0.63 | 0.934 | 16 |
| Crackle connectomics | safe | encode ms | V | 1.24 | 0.987 | 16 |
| Crackle connectomics | safe | encode ms | nomzod | 0.87 | 0.978 | 16 |
| Crackle connectomics | safe | encode ms | qolgan nomzod | 0.55 | 0.931 | 16 |
| Crackle connectomics | safe | peak RSS | V | 0.63 | 0.934 | 16 |
| Crackle connectomics | refine | encode ms | V | 1.30 | 0.945 | 16 |
| Crackle connectomics | refine | encode ms | nomzod | 0.94 | 0.984 | 16 |
| Crackle connectomics | refine | encode ms | qolgan nomzod | 0.60 | 0.981 | 16 |
| Crackle connectomics | refine | peak RSS | V | 0.67 | 0.947 | 16 |
| Crackle connectomics | flat | encode ms | V | 1.10 | 0.990 | 16 |
| Crackle connectomics | flat | encode ms | nomzod | 0.77 | 0.975 | 16 |
| Crackle connectomics | flat | encode ms | qolgan nomzod | 0.49 | 0.930 | 16 |
| Crackle connectomics | flat | peak RSS | V | 0.54 | 0.913 | 16 |
| Crackle connectomics | stock | encode ms | V | 1.87 | 0.951 | 14 |
| Crackle connectomics | stock | encode ms | nomzod | 1.28 | 0.970 | 14 |
| Crackle connectomics | stock | encode ms | qolgan nomzod | 0.76 | 0.909 | 14 |
| Crackle connectomics | stock | peak RSS | V | 0.67 | 0.962 | 14 |
| Crackle connectomics | fast | pass1+pass2 ms | max komp. CC | 2.34 | 0.809 | 16 |
| Crackle connectomics | fast | reduksiya ms | nomzod | 1.01 | 0.988 | 16 |
| Crackle connectomics | - | nomzod | V | 1.38 | 0.942 | 16 |
| Crackle connectomics | - | max komp. CC | V | 0.67 | 0.797 | 16 |
| Crackle ws | fast | encode ms | V | 1.12 | 0.999 | 4 |
| Crackle ws | fast | encode ms | nomzod | 1.14 | 0.998 | 4 |
| Crackle ws | fast | encode ms | qolgan nomzod | 1.03 | 1.000 | 4 |
| Crackle ws | fast | peak RSS | V | 0.88 | 0.997 | 4 |
| Crackle ws | legacy | encode ms | V | 1.21 | 0.990 | 4 |
| Crackle ws | legacy | encode ms | nomzod | 1.23 | 0.992 | 4 |
| Crackle ws | legacy | encode ms | qolgan nomzod | 1.11 | 0.985 | 4 |
| Crackle ws | legacy | peak RSS | V | 0.89 | 0.998 | 4 |
| Crackle ws | regimes | encode ms | V | 1.21 | 0.993 | 4 |
| Crackle ws | regimes | encode ms | nomzod | 1.23 | 0.994 | 4 |
| Crackle ws | regimes | encode ms | qolgan nomzod | 1.11 | 0.989 | 4 |
| Crackle ws | regimes | peak RSS | V | 0.88 | 0.997 | 4 |
| Crackle ws | safe | encode ms | V | 1.11 | 0.999 | 4 |
| Crackle ws | safe | encode ms | nomzod | 1.13 | 0.998 | 4 |
| Crackle ws | safe | encode ms | qolgan nomzod | 1.02 | 0.999 | 4 |
| Crackle ws | safe | peak RSS | V | 0.88 | 0.997 | 4 |
| Crackle ws | refine | encode ms | V | 0.99 | 1.000 | 4 |
| Crackle ws | refine | encode ms | nomzod | 1.01 | 1.000 | 4 |
| Crackle ws | refine | encode ms | qolgan nomzod | 0.91 | 0.998 | 4 |
| Crackle ws | refine | peak RSS | V | 0.89 | 0.998 | 4 |
| Crackle ws | flat | encode ms | V | 1.04 | 1.000 | 4 |
| Crackle ws | flat | encode ms | nomzod | 1.06 | 0.999 | 4 |
| Crackle ws | flat | encode ms | qolgan nomzod | 0.96 | 0.999 | 4 |
| Crackle ws | flat | peak RSS | V | 0.82 | 0.994 | 4 |
| Crackle ws | fast | pass1+pass2 ms | max komp. CC | 2.89 | 0.930 | 4 |
| Crackle ws | fast | reduksiya ms | nomzod | 1.22 | 0.997 | 4 |
| Crackle ws | - | nomzod | V | 0.98 | 1.000 | 4 |
| Crackle ws | - | max komp. CC | V | 0.39 | 0.948 | 4 |

### Crackle connectomics 4×4 grid: vaqt ∝ (XY)^a · Z^b
| Usul | a (XY) | b (Z) | n |
|---|---|---|---|
| fast | 1.24 | 1.32 | 16 |
| legacy | 1.32 | 1.76 | 16 |

O'tkazib yuborilgan: 6 ta (stock uchun >2^25 voksel `SKIPPED_BUDGET`, manbaga sig'maydiganlar `NOT_APPLICABLE`) - `data/manifests/scaling_v21_skipped.json`.

## 4. CAPE yadrosi, SAFE va refine: to'liq vaqtlar alohida

Encode = worker o'lchagan to'liq vaqt (bitta yadro, median). `native` = C++ encode chaqiruvi (SAFE/refine'da ikkala stream: CAPE + flat; v2.1 taymeri bo'lmasa `encode_core_ns`). `zstd` = barcha zstd chaqiruvlari (SAFE: ikkala stream; refine: flat + J0 + har bir baholash); faqat v2.1 taymerlari bor run'larda (scaling). `refine sikli` = `refine_ns` (ichida zstd ham bor), `refine Python` = refine sikli minus uning zstd'si. `glue` = encode − native − zstd − refine Python (nusxalash, Python; taymer yo'q run'larda zstd ham shu ustunda). Har ustun alohida median, shuning uchun qismlar yig'indisi encode medianiga aniq teng bo'lishi shart emas. Decode yo'li SAFE va refine'da bir xil: unzstd + stock Crackle.

| Ma'lumot | Usul | n | encode ms (med) | native ms | zstd ms | refine sikli ms | refine Python ms | baholashlar | glue ms | encode jami ms | decode ms | peak MiB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v2 test (24 ko'rilmagan CREMI B/C crop) | CAPE yadrosi (FAST, raw) | 24 | 31.18 | 29.72 | - | - | - | - | 0.51 | 784 | 7.05 | 81.6 |
| v2 test (24 ko'rilmagan CREMI B/C crop) | CAPE yadrosi + zstd9 | 24 | 31.78 | 28.63 | - | - | - | - | 0.70 | 798 | 7.14 | - |
| v2 test (24 ko'rilmagan CREMI B/C crop) | SAFE-ARCHIVE | 24 | 34.88 | 33.82 | - | - | - | - | 1.18 | 885 | 6.89 | 81.5 |
| v2 test (24 ko'rilmagan CREMI B/C crop) | SAFE + refine [EXPERIMENTAL] | 24 | 83.68 | 34.65 | - | 45.51 | - | 24 | 2.43 | 2169 | 6.87 | 91.2 |
| v2 test (24 ko'rilmagan CREMI B/C crop) | flat (pastki chegara) | 24 | 10.32 | - | - | - | - | - | - | 258 | 6.80 | 74.0 |
| v2 test (24 ko'rilmagan CREMI B/C crop) | flat + zstd9 | 24 | 10.75 | - | - | - | - | - | - | 267 | 6.87 | - |
| v2 test (24 ko'rilmagan CREMI B/C crop) | tuzatilgan stock | 24 | 165.56 | 155.92 | - | - | - | - | 2.81 | 4612 | 6.99 | 133.5 |
| Z=512 width (4 Crackle crop) | CAPE yadrosi (FAST, raw) | 4 | 1252.43 | 1235.78 | - | - | - | - | 21.82 | 5252 | 246.58 | 698.7 |
| Z=512 width (4 Crackle crop) | CAPE yadrosi + zstd9 | 4 | 1300.14 | 1236.79 | - | - | - | - | 48.91 | 5351 | 248.23 | - |
| Z=512 width (4 Crackle crop) | SAFE-ARCHIVE | 4 | 1434.31 | 1351.20 | - | - | - | - | 88.12 | 5924 | 253.57 | 700.3 |
| Z=512 width (4 Crackle crop) | SAFE + refine [EXPERIMENTAL] | 4 | 3833.50 | 1380.83 | - | 2262.49 | - | 24 | 92.35 | 38976 | 247.67 | 828.7 |
| Z=512 width (4 Crackle crop) | flat (pastki chegara) | 4 | 329.90 | - | - | - | - | - | - | 1328 | 143.09 | 424.6 |
| Z=512 width (4 Crackle crop) | flat + zstd9 | 4 | 358.05 | - | - | - | - | - | - | 1465 | 145.82 | - |
| Z=512 width (4 Crackle crop) | tuzatilgan stock | 4 | 38069.88 | 38069.35 | - | - | - | - | 0.52 | 298636 | 255.88 | 1248.6 |
| scaling (barcha crop'lar) | CAPE yadrosi (FAST, raw) | 25 | 127.88 | 127.79 | - | - | - | - | 0.16 | 23794 | 40.18 | 168.3 |
| scaling (barcha crop'lar) | SAFE-ARCHIVE | 25 | 151.13 | 136.10 | 6.49 | - | - | - | 1.10 | 27004 | 40.75 | 168.5 |
| scaling (barcha crop'lar) | SAFE + refine [EXPERIMENTAL] | 25 | 669.86 | 145.37 | 64.32 | 538.88 | 452.94 | 24 | 2.60 | 225887 | 40.40 | 199.7 |
| scaling (barcha crop'lar) | flat (pastki chegara) | 25 | 42.72 | - | - | - | - | - | - | 6652 | 23.16 | 162.4 |

## 5. Refinement holati: EKSPERIMENTAL

Refine `configs/methods.yaml` da `experimental: true`; faqat config'da nomi aniq yozilganda ishlaydi, hisobotlarda g'olib sifatida ko'rsatilmaydi va tasdiqlovchi `confirm_snemi3d.yaml` ga kiritilmagan. Sabab (v2 test): SAFE'ga nisbatan +0.013% (42 B / 24 crop), encode 2.73× sekin.

## 6. CREMI'dan mustaqil manba: SNEMI3D (tayyor, hali o'lchanmagan)

- Manba: DOI 10.5281/zenodo.7142003, litsenziya cc-by-4.0, md5 `3d25a7025f66698f33c7850ace885939` (Zenodo bilan mos), SHA-256 `59b72d89e14ddd4b…`.
- Muzlatilgan: 32 crop, 16 klaster, `prepared_at` 2026-11-06T07:11:37+00:00.
- Oldindan ro'yxatdan o'tgan konfiguratsiya: `configs/confirm_snemi3d.yaml` (primary: CAPE-FAST va tuzatilgan stock; secondary: SAFE va flat+zstd9; refine yo'q).
- Bu ma'lumotdan foydalangan run'lar: **yo`q (siqish o`lchovi hali qilinmagan)**.
- Batafsil: `docs/MUSTAQIL_DATA_SNEMI3D_UZ.md`.

## 7. Grafiklar

- `analysis/v21_final/figures/V21_S3_time_vs_voxels.png` (plot data `plot_data/V21_S3_time_vs_voxels.csv`)
- `analysis/v21_final/figures/V21_S4_memory_vs_voxels.png` (plot data `plot_data/V21_S4_memory_vs_voxels.csv`)
- `analysis/v21_final/figures/V21_S5_time_vs_candidates.png` (plot data `plot_data/V21_S5_time_vs_candidates.csv`)
- `analysis/v21_final/figures/V21_S6_solve_vs_maxcomp.png` (plot data `plot_data/V21_S6_solve_vs_maxcomp.csv`)
- `analysis/v21_final/figures/V21_S7_time_breakdown.png` (plot data `plot_data/V21_S7_time_breakdown.csv`)
- `analysis/v21_speedup/figures/V21_S1_shapley.png`, `V21_S2_stage_profile.png`
