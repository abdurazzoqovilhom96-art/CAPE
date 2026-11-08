# CAPE Q1: yakuniy audit va xulosa

Run ID: `q1_20261107T072741Z` · Yaratilgan: 2026-11-07T18:48:11+00:00 · Eθ impl_mask 6719 (qabul qilingan Q1 bitlari: O2, O3) · source `f3fa7321f96a`

**Texnik bajarilish: COMPLETE.** **Ilmiy tayyorlik: tayyorlash mumkin (cheklangan da'vo bilan); muhim dalil yetishmaydi: mustaqil acquisition'lar soni.**
Texnik COMPLETE Q1 jurnal qabuli yoki 10/10 degani emas. Jurnal tanlanmagan, shuning uchun format, qamrov va kvartil talablari tekshirilmagan. Maqola hech qayerga yuborilmadi.

## 1. Tekshirilgan versiyalar va bosqichlar

- E0 (muzlatilgan v3) sha256 `f1029e19992af218`; v2.1 `39dca94b1eeb1c59`; Eθ `4bf56afc7259c275`.
- Bosqichlar: audit → tuzatishlar → development (seen data) → freeze → yangi to'liq run → raw audit → tahlil → paket → validator.

| run | holat | katalog |
|---|---|---|
| j0126 | DONE | `results/20261107T072741Z_all_881c7eae` |
| snemi | DONE | `results/20261107T112030Z_all_a3fe0095` |
| hemibrain | DONE | `results/20261107T144808Z_all_dc44db69` |
| scale | DONE | `results/20261107T150702Z_all_92c1c67b` |
| scale_stock | DONE | `results/20261107T151528Z_all_82795edb` |
| profile_j0126 | DONE | `results/20261107T153143Z_all_f3f993b8` |
| profile_hemibrain | DONE | `results/20261107T153444Z_all_f0ef67fb` |
| profile_scale | DONE | `results/20261107T153649Z_all_0795b28c` |

## 2. Muammolar: avval → tuzatish → dalil → qolgan cheklov

| ID | muammo | tuzatish | holat | dalil |
|---|---|---|---|---|
| I01 | 1.343x reported without the time-reduction form | generator prints 100(1-1/S_T) | FIXED (generator) | audit/claims_recheck.csv |
| I02 | equal bytes could be read as a compression result | byte-equality table; C1 = time and memory only | FIXED (generator) | audit/claims_recheck.csv |
| I03 | 12.9x vs stock attributed to new modules | C1/C2/C3 separated | FIXED (generator) | audit/claims_recheck.csv |
| I04 | matched greedy must stay in the main table | T03 C3 rows include it | FIXED | audit/claims_recheck.csv |
| I05 | 12 invalid v2.1 certificate rows (w_D compaction) | v3 scaled-dual bound; propagation audited (stream bytes unaffected) | FIXED in v3; AUDITED | audit/certificate_propagation.csv |
| I06 | '5 volumes' wording | '1 acquisition: full + 4 subvolumes' | FIXED (generator) | audit/claims_recheck.csv |
| I07 | stock 53.96x scope | quadrants only; full volume N/A | FIXED (generator) | audit/claims_recheck.csv |
| I08 | M5a label | statistically positive, practical gate unmet | FIXED (generator) | audit/claims_recheck.csv |
| I09 | M3a mechanism claim with 0 prunes | claim withdrawn | FIXED (ledger) | audit/claims_recheck.csv |
| I10 | SAFE scale CI crosses 0 | no superiority/equivalence claim | FIXED (generator) | audit/claims_recheck.csv |
| I11 | memory = encode+decode peak | encode-inclusive peak is primary; e2e apart | FIXED (protocol) | audit/claims_recheck.csv |
| I12 | 'enc ms' aggregation unnamed | aggregates named | FIXED (generator) | audit/claims_recheck.csv |
| I13 | neuroglancer uint16 unsupported | amended explicit uint32 widening track | NOT FIXED in the final run (704/704 uint8/uint16 rows not SUCCESS: the runner checks the class-level supported_dtypes before the adapter, so the widening path was never reached); FIXED by the post-run AMENDMENT run results/20261107T183016Z_all_296f78da after the runner fix: 704/704 uint16 rows SUCCESS, all lossless | audit/claims_recheck.csv |
| I14 | SAFE guarantee scope | checked at stored-file level, same zstd level | VERIFIED | audit/claims_recheck.csv A14 |
| I15 | Q8 verdict / status-count bug in report_v3 | Q1 generator separates statuses | FIXED (generator) | audit/claims_recheck.csv |
| I16 | M5b memory judged on e2e peak median | encode-inclusive peak, geo ratio with CI | FIXED (protocol) | audit/claims_recheck.csv |
| I17 | SNEMI3D seen while designing Eθ | j0126 is the primary C1 test | DISCLOSED | audit/claims_recheck.csv |
| I18 | tools/*.py not covered by the source hash | tools/*.py added to SOURCE_GLOBS before the Q1 freeze | FIXED | cape/provenance.py |
| I19 | first Q1 dev attempt stopped in TESTED (frozen v3 module loaded in-process by test_adapters) | frozen v3 adapter tested in its own process | FIXED | tests/test_q1_invariants.py |

### Yakuniy run'dan keyin topilgan holatlar (xom qatorlar va git'dan hisoblangan; `audit/post_run_findings.json`)

- `neuroglancer_b8_u32` (snemi): uint8/uint16 qatorlar 704, SUCCESS 0, boshqa statuslar {"UNSUPPORTED_DTYPE": 704}. Qatordagi sabab: neuroglancer_b8_u32 supports ['uint32', 'uint64']; input is uint16 (no silent cast). C1/C2 ga ta'siri yo'q; bu C3 baseline final run'da uint16 ma'lumotda yo'q (uint64 da native yo'l bilan bir xil).
- AMENDMENT `I13_neuroglancer_b8_u32_snemi` (`results/20261107T183016Z_all_296f78da`, runner tuzatilgandan keyin): `neuroglancer_b8_u32` uint16 qatorlari 704/704 SUCCESS, lossless True. Eθ bilan bir xil 32 crop'da (boshqa run, bir xil protokol): Eθ 90.39% kichik, S_T 0.523. Final qatorlarga qo'shilmagan (T09).
- Interferensiya oynasi 2026-11-07T07:28:50Z – 2026-11-07T07:31:35Z (the agent re-rendered the smoke-test article package (CPU-heavy analysis) after the j0126 timing had started; window = benchmark start to the last file the rebuild wrote (07:31:31Z)): j0126 da 79/12672 qator; C1 vaqt qatorlari 3/462, C1 xotira qatorlari 0; S_T barcha qatorlar bilan 1.0739, oynadagi qatorlarsiz 1.0741.
- j0126 klaster amendment'i (registered_33): 33 klaster; S_T 1.0739 [1.0650, 1.0832], R_M 0.9154 [0.9112, 0.9192]. Ustma-ust juftlar: 2. Ro'yxatdan o'tgan 33 klasterli natija o'zgarmaydi.
- j0126 klaster amendment'i (overlap_merged): 31 klaster; S_T 1.0739 [1.0653, 1.0833], R_M 0.9154 [0.9112, 0.9191]. 
- j0126 klaster amendment'i (gap_le_150_merged): 26 klaster; S_T 1.0739 [1.0645, 1.0837], R_M 0.9154 [0.9111, 0.9194]. 
- Freeze commit `0608c60` dan keyingi commit'lar: 5927ee9 2026-11-07T23:30:08+05:00 Q1b Stage 0: O1 shown as rejected in methods/pseudocode/prior-art (validator checks pseudocode bits); j0126 cluster amendment (overlap-merged + proximity sensitivity, registered result kept); runner dtype gate asks the adapter instance (I13) with tests; amendment config for neuroglancer_b8_u32 on SNEMI; 322936d 2026-11-07T23:25:19+05:00 B protocol (pre-registered before any prototype result): dominance-completeness theorem, pricing/certificate prechecks, column-generation prototype with gates G1/G2, Stage 0 fixes of the Q1 package; bea418c 2026-11-07T20:52:21+05:00 HANDOFF: Q1 final run, package, open issues; 6867a2b 2026-11-07T20:50:56+05:00 Q1 report: runner-written configs/frozen snapshots are not listed as uncommitted code; full first reason text; 7802bfd 2026-11-07T20:49:30+05:00 Q1 analysis-only post-run fixes from the visual review and raw-row audit: F03 labels/z-order, F04 panel roles, F05 stock on the 4 subvolumes, F08 colours; computed post-run findings (amended neuroglancer track coverage, interference window sensitivity, post-freeze commits) in the final report; efbe2d5 2026-11-07T20:40:49+05:00 Q1 analysis-only post-freeze fixes found by the smoke test (figures layout, fresh-process stage profile, validator integer formatting, manifest self entry); no measurement code changed. O'zgargan fayllar: cape/runner.py, configs/q1b_amend_ng_snemi.yaml, docs/CAPE_Q1_B_YAGONA_AGENT_PROMPT_UZ.md, docs/HANDOFF_UZ.md, docs/q1/mathematics/q1_output_preserving.md, scripts/q1_common.py, tests/test_q1b_runner_dtype.py, tools/q1_analysis.py, tools/q1_article.py, tools/q1_figs.py, tools/validate_article_package.py. O'lchov kodi (cape/, cpp/, run_all.py, configs/, snapshots/, vendor/, manifestlar) o'zgarganmi: True. Commit qilinmagan kod fayllari: tools/q1_article.py.

## 3. Yangi o'lchovlar (yangi run; eski frozen natijalar ishlatilmagan)

| dataset | taqqoslash | n | S_T [95% CI] | R_M [95% CI] | hajm farqi | W/T/L |
|---|---|---|---|---|---|---|
| j0126 | C1 Eθ vs E0 | 33 | 1.074 [1.065, 1.083] | 0.915 [0.911, 0.919] | 0.0000% | 0/33/0 |
| j0126 | build drift | 33 | 1.004 [0.998, 1.011] | 0.999 [0.998, 1.001] | 0.0000% | 0/33/0 |
| j0126 | C2 vs v2.1 | 33 | 1.315 [1.295, 1.334] | 0.842 [0.835, 0.848] | 0.0000% | 0/33/0 |
| j0126 | C3 weighted greedy | 33 | 0.988 [0.981, 0.995] | 1.000 [0.999, 1.001] | 0.0368% | 33/0/0 |
| j0126 | C3 corrected stock | 33 | 7.054 [6.361, 7.892] | 0.411 [0.401, 0.423] | 0.1216% | 33/0/0 |
| j0126 | C3 flat | 33 | 0.501 [0.486, 0.516] | 1.224 [1.209, 1.240] | 3.0911% | 33/0/0 |
| snemi | C1 Eθ vs E0 | 32 | 1.079 [1.067, 1.091] | 0.893 [0.885, 0.900] | 0.0000% | 0/32/0 |
| snemi | build drift | 32 | 0.993 [0.985, 1.000] | 1.001 [0.999, 1.002] | 0.0000% | 0/32/0 |
| snemi | C2 vs v2.1 | 32 | 1.457 [1.438, 1.477] | 0.799 [0.792, 0.807] | 0.0000% | 0/32/0 |
| snemi | C3 weighted greedy | 32 | 0.998 [0.992, 1.004] | 1.000 [0.999, 1.001] | 0.0343% | 32/0/0 |
| snemi | C3 corrected stock | 32 | 14.207 [12.881, 15.518] | 0.373 [0.359, 0.390] | 0.1199% | 32/0/0 |
| snemi | C3 flat | 32 | 0.537 [0.519, 0.558] | 1.259 [1.243, 1.274] | 5.4001% | 32/0/0 |
| hemibrain | C1 Eθ vs E0 | 4 | 1.066 [1.009, 1.124] | 0.859 [0.858, 0.860] | 0.0000% | 0/4/0 |
| hemibrain | build drift | 4 | 1.025 [0.988, 1.076] | 1.000 [0.999, 1.000] | 0.0000% | 0/4/0 |
| hemibrain | C2 vs v2.1 | 4 | 1.324 [1.279, 1.370] | 0.732 [0.728, 0.737] | 0.0000% | 0/4/0 |
| hemibrain | C3 weighted greedy | 4 | 0.893 [0.877, 0.908] | 1.000 [1.000, 1.000] | 0.1062% | 4/0/0 |
| hemibrain | C3 corrected stock | NA | NA | NA | NA | NA |
| hemibrain | C3 flat | 4 | 0.431 [0.423, 0.441] | 1.395 [1.387, 1.405] | 8.2691% | 4/0/0 |

Hukmlar (oldindan belgilangan maqsadlar: S_T ≥ 1.05, R_M ≤ 0.95; maqsad va statistik dalil alohida):

- **j0126**: bayt tengligi 100.0%; tezlik maqsadi True (CI 1 dan yuqori: True); xotira maqsadi True (CI 1 dan past: True); eng yomon namuna: tezlik 1.022 (j0126_z3710_y8691_x2889_150x150x150), xotira 0.930.
- **snemi**: bayt tengligi 100.0%; tezlik maqsadi True (CI 1 dan yuqori: True); xotira maqsadi True (CI 1 dan past: True); eng yomon namuna: tezlik 1.002 (snemi3d_x256_y768_z0_128x128x64), xotira 0.955.
- **hemibrain**: bayt tengligi 100.0%; tezlik maqsadi True (CI 1 dan yuqori: True); xotira maqsadi True (CI 1 dan past: True); eng yomon namuna: tezlik 0.985 (hemibrain_x20096_y17792_z13312_512x512x256), xotira 0.860.
- Asosiy oila (Holm): {"H1_C1_speed_j0126": 0.0002, "H2_C1_memory_j0126": 0.0002}.

## 4. Modullar: nima yutdi va nima yutqazdi

- O1: development qarori **REJECT** (S_T 0.993 [0.986, 1.004], R_M 1.000 [0.999, 1.001]); sabab: speed CI lower 0.986 > 1: False; memory CI upper 1.001 < 1: False; other axis within 2% (S_T 0.993 >= 0.98, R_M 1.000 <= 1.02): True.
- O2: development qarori **ACCEPT** (S_T 1.019 [0.992, 1.059], R_M 0.981 [0.968, 0.990]); sabab: speed CI lower 0.992 > 1: False; memory CI upper 0.990 < 1: True; other axis within 2% (S_T 1.019 >= 0.98, R_M 0.981 <= 1.02): True.
- O3: development qarori **ACCEPT** (S_T 1.048 [1.038, 1.056], R_M 0.920 [0.907, 0.939]); sabab: speed CI lower 1.038 > 1: True; memory CI upper 0.939 < 1: True; other axis within 2% (S_T 1.048 >= 0.98, R_M 0.920 <= 1.02): True.
- final j0126: Eθ vs cape_q1_noM1a_m0: S_T 1.140 [1.127, 1.153], R_M 0.920 [0.914, 0.927].
- final j0126: Eθ vs cape_q1_noM5b_m0: S_T 1.177 [1.161, 1.193], R_M 0.863 [0.854, 0.871].
- final j0126: Eθ vs cape_q1_noO2f_m0: S_T 1.018 [1.009, 1.026], R_M 0.996 [0.992, 1.000].
- final j0126: Eθ vs cape_q1_noO3f_m0: S_T 1.059 [1.048, 1.071], R_M 0.919 [0.915, 0.922].
- final snemi: Eθ vs cape_q1_noM1a_m0: S_T 1.266 [1.249, 1.282], R_M 0.857 [0.847, 0.869].
- final snemi: Eθ vs cape_q1_noM5b_m0: S_T 1.187 [1.178, 1.197], R_M 0.885 [0.874, 0.895].
- final snemi: Eθ vs cape_q1_noO2f_m0: S_T 1.054 [1.044, 1.064], R_M 0.969 [0.960, 0.977].
- final snemi: Eθ vs cape_q1_noO3f_m0: S_T 1.031 [1.021, 1.040], R_M 0.922 [0.921, 0.923].
- final hemibrain: Eθ vs cape_q1_noM1a_m0: S_T 1.079 [1.067, 1.091], R_M 0.961 [0.949, 0.977].
- final hemibrain: Eθ vs cape_q1_noM5b_m0: S_T 1.213 [1.180, 1.246], R_M 0.732 [0.728, 0.737].
- final hemibrain: Eθ vs cape_q1_noO2f_m0: S_T 0.972 [0.949, 0.995], R_M 1.000 [1.000, 1.000].
- final hemibrain: Eθ vs cape_q1_noO3f_m0: S_T 1.064 [1.044, 1.091], R_M 0.859 [0.858, 0.860].
- final scale: Eθ vs cape_q1_noM1a_m0: S_T 1.293 [1.258, 1.337], R_M 0.672 [0.650, 0.698].
- final scale: Eθ vs cape_q1_noM5b_m0: S_T 1.256 [1.249, 1.266], R_M 0.719 [0.704, 0.734].
- final scale: Eθ vs cape_q1_noO2f_m0: S_T 1.025 [1.015, 1.041], R_M 0.966 [0.902, 1.001].
- final scale: Eθ vs cape_q1_noO3f_m0: S_T 1.050 [1.043, 1.055], R_M 0.805 [0.796, 0.813].
- Run-based CC labeling (birinchi O1 urinish): baytlar bir xil, lekin fragmentlangan (ws) slice'larda ~40% sekin bo'lgani uchun o'lchov panelidan oldin rad etildi.

## 5. Yangilik, engineering hissasi va isbotlanmagan taxminlar

- **Engineering hissasi:** chiqishni saqlovchi bufer va allokatsiya o'zgarishlari (O1/O2/O3). Ularning ekvivalentlik isbotlari `mathematics/` da, muzlatilgan binari bilan bayt tengligi esa har namunada tekshirilgan.
- **Yangilik:** yangi siqish algoritmi yo'q. Inverted index va dedup g'oyalari ma'lum (`methods/CONTRIBUTION_AND_PRIOR_ART_EN.md`).
- **Isbotlanmagan:** boshqa platformalar, ko'p thread va boshqa acquisition'larga umumlashuv.

## 6. Baholar (dalil manzili bilan)

| mezon | baho | dalil |
|---|---|---|
| matematik to'g'rilik | PASS | lossless xato 0; bayt tengligi: True; `mathematics/`, `raw_results/raw_audit.json` |
| baseline adolati | PASS | bir xil worker/thread/pinning; matched greedy bir xil infratuzilmada; T02/T03 |
| tashqi validatsiya | PARTIAL | yangi acquisition'lar: j0126 (asosiy), hemibrain (tavsifiy); T01 |
| reproduksiya | PASS | `reproducibility/REPRODUCE.md`, freeze hash'lari, `--mode render` |
| amaliy foyda | PASS | C1 j0126: S_T 1.074, R_M 0.915 |

## 7. Maqolada yozish mumkin va mumkin bo'lmagan da'volar

- [SUPPORTED] Eθ writes byte-identical streams to frozen v3 E0 on 100.0% of j0126 samples — doira: j0126 (33 volumes); also SNEMI3D, hemibrain; cheklov: implementation equivalence, not compression
- [SUPPORTED] Eθ encodes faster than E0 (j0126 S_T 1.074 [1.065, 1.083]; time reduction 6.9%) — doira: one new acquisition (j0126), 1 thread, Windows/MinGW, i7-13700F; cheklov: target 1.05 reached: True
- [SUPPORTED] Eθ needs less encode-inclusive peak memory than E0 (j0126 R_M 0.915 [0.911, 0.919]) — doira: process peak incl. Python and input; one new acquisition; cheklov: target 0.95 reached: True
- [CONDITIONAL] C1 on snemi: S_T 1.079 [1.067, 1.091], R_M 0.893 [0.885, 0.900] — doira: previously seen (SNEMI3D); cheklov: not independent
- [CONDITIONAL] C1 on hemibrain: S_T 1.066 [1.009, 1.124], R_M 0.859 [0.858, 0.860] — doira: descriptive (4 cutouts, one acquisition); cheklov: CI = timing variation only
- [CONDITIONAL] CAPE selection vs matched weighted greedy (same infrastructure): 0.0368% smaller [0.0317, 0.0416], S_T 0.988 — doira: j0126; cheklov: small size gain; not a Q1 change
- [CONDITIONAL] vs corrected stock pins: 0.1216% smaller, S_T 7.054 — doira: j0126; stock = pinned upstream + count-width fix; cheklov: whole CAPE vs stock; mostly v2.1/v3 work
- [UNSUPPORTED] the Q1 mechanisms are new algorithms — doira: -; cheklov: buffer/allocation engineering with proofs of output equivalence
- [UNSUPPORTED] results generalize to all connectomics label data — doira: -; cheklov: three acquisitions in total; one new primary
- [SUPPORTED] certificates are valid lower bounds of the restricted model — doira: restricted model; cheklov: not global, no zstd bound
- [UNSUPPORTED] Q1 acceptance / 10-out-of-10 — doira: -; cheklov: never derived automatically

## 8. Qolgan kamchiliklar va eng kichik keyingi tajriba

- Mustaqil acquisition'lar soni kam. Eng kichik keyingi qadam: yana 1–2 ta ochiq, real neyron label hajmi (foydalanuvchi ruxsati bilan) va xuddi shu muzlatilgan protokol.
- Ikkinchi platformada (Linux/GCC yoki boshqa CPU) C1 ni qayta o'lchash.
- Qo'shimcha test yutuq kafolati emas.

## 9. Artefaktlar va qayta yaratish

- Indeks: `artifact_manifest.csv`; da'volar: `claims_ledger.csv`; jadvallar: `tables/`; grafiklar: `figures/`.
- Qayta yaratish: `.venv\Scripts\python.exe tools\q1_pipeline.py --mode render --run-id q1_20261107T072741Z --output "maqola uchun"` (o'lchovsiz). To'liq yangi run: `--mode full --fresh-run`.

## 10. Validator

Natija: **PASS** (`checks/VALIDATION_UZ.md`).
