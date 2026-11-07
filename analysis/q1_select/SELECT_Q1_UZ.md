# CAPE Q1: development selection (avtomatik, `scripts/q1_develop.py`)

Yaratilgan: 2026-11-07T07:06:10+00:00. Faqat development ma'lumoti (CREMI + Crackle namunalari + scaling_v21).
Run'lar: core `results/20261107T054303Z_development_ee998362`, scale `results/20261107T062104Z_development_93ad9f72`.

## To'g'rilik (E0 = muzlatilgan v3 bilan bayt va sha256)

| method | n | bayt/sha farqi | chiqarilgan | OK emas | lossless=False |
|---|---|---|---|---|---|
| cape_q1_O1_m0 | 61 | 0 | 0 | 0 | 0 |
| cape_q1_O2_m0 | 61 | 0 | 0 | 0 | 0 |
| cape_q1_O3_m0 | 61 | 0 | 0 | 0 | 0 |
| cape_q1_all_m0 | 61 | 0 | 0 | 0 | 0 |
| cape_q1_base_m0 | 61 | 0 | 0 | 0 | 0 |
| cape_q1_noO1_m0 | 61 | 0 | 0 | 0 | 0 |
| cape_q1_noO2_m0 | 61 | 0 | 0 | 0 | 0 |
| cape_q1_noO3_m0 | 61 | 0 | 0 | 0 | 0 |

## Modul qarorlari (leave-one-out: barcha bitlar vs bitta modulsiz)

| modul | qaror | S_T | 95% CI | R_M | 95% CI | yakka bit S_T | yakka bit R_M |
|---|---|---|---|---|---|---|---|
| O1 | **REJECT** | 0.993 | [0.986, 1.004] | 1.000 | [0.999, 1.001] | 0.994 | 0.999 |
| O2 | **ACCEPT** | 1.019 | [0.992, 1.059] | 0.981 | [0.968, 0.990] | 1.022 | 0.981 |
| O3 | **ACCEPT** | 1.048 | [1.038, 1.056] | 0.920 | [0.907, 0.939] | 1.049 | 0.920 |

Tanlangan impl_mask: **6719** (O2, O3).

## Umumiy (development)

- `cape_q1_all_m0__vs__cape_v3frozen_fast_m0`: n=61, S_T 1.073 [1.058, 1.096] (vaqt kamayishi 6.76%), R_M 0.903 [0.895, 0.916], baytlar bir xil: True; >10% sekin: 1; >10% peak: 0
- `cape_q1_base_m0__vs__cape_v3frozen_fast_m0`: n=61, S_T 1.002 [0.998, 1.007] (vaqt kamayishi 0.16%), R_M 1.000 [0.999, 1.001], baytlar bir xil: True; >10% sekin: 1; >10% peak: 0
- `cape_q1_all_m0__vs__cape_q1_base_m0`: n=61, S_T 1.071 [1.057, 1.092] (vaqt kamayishi 6.61%), R_M 0.903 [0.895, 0.916], baytlar bir xil: True; >10% sekin: 1; >10% peak: 0
