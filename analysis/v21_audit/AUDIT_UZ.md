# Mustaqil audit — `v21_audit`

Raqamlar `05_raw_metrics/results.csv` dan `cape.statistics` dan foydalanmasdan qayta hisoblangan va run'ning `09_statistics/summary.json` bilan solishtirilgan. Run papkalari faqat o'qildi.

## `20261106T091815Z_development_73f40dd8`

- **Mustaqillik:** 25 namuna, 3 klaster (macroblock), 3 ta original volume. CI shu volume'lar ichida shartli.
- **Hisobot bilan moslik:** ✅ verified
- **Determinizm:** {'cells_with_repeats': 150, 'nondeterministic_bytes': 0, 'nondeterministic_sha': 0}

### Asosiy juftlik

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_fast_m0 | cape_m0_legacy | 25 | 3 | 3 | 38994302 | 38963621 | -30681 | 1.0008 | 0 | 20 | 5 | 0.0000 | 2.4425 | 0.9985 |

### Head-to-head (panel B, bir xil wrapper va Markov tartibi)

| competitor | cape_counterpart | n | cape_smaller | equal | cape_larger | sum_cape | sum_competitor | cape_vs_competitor_percent |
|---|---|---|---|---|---|---|---|---|
| crackle_flat_m0 | cape_m0 | 25 | 22 | 0 | 3 | 38963621 | 45183346 | -13.7655 |
| safe_refine_e24_m0_zstd9 | cape_m0 | 25 | 0 | 0 | 25 | 38963621 | 28316812 | 37.5989 |

### SAFE post-hoc (min(flat, X) bir xil wrapper bilan; engineering bound, hissa emas)

| track | n | flat | cape | safe_cape | safe_cape_vs_flat_percent |
|---|---|---|---|---|---|
| m0+none | 25 | 45183346 | 38963621 | 38860443 | -13.9939 |

### Label bo'limi ulushi

| method | n | label_bytes | total_bytes | share_median_percent | share_min_percent | share_max_percent |
|---|---|---|---|---|---|---|
| cape_m0 | 25 | 9092186 | 38963621 | 10.8805 | 5.2832 | 29.3144 |

### UB/LB gap (cheklangan model; UB/LB butun fayl baytlari)

| method | n | note | room_bytes_total | room_percent_of_files | file_gap_over_ub_median_percent | file_gap_over_ub_max_percent | file_gap_over_lb_median_percent | label_section_gap_median_percent | label_section_gap_max_percent |
|---|---|---|---|---|---|---|---|---|---|
| cape_m0 | 25 | ub/lb are whole-stream bytes; model = restricted certified pin model | 287403.0000 | 0.7376 | 0.2179 | 0.9312 | 0.2184 | 2.7472 | 7.9725 |

### Encode bosqichlari ulushi (`cape_core`, panel A)

_yo'q_

### Qo'shimcha juftliklar

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_fast_m0 | crackle_pins_opt_corrected_m0 | 0 | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 | - | - | - |
| safe_refine_e24_m0_zstd9 | safe_archive_m0_zstd9 | 25 | 3 | 3 | 28316812 | 28319570 | 2758 | 0.9999 | 16 | 9 | 0 | 0.0003 | 0.2744 | 1.0054 |

## `20261106T100701Z_development_9be56574`

- **Mustaqillik:** 19 namuna, 3 klaster (macroblock), 3 ta original volume. CI shu volume'lar ichida shartli.
- **Hisobot bilan moslik:** ✅ verified
- **Determinizm:** {'cells_with_repeats': 38, 'nondeterministic_bytes': 0, 'nondeterministic_sha': 0}

### Asosiy juftlik

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_fast_m0 | crackle_pins_opt_corrected_m0 | 19 | 3 | 3 | 5388140 | 5422829 | 34689 | 0.9936 | 15 | 4 | 0 | 0.2757 | 5.1087 | 1.0104 |

### Head-to-head (panel B, bir xil wrapper va Markov tartibi)

_yo'q_

### SAFE post-hoc (min(flat, X) bir xil wrapper bilan; engineering bound, hissa emas)

_yo'q_

### Label bo'limi ulushi

_yo'q_

### UB/LB gap (cheklangan model; UB/LB butun fayl baytlari)

_yo'q_

### Encode bosqichlari ulushi (`cape_core`, panel A)

_yo'q_

### Qo'shimcha juftliklar

| new | base | n_samples | n_clusters | n_source_volumes | total_bytes_new | total_bytes_base | saved_bytes | total_ratio | n_smaller | n_ties | n_regressions | median_sample_gain_percent | geo_speedup_encode | geo_speedup_decode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cape_fast_m0 | cape_m0_legacy | 0 | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 | - | - | - |
| cape_fast_m0 | crackle_pins_opt_corrected_m0 | 19 | 3 | 3 | 5388140 | 5422829 | 34689 | 0.9936 | 15 | 4 | 0 | 0.2757 | 5.1087 | 1.0104 |
| safe_refine_e24_m0_zstd9 | safe_archive_m0_zstd9 | 0 | 0 | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 | - | - | - |

