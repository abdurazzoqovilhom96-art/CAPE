# Mustaqil audit — `v1_audit`

Raqamlar `05_raw_metrics/results.csv` dan `cape.statistics` dan foydalanmasdan qayta hisoblangan va run'ning `09_statistics/summary.json` bilan solishtirilgan. Run papkalari faqat o'qildi.

## `20261105T122347Z_all_d1a76eb7`

- **Mustaqillik:** 24 namuna, 12 klaster (macroblock), 2 ta original volume. CI shu volume'lar ichida shartli.
- **Hisobot bilan moslik:** ✅ verified
- **Determinizm:** {'cells_with_repeats': 1176, 'nondeterministic_bytes': 0, 'nondeterministic_sha': 7}

### Asosiy juftlik

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_m0 | crackle_pins_opt_m0 | 24 | 12 | 2 | 519345 | 520030 | 685 | 0.9987 | 23 | 1 | 0 | 0.1222 | 3.4115 | 1.0019 |

### Head-to-head (panel B, bir xil wrapper va Markov tartibi)

| competitor | cape_counterpart | n | cape_smaller | equal | cape_larger | sum_cape | sum_competitor | cape_vs_competitor_percent |
|---|---|---|---|---|---|---|---|---|
| blosc2_bshuffle_zstd5 | cape_m0 | 24 | 24 | 0 | 0 | 519345 | 4041495 | -87.1497 |
| compresso_lzma6 | cape_m0 | 24 | 22 | 0 | 2 | 519345 | 560176 | -7.2890 |
| compresso_native | cape_m0 | 24 | 24 | 0 | 0 | 519345 | 3133456 | -83.4258 |
| compresso_native+zstd3 | cape_m0+zstd3 | 24 | 24 | 0 | 0 | 316389 | 832540 | -61.9971 |
| compresso_native+zstd9 | cape_m0+zstd9 | 24 | 24 | 0 | 0 | 306806 | 749180 | -59.0478 |
| crackle_flat_m0 | cape_m0 | 24 | 21 | 0 | 3 | 519345 | 521013 | -0.3201 |
| crackle_flat_m0+zstd3 | cape_m0+zstd3 | 24 | 11 | 0 | 13 | 316389 | 316613 | -0.0707 |
| crackle_flat_m0+zstd9 | cape_m0+zstd9 | 24 | 5 | 0 | 19 | 306806 | 306352 | 0.1482 |
| crackle_flat_m5 | cape_m5 | 24 | 21 | 0 | 3 | 373953 | 375621 | -0.4441 |
| crackle_flat_m5+zstd3 | cape_m5+zstd3 | 24 | 10 | 0 | 14 | 288677 | 288602 | 0.0260 |
| crackle_flat_m5+zstd9 | cape_m5+zstd9 | 24 | 3 | 2 | 19 | 288791 | 288123 | 0.2318 |
| crackle_pins_fast_m0 | cape_m0 | 24 | 24 | 0 | 0 | 519345 | 529016 | -1.8281 |
| crackle_pins_fast_m0+zstd3 | cape_m0+zstd3 | 24 | 24 | 0 | 0 | 316389 | 323845 | -2.3023 |
| crackle_pins_fast_m0+zstd9 | cape_m0+zstd9 | 24 | 24 | 0 | 0 | 306806 | 314173 | -2.3449 |
| crackle_pins_opt_m0 | cape_m0 | 24 | 23 | 1 | 0 | 519345 | 520030 | -0.1317 |
| crackle_pins_opt_m0+zstd3 | cape_m0+zstd3 | 24 | 23 | 0 | 1 | 316389 | 316964 | -0.1814 |
| crackle_pins_opt_m0+zstd9 | cape_m0+zstd9 | 24 | 22 | 2 | 0 | 306806 | 307329 | -0.1702 |
| crackle_pins_opt_m5 | cape_m5 | 24 | 23 | 1 | 0 | 373953 | 374638 | -0.1828 |
| crackle_pins_opt_m5+zstd3 | cape_m5+zstd3 | 24 | 21 | 2 | 1 | 288677 | 289145 | -0.1619 |
| crackle_pins_opt_m5+zstd9 | cape_m5+zstd9 | 24 | 23 | 1 | 0 | 288791 | 289260 | -0.1621 |
| crackle_vendor_pins_opt_m0 | cape_m0 | 24 | 23 | 1 | 0 | 519345 | 520030 | -0.1317 |
| csgv_rans_b64 | cape_m0 | 24 | 24 | 0 | 0 | 519345 | 4249048 | -87.7774 |
| csgvr_sb_b64 | cape_m0 | 24 | 24 | 0 | 0 | 519345 | 5882752 | -91.1717 |
| lzma6_raw | cape_m0 | 24 | 24 | 0 | 0 | 519345 | 1105084 | -53.0040 |
| neuroglancer_b8 | cape_m0 | 24 | 24 | 0 | 0 | 519345 | 10625368 | -95.1122 |
| neuroglancer_b8+zstd3 | cape_m0+zstd3 | 24 | 24 | 0 | 0 | 316389 | 1534537 | -79.3821 |
| neuroglancer_b8+zstd9 | cape_m0+zstd9 | 24 | 24 | 0 | 0 | 306806 | 1329036 | -76.9151 |
| raw | cape_m0 | 24 | 24 | 0 | 0 | 519345 | 503317344 | -99.8968 |
| zstd3 | cape_m0 | 24 | 24 | 0 | 0 | 519345 | 2333857 | -77.7474 |
| zstd9 | cape_m0 | 24 | 24 | 0 | 0 | 519345 | 1791400 | -71.0090 |

### SAFE post-hoc (min(flat, X) bir xil wrapper bilan; engineering bound, hissa emas)

| track | n | flat | cape | safe_cape | safe_stock_pins | safe_cape_vs_flat_percent | safe_stock_vs_flat_percent |
|---|---|---|---|---|---|---|---|
| m0+none | 24 | 521013 | 519345 | 519248 | 519780 | -0.3388 | -0.2367 |
| m0+zstd3 | 24 | 316613 | 316389 | 316000 | 316372 | -0.1936 | -0.0761 |
| m0+zstd9 | 24 | 306352 | 306806 | 306236 | 306295 | -0.0379 | -0.0186 |
| m5+none | 24 | 375621 | 373953 | 373856 | 374388 | -0.4699 | -0.3283 |
| m5+zstd3 | 24 | 288602 | 288677 | 288198 | 288427 | -0.1400 | -0.0606 |
| m5+zstd9 | 24 | 288123 | 288791 | 288040 | 288056 | -0.0288 | -0.0233 |

### Label bo'limi ulushi

| method | n | label_bytes | total_bytes | share_median_percent | share_min_percent | share_max_percent |
|---|---|---|---|---|---|---|
| cape_m0 | 24 | 25020 | 519345 | 5.0580 | 3.4258 | 7.8663 |
| crackle_pins_opt_m0 | 24 | 25705 | 520030 | 5.2129 | 3.5361 | 7.9738 |

### UB/LB gap (cheklangan model; UB/LB butun fayl baytlari)

| method | n | note | room_bytes_total | room_percent_of_files | file_gap_over_ub_median_percent | file_gap_over_ub_max_percent | file_gap_over_lb_median_percent | label_section_gap_median_percent | label_section_gap_max_percent |
|---|---|---|---|---|---|---|---|---|---|
| cape_m0 | 24 | ub/lb are whole-stream bytes; model = restricted certified pin model | 148.0000 | 0.0285 | 0.0238 | 0.0794 | 0.0238 | 0.4245 | 1.2506 |

### Encode bosqichlari ulushi (`cape_core`, panel A)

| method | stage | n | median_share_percent | max_share_percent |
|---|---|---|---|---|
| cape_core | candidate_ns | 24 | 2.3810 | 3.4351 |
| cape_core | reduction_ns | 24 | 61.0891 | 70.5448 |
| cape_core | pass1_ns | 24 | 0.1722 | 0.3783 |
| cape_core | pass2_ns | 24 | 1.1090 | 11.4553 |

### Qo'shimcha juftliklar

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_m5 | crackle_pins_opt_m5 | 24 | 12 | 2 | 373953 | 374638 | 685 | 0.9982 | 23 | 1 | 0 | 0.1665 | 3.2575 | 0.9828 |
| cape_m0+zstd9 | crackle_flat_m0+zstd9 | 24 | 12 | 2 | 306806 | 306352 | -454 | 1.0015 | 5 | 0 | 19 | -0.1576 | 0.1924 | 0.9767 |
| cape_m5+zstd9 | crackle_flat_m5+zstd9 | 24 | 12 | 2 | 288791 | 288123 | -668 | 1.0023 | 3 | 2 | 19 | -0.2551 | 0.2046 | 0.9741 |

## `20261105T112549Z_pilot_5fc4a006`

- **Mustaqillik:** 12 namuna, 6 klaster (macroblock), 1 ta original volume. CI shu volume'lar ichida shartli.
- **Hisobot bilan moslik:** ✅ verified
- **Determinizm:** {'cells_with_repeats': 480, 'nondeterministic_bytes': 0, 'nondeterministic_sha': 2}

### Asosiy juftlik

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_m0 | crackle_pins_opt_m0 | 12 | 6 | 1 | 385013 | 385222 | 209 | 0.9995 | 12 | 0 | 0 | 0.0596 | 3.4148 | 1.0076 |

### Head-to-head (panel B, bir xil wrapper va Markov tartibi)

| competitor | cape_counterpart | n | cape_smaller | equal | cape_larger | sum_cape | sum_competitor | cape_vs_competitor_percent |
|---|---|---|---|---|---|---|---|---|
| blosc2_bshuffle_zstd5 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 3290941 | -88.3008 |
| compresso_lzma6 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 447268 | -13.9189 |
| compresso_native | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 2295248 | -83.2256 |
| compresso_native+zstd3 | cape_m0+zstd3 | 12 | 12 | 0 | 0 | 276860 | 651915 | -57.5313 |
| crackle_flat_m0 | cape_m0 | 12 | 8 | 0 | 4 | 385013 | 387597 | -0.6667 |
| crackle_flat_m0+zstd3 | cape_m0+zstd3 | 12 | 2 | 0 | 10 | 276860 | 275605 | 0.4554 |
| crackle_flat_m5 | cape_m5 | 12 | 8 | 0 | 4 | 302180 | 304764 | -0.8479 |
| crackle_flat_m5+zstd3 | cape_m5+zstd3 | 12 | 1 | 0 | 11 | 254931 | 253237 | 0.6689 |
| crackle_pins_fast_m0 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 389769 | -1.2202 |
| crackle_pins_fast_m0+zstd3 | cape_m0+zstd3 | 12 | 12 | 0 | 0 | 276860 | 280522 | -1.3054 |
| crackle_pins_opt_m0 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 385222 | -0.0543 |
| crackle_pins_opt_m0+zstd3 | cape_m0+zstd3 | 12 | 10 | 0 | 2 | 276860 | 276851 | 0.0033 |
| crackle_pins_opt_m5 | cape_m5 | 12 | 12 | 0 | 0 | 302180 | 302389 | -0.0691 |
| crackle_pins_opt_m5+zstd3 | cape_m5+zstd3 | 12 | 7 | 1 | 4 | 254931 | 255059 | -0.0502 |
| crackle_vendor_pins_opt_m0 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 385222 | -0.0543 |
| csgv_rans_b64 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 1532216 | -74.8721 |
| csgvr_sb_b64 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 2112576 | -81.7752 |
| lzma6_raw | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 801100 | -51.9395 |
| neuroglancer_b8 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 4402800 | -91.2553 |
| neuroglancer_b8+zstd3 | cape_m0+zstd3 | 12 | 12 | 0 | 0 | 276860 | 884418 | -68.6958 |
| raw | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 251658672 | -99.8470 |
| zstd3 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 1553192 | -75.2115 |
| zstd9 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 1225046 | -68.5715 |

### SAFE post-hoc (min(flat, X) bir xil wrapper bilan; engineering bound, hissa emas)

| track | n | flat | cape | safe_cape | safe_stock_pins | safe_cape_vs_flat_percent | safe_stock_vs_flat_percent |
|---|---|---|---|---|---|---|---|
| m0+none | 12 | 387597 | 385013 | 383864 | 384021 | -0.9631 | -0.9226 |
| m0+zstd3 | 12 | 275605 | 276860 | 275209 | 275288 | -0.1437 | -0.1150 |
| m5+none | 12 | 304764 | 302180 | 301031 | 301188 | -1.2249 | -1.1734 |
| m5+zstd3 | 12 | 253237 | 254931 | 253062 | 253075 | -0.0691 | -0.0640 |

### Label bo'limi ulushi

| method | n | label_bytes | total_bytes | share_median_percent | share_min_percent | share_max_percent |
|---|---|---|---|---|---|---|
| cape_m0 | 12 | 62737 | 385013 | 15.5577 | 13.9966 | 21.9271 |
| crackle_pins_opt_m0 | 12 | 62946 | 385222 | 15.6135 | 14.0225 | 21.9829 |

### UB/LB gap (cheklangan model; UB/LB butun fayl baytlari)

| method | n | note | room_bytes_total | room_percent_of_files | file_gap_over_ub_median_percent | file_gap_over_ub_max_percent | file_gap_over_lb_median_percent | label_section_gap_median_percent | label_section_gap_max_percent |
|---|---|---|---|---|---|---|---|---|---|
| cape_m0 | 12 | ub/lb are whole-stream bytes; model = restricted certified pin model | 93.0000 | 0.0242 | 0.0155 | 0.0476 | 0.0155 | 0.1086 | 0.2744 |

### Encode bosqichlari ulushi (`cape_core`, panel A)

| method | stage | n | median_share_percent | max_share_percent |
|---|---|---|---|---|
| cape_core | candidate_ns | 12 | 1.6678 | 2.3228 |
| cape_core | reduction_ns | 12 | 60.8305 | 67.8601 |
| cape_core | pass1_ns | 12 | 0.2169 | 0.3533 |
| cape_core | pass2_ns | 12 | 0.1847 | 24.2090 |

### Qo'shimcha juftliklar

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_m5 | crackle_pins_opt_m5 | 12 | 6 | 1 | 302180 | 302389 | 209 | 0.9993 | 12 | 0 | 0 | 0.0767 | 3.1563 | 0.9960 |
| cape_m0+zstd9 | crackle_flat_m0+zstd9 | 0 | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 | - | - | - |
| cape_m5+zstd9 | crackle_flat_m5+zstd9 | 0 | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 | - | - | - |

## `20261105T145305Z_development_c1d12b3e`

- **Mustaqillik:** 4 namuna, 4 klaster (macroblock), 2 ta original volume. CI shu volume'lar ichida shartli.
- **Hisobot bilan moslik:** ✅ verified
- **Determinizm:** {'cells_with_repeats': 40, 'nondeterministic_bytes': 0, 'nondeterministic_sha': 0}

### Asosiy juftlik

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_m0 | crackle_pins_opt_m0 | 4 | 4 | 2 | 8791287 | 8856190 | 64903 | 0.9927 | 4 | 0 | 0 | 0.8028 | 11.4198 | 1.0385 |

### Head-to-head (panel B, bir xil wrapper va Markov tartibi)

| competitor | cape_counterpart | n | cape_smaller | equal | cape_larger | sum_cape | sum_competitor | cape_vs_competitor_percent |
|---|---|---|---|---|---|---|---|---|
| crackle_flat_m0 | cape_m0 | 4 | 4 | 0 | 0 | 8791287 | 9903553 | -11.2310 |
| crackle_pins_opt_m0 | cape_m0 | 4 | 4 | 0 | 0 | 8791287 | 8856190 | -0.7329 |
| crackle_vendor_pins_opt_m0 | cape_m0 | 4 | 4 | 0 | 0 | 8791287 | 8856190 | -0.7329 |
| zstd3 | cape_m0 | 4 | 4 | 0 | 0 | 8791287 | 23470524 | -62.5433 |

### SAFE post-hoc (min(flat, X) bir xil wrapper bilan; engineering bound, hissa emas)

| track | n | flat | cape | safe_cape | safe_stock_pins | safe_cape_vs_flat_percent | safe_stock_vs_flat_percent |
|---|---|---|---|---|---|---|---|
| m0+none | 4 | 9903553 | 8791287 | 8791287 | 8856190 | -11.2310 | -10.5756 |

### Label bo'limi ulushi

| method | n | label_bytes | total_bytes | share_median_percent | share_min_percent | share_max_percent |
|---|---|---|---|---|---|---|
| cape_m0 | 4 | 1624792 | 8791287 | 8.5005 | 7.8716 | 29.6233 |
| crackle_pins_opt_m0 | 4 | 1689695 | 8856190 | 9.2943 | 8.5805 | 30.0609 |

### UB/LB gap (cheklangan model; UB/LB butun fayl baytlari)

| method | n | note | room_bytes_total | room_percent_of_files | file_gap_over_ub_median_percent | file_gap_over_ub_max_percent | file_gap_over_lb_median_percent | label_section_gap_median_percent | label_section_gap_max_percent |
|---|---|---|---|---|---|---|---|---|---|
| cape_m0 | 4 | ub/lb are whole-stream bytes; model = restricted certified pin model | 61166.0000 | 0.6958 | 0.5871 | 0.8425 | 0.5906 | 6.6878 | 7.1418 |

### Encode bosqichlari ulushi (`cape_core`, panel A)

| method | stage | n | median_share_percent | max_share_percent |
|---|---|---|---|---|
| cape_core | candidate_ns | 4 | 0.7702 | 1.0272 |
| cape_core | reduction_ns | 4 | 57.0092 | 74.9366 |
| cape_core | pass1_ns | 4 | 1.7230 | 2.4628 |
| cape_core | pass2_ns | 4 | 4.5355 | 22.4776 |

### Qo'shimcha juftliklar

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_m5 | crackle_pins_opt_m5 | 0 | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 | - | - | - |
| cape_m0+zstd9 | crackle_flat_m0+zstd9 | 0 | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 | - | - | - |
| cape_m5+zstd9 | crackle_flat_m5+zstd9 | 0 | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 | - | - | - |

