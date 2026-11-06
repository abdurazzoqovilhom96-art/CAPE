# Mustaqil audit — `v2_audit`

Raqamlar `05_raw_metrics/results.csv` dan `cape.statistics` dan foydalanmasdan qayta hisoblangan va run'ning `09_statistics/summary.json` bilan solishtirilgan. Run papkalari faqat o'qildi.

## `20261106T041741Z_pilot_ca467036`

- **Mustaqillik:** 12 namuna, 6 klaster (macroblock), 1 ta original volume. CI shu volume'lar ichida shartli.
- **Hisobot bilan moslik:** ✅ verified
- **Determinizm:** {'cells_with_repeats': 336, 'nondeterministic_bytes': 0, 'nondeterministic_sha': 0}

### Asosiy juftlik

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| safe_refine_e24_m0_zstd9 | safe_archive_m0_zstd9 | 12 | 6 | 1 | 270685 | 270695 | 10 | 1.0000 | 2 | 10 | 0 | 0.0000 | 0.1514 | 1.0023 |

### Head-to-head (panel B, bir xil wrapper va Markov tartibi)

| competitor | cape_counterpart | n | cape_smaller | equal | cape_larger | sum_cape | sum_competitor | cape_vs_competitor_percent |
|---|---|---|---|---|---|---|---|---|
| crackle_flat_m0 | cape_m0 | 12 | 8 | 0 | 4 | 385013 | 387597 | -0.6667 |
| crackle_flat_m0+zstd3 | cape_m0+zstd3 | 12 | 2 | 0 | 10 | 276860 | 275605 | 0.4554 |
| crackle_flat_m0+zstd9 | cape_m0+zstd9 | 12 | 2 | 0 | 10 | 272116 | 270933 | 0.4366 |
| crackle_pins_opt_corrected_m0 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 385222 | -0.0543 |
| crackle_pins_opt_corrected_m0+zstd3 | cape_m0+zstd3 | 12 | 10 | 0 | 2 | 276860 | 276851 | 0.0033 |
| crackle_pins_opt_corrected_m0+zstd9 | cape_m0+zstd9 | 12 | 11 | 1 | 0 | 272116 | 272246 | -0.0478 |
| crackle_pins_opt_m0 | cape_m0 | 12 | 12 | 0 | 0 | 385013 | 385222 | -0.0543 |
| crackle_pins_opt_m0+zstd3 | cape_m0+zstd3 | 12 | 10 | 0 | 2 | 276860 | 276851 | 0.0033 |
| crackle_pins_opt_m0+zstd9 | cape_m0+zstd9 | 12 | 11 | 1 | 0 | 272116 | 272246 | -0.0478 |
| safe_refine_anchor_e24_m0_zstd9 | cape_m0 | 12 | 0 | 0 | 12 | 385013 | 270695 | 42.2313 |
| safe_refine_e24_m0_zstd3 | cape_m0 | 12 | 0 | 0 | 12 | 385013 | 275200 | 39.9030 |
| safe_refine_e24_m0_zstd9 | cape_m0 | 12 | 0 | 0 | 12 | 385013 | 270685 | 42.2365 |
| safe_refine_e64_m0_zstd9 | cape_m0 | 12 | 0 | 0 | 12 | 385013 | 270685 | 42.2365 |
| safe_refine_e8_m0_zstd9 | cape_m0 | 12 | 0 | 0 | 12 | 385013 | 270693 | 42.2323 |
| safe_refine_unpin_e24_m0_zstd9 | cape_m0 | 12 | 0 | 0 | 12 | 385013 | 270685 | 42.2365 |

### SAFE post-hoc (min(flat, X) bir xil wrapper bilan; engineering bound, hissa emas)

| track | n | flat | cape | safe_cape | safe_stock_pins | safe_cape_vs_flat_percent | safe_stock_vs_flat_percent |
|---|---|---|---|---|---|---|---|
| m0+none | 12 | 387597 | 385013 | 383864 | 384021 | -0.9631 | -0.9226 |
| m0+zstd3 | 12 | 275605 | 276860 | 275209 | 275288 | -0.1437 | -0.1150 |
| m0+zstd9 | 12 | 270933 | 272116 | 270695 | 270707 | -0.0878 | -0.0834 |

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
| cape_core | scan_ns | 12 | 8.4180 | 11.4718 |
| cape_core | boundary_ns | 12 | 14.0052 | 57.7066 |
| cape_core | cc_ns | 12 | 17.7353 | 19.1858 |
| cape_core | transpose_ns | 12 | 11.3598 | 19.3296 |
| cape_core | runs_ns | 12 | 12.3209 | 13.4262 |
| cape_core | candidate_ns | 12 | 3.4094 | 4.3881 |
| cape_core | reduction_ns | 12 | 27.2300 | 30.9071 |
| cape_core | reduction_singleton_ns | 12 | 2.6522 | 3.0213 |
| cape_core | reduction_equal_hash_ns | 12 | 7.8641 | 8.6861 |
| cape_core | reduction_equal_sort_ns | 12 | 13.5193 | 15.7221 |
| cape_core | reduction_subset_incidence_ns | 12 | 1.6514 | 2.6761 |
| cape_core | reduction_subset_scan_ns | 12 | 1.6009 | 2.1264 |
| cape_core | component_ns | 12 | 0.0764 | 0.1021 |
| cape_core | pass1_ns | 12 | 0.3451 | 0.4754 |
| cape_core | dp_ns | 12 | 0.0056 | 0.0511 |
| cape_core | local_ns | 12 | 0.1924 | 0.4196 |
| cape_core | pass2_ns | 12 | 0.2407 | 0.5557 |
| cape_core | serialize_ns | 12 | 0.0706 | 0.1166 |

### Qo'shimcha juftliklar

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_fast_m0 | crackle_pins_opt_corrected_m0 | 12 | 6 | 1 | 385013 | 385222 | 209 | 0.9995 | 12 | 0 | 0 | 0.0596 | 5.3879 | 1.0011 |
| cape_m0 | crackle_pins_opt_m0 | 12 | 6 | 1 | 385013 | 385222 | 209 | 0.9995 | 12 | 0 | 0 | 0.0596 | 5.9746 | 0.9998 |
| cape_fast_m0 | crackle_pins_opt_m0 | 12 | 6 | 1 | 385013 | 385222 | 209 | 0.9995 | 12 | 0 | 0 | 0.0596 | 6.0400 | 1.0059 |
| cape_m0 | cape_m0_legacy | 12 | 6 | 1 | 385013 | 385013 | 0 | 1.0000 | 0 | 12 | 0 | 0.0000 | 1.7282 | 0.9965 |

## `20261106T044558Z_all_83c337ae`

- **Mustaqillik:** 24 namuna, 12 klaster (macroblock), 2 ta original volume. CI shu volume'lar ichida shartli.
- **Hisobot bilan moslik:** ✅ verified
- **Determinizm:** {'cells_with_repeats': 912, 'nondeterministic_bytes': 0, 'nondeterministic_sha': 0}

### Asosiy juftlik

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| safe_refine_e24_m0_zstd9 | safe_archive_m0_zstd9 | 24 | 12 | 2 | 318450 | 318492 | 42 | 0.9999 | 10 | 14 | 0 | 0.0000 | 0.3665 | 0.9961 |

### Head-to-head (panel B, bir xil wrapper va Markov tartibi)

| competitor | cape_counterpart | n | cape_smaller | equal | cape_larger | sum_cape | sum_competitor | cape_vs_competitor_percent |
|---|---|---|---|---|---|---|---|---|
| crackle_flat_m0 | cape_m0 | 24 | 12 | 2 | 10 | 534485 | 535558 | -0.2004 |
| crackle_flat_m0+zstd3 | cape_m0+zstd3 | 24 | 15 | 0 | 9 | 328690 | 329888 | -0.3632 |
| crackle_flat_m0+zstd9 | cape_m0+zstd9 | 24 | 9 | 0 | 15 | 318839 | 319047 | -0.0652 |
| crackle_pins_opt_corrected_m0 | cape_m0 | 24 | 23 | 1 | 0 | 534485 | 535058 | -0.1071 |
| crackle_pins_opt_corrected_m0+zstd3 | cape_m0+zstd3 | 24 | 21 | 1 | 2 | 328690 | 329255 | -0.1716 |
| crackle_pins_opt_corrected_m0+zstd9 | cape_m0+zstd9 | 24 | 22 | 1 | 1 | 318839 | 319269 | -0.1347 |
| crackle_pins_opt_m0 | cape_m0 | 24 | 23 | 1 | 0 | 534485 | 535058 | -0.1071 |
| crackle_pins_opt_m0+zstd3 | cape_m0+zstd3 | 24 | 21 | 1 | 2 | 328690 | 329255 | -0.1716 |
| crackle_pins_opt_m0+zstd9 | cape_m0+zstd9 | 24 | 22 | 1 | 1 | 318839 | 319269 | -0.1347 |
| crackle_vendor_pins_opt_m0 | cape_m0 | 24 | 23 | 1 | 0 | 534485 | 535058 | -0.1071 |
| safe_refine_e24_m0_zstd3 | cape_m0 | 24 | 0 | 0 | 24 | 534485 | 328411 | 62.7488 |
| safe_refine_e24_m0_zstd9 | cape_m0 | 24 | 0 | 0 | 24 | 534485 | 318450 | 67.8395 |

### SAFE post-hoc (min(flat, X) bir xil wrapper bilan; engineering bound, hissa emas)

| track | n | flat | cape | safe_cape | safe_stock_pins | safe_cape_vs_flat_percent | safe_stock_vs_flat_percent |
|---|---|---|---|---|---|---|---|
| m0+none | 24 | 535558 | 534485 | 534011 | 534372 | -0.2889 | -0.2215 |
| m0+zstd3 | 24 | 329888 | 328690 | 328491 | 328997 | -0.4235 | -0.2701 |
| m0+zstd9 | 24 | 319047 | 318839 | 318492 | 318727 | -0.1740 | -0.1003 |

### Label bo'limi ulushi

| method | n | label_bytes | total_bytes | share_median_percent | share_min_percent | share_max_percent |
|---|---|---|---|---|---|---|
| cape_m0 | 24 | 27422 | 534485 | 5.4250 | 3.5820 | 8.1197 |
| crackle_pins_opt_m0 | 24 | 27995 | 535058 | 5.5910 | 3.6495 | 8.2759 |

### UB/LB gap (cheklangan model; UB/LB butun fayl baytlari)

| method | n | note | room_bytes_total | room_percent_of_files | file_gap_over_ub_median_percent | file_gap_over_ub_max_percent | file_gap_over_lb_median_percent | label_section_gap_median_percent | label_section_gap_max_percent |
|---|---|---|---|---|---|---|---|---|---|
| cape_m0 | 24 | ub/lb are whole-stream bytes; model = restricted certified pin model | 143.0000 | 0.0268 | 0.0204 | 0.0786 | 0.0204 | 0.3236 | 1.3919 |

### Encode bosqichlari ulushi (`cape_core`, panel A)

| method | stage | n | median_share_percent | max_share_percent |
|---|---|---|---|---|
| cape_core | scan_ns | 24 | 8.2045 | 11.0804 |
| cape_core | boundary_ns | 24 | 11.7804 | 13.8726 |
| cape_core | cc_ns | 24 | 14.6993 | 18.7347 |
| cape_core | transpose_ns | 24 | 9.6629 | 12.9558 |
| cape_core | runs_ns | 24 | 15.1597 | 18.3594 |
| cape_core | candidate_ns | 24 | 6.1433 | 8.8063 |
| cape_core | reduction_ns | 24 | 28.8650 | 37.0627 |
| cape_core | reduction_singleton_ns | 24 | 3.3446 | 4.8766 |
| cape_core | reduction_equal_hash_ns | 24 | 8.0949 | 10.8835 |
| cape_core | reduction_equal_sort_ns | 24 | 15.5039 | 21.7282 |
| cape_core | reduction_subset_incidence_ns | 24 | 0.4748 | 2.4433 |
| cape_core | reduction_subset_scan_ns | 24 | 0.4021 | 1.1499 |
| cape_core | component_ns | 24 | 0.0569 | 0.0886 |
| cape_core | pass1_ns | 24 | 0.3476 | 0.5887 |
| cape_core | dp_ns | 24 | 0.0295 | 0.0727 |
| cape_core | local_ns | 24 | 0.1131 | 0.3346 |
| cape_core | pass2_ns | 24 | 0.1658 | 0.4474 |
| cape_core | serialize_ns | 24 | 0.0514 | 0.0919 |

### Qo'shimcha juftliklar

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_fast_m0 | crackle_pins_opt_corrected_m0 | 24 | 12 | 2 | 534485 | 535058 | 573 | 0.9989 | 23 | 1 | 0 | 0.0915 | 5.6312 | 0.9994 |
| cape_m0 | crackle_pins_opt_m0 | 24 | 12 | 2 | 534485 | 535058 | 573 | 0.9989 | 23 | 1 | 0 | 0.0915 | 6.1965 | 1.0077 |
| cape_fast_m0 | crackle_pins_opt_m0 | 24 | 12 | 2 | 534485 | 535058 | 573 | 0.9989 | 23 | 1 | 0 | 0.0915 | 6.1650 | 1.0041 |
| cape_m0 | cape_m0_legacy | 24 | 12 | 2 | 534485 | 534485 | 0 | 1.0000 | 0 | 24 | 0 | 0.0000 | 1.7814 | 1.0065 |

## `20261106T062540Z_development_0227806a`

- **Mustaqillik:** 4 namuna, 4 klaster (macroblock), 2 ta original volume. CI shu volume'lar ichida shartli.
- **Hisobot bilan moslik:** ✅ verified
- **Determinizm:** {'cells_with_repeats': 68, 'nondeterministic_bytes': 0, 'nondeterministic_sha': 0}

### Asosiy juftlik

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_fast_m0 | crackle_pins_opt_corrected_m0 | 4 | 4 | 2 | 8791299 | 8856190 | 64891 | 0.9927 | 4 | 0 | 0 | 0.8028 | 29.2241 | 1.0220 |

### Head-to-head (panel B, bir xil wrapper va Markov tartibi)

| competitor | cape_counterpart | n | cape_smaller | equal | cape_larger | sum_cape | sum_competitor | cape_vs_competitor_percent |
|---|---|---|---|---|---|---|---|---|
| crackle_flat_m0 | cape_m0 | 4 | 4 | 0 | 0 | 8791287 | 9903553 | -11.2310 |
| crackle_flat_m0+zstd9 | cape_m0+zstd9 | 4 | 4 | 0 | 0 | 6542448 | 6928780 | -5.5758 |
| crackle_pins_opt_corrected_m0 | cape_m0 | 4 | 4 | 0 | 0 | 8791287 | 8856190 | -0.7329 |
| crackle_pins_opt_corrected_m0+zstd9 | cape_m0+zstd9 | 4 | 4 | 0 | 0 | 6542448 | 6574894 | -0.4935 |
| crackle_pins_opt_m0 | cape_m0 | 4 | 4 | 0 | 0 | 8791287 | 8856190 | -0.7329 |
| crackle_pins_opt_m0+zstd9 | cape_m0+zstd9 | 4 | 4 | 0 | 0 | 6542448 | 6574894 | -0.4935 |
| safe_refine_e24_m0_zstd9 | cape_m0 | 4 | 0 | 0 | 4 | 8791287 | 6542030 | 34.3816 |

### SAFE post-hoc (min(flat, X) bir xil wrapper bilan; engineering bound, hissa emas)

| track | n | flat | cape | safe_cape | safe_stock_pins | safe_cape_vs_flat_percent | safe_stock_vs_flat_percent |
|---|---|---|---|---|---|---|---|
| m0+none | 4 | 9903553 | 8791287 | 8791287 | 8856190 | -11.2310 | -10.5756 |
| m0+zstd9 | 4 | 6928780 | 6542448 | 6542448 | 6574894 | -5.5758 | -5.1075 |

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
| cape_core | scan_ns | 4 | 1.4095 | 1.6955 |
| cape_core | boundary_ns | 4 | 9.5066 | 10.6200 |
| cape_core | cc_ns | 4 | 8.8478 | 12.1723 |
| cape_core | transpose_ns | 4 | 8.3698 | 11.1369 |
| cape_core | runs_ns | 4 | 7.0620 | 8.9516 |
| cape_core | candidate_ns | 4 | 1.7634 | 2.3727 |
| cape_core | reduction_ns | 4 | 34.7241 | 44.7331 |
| cape_core | reduction_singleton_ns | 4 | 0.9851 | 1.1065 |
| cape_core | reduction_equal_hash_ns | 4 | 5.1210 | 6.9264 |
| cape_core | reduction_equal_sort_ns | 4 | 18.1532 | 23.1900 |
| cape_core | reduction_subset_incidence_ns | 4 | 3.1512 | 5.3037 |
| cape_core | reduction_subset_scan_ns | 4 | 6.9308 | 8.6722 |
| cape_core | component_ns | 4 | 1.5369 | 1.6426 |
| cape_core | pass1_ns | 4 | 4.1682 | 4.6346 |
| cape_core | dp_ns | 4 | 0.0216 | 0.5288 |
| cape_core | local_ns | 4 | 3.0769 | 3.7319 |
| cape_core | pass2_ns | 4 | 3.9994 | 4.7018 |
| cape_core | serialize_ns | 4 | 0.0643 | 0.1512 |

### Qo'shimcha juftliklar

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_m0 | crackle_pins_opt_m0 | 4 | 4 | 2 | 8791287 | 8856190 | 64903 | 0.9927 | 4 | 0 | 0 | 0.8028 | 27.0948 | 1.0435 |
| cape_fast_m0 | crackle_pins_opt_m0 | 4 | 4 | 2 | 8791299 | 8856190 | 64891 | 0.9927 | 4 | 0 | 0 | 0.8028 | 34.1640 | 1.0405 |
| cape_m0 | cape_m0_legacy | 4 | 4 | 2 | 8791287 | 8791287 | 0 | 1.0000 | 0 | 4 | 0 | 0.0000 | 2.3841 | 1.0005 |

