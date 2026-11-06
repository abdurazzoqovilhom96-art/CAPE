# CAPE-Pins — topshirish hujjati (HANDOFF)

Sana: 2026-11-05 (v2/v2.1 holati 6-bo'limda, 2026-11-06). Bu hujjat **haqiqiy holatni** yozadi: nima yaratildi, nima real bajarildi,
nima bloklangan. Raqamlar faqat `results/<run_id>/` dagi tekshirilgan yozuvlardan olingan.

## 1. Qabul qilingan qarorlar (foydalanuvchi bilan)
| Masala | Qaror |
|---|---|
| Toolchain | Windows native, MinGW-w64 g++ 16.2, CMake 4.4.4, Ninja, CPython 3.12 |
| Joylashuv | hammasi `D:\CAPE_PINS` |
| Datasetlar | faqat CREMI A/B/C + Crackle repo namunalari; H01/MICrONS **ruxsat berilmagan** |
| CREMI manbasi | cremi.org ishlamadi → Hugging Face `pytc/tutorial` mirror, har fayl LFS SHA-256 bilan tekshirildi |
| Vulkan SDK | 1.4.363.0 winget orqali o'rnatildi (UAC foydalanuvchi tomonidan tasdiqlandi) |

## 2. Nima yaratildi (ishlaydigan kod)
- **C++ yadro** (`cpp/`): runs, depth-window nomzodlar, xavfsiz qisqartirishlar, komponentlar,
  greedy, lowest-bit bitmask DP, local search, integer dual bound, byte model, explicit serializer,
  upstream bridge (vendor header'larni faqat bitta TU include qiladi). `_crackle_vendor`: pinned
  upstream bir xil kompilyatorda.
- **Python pipeline** (`cape/`): typed config, I/O va kanonik shakl, manifest, adapterlar
  (CAPE, stock PyPI + vendor, Compresso, Neuroglancer, zstd/LZMA/raw, Blosc2, zstd wrapper'lar,
  Volcanite CSGV/CSGV-R CLI), SQLite store, runner/worker (P-core pinning, timeout, RSS watchdog),
  statistika (klaster bootstrap), jadvallar, F01–F11, claim gate, verifier, packaging, recovery.
- **Testlar**: 1208 ta unit/matematik/interop testi + T1–T12 acceptance (`tests_acceptance.json`).
- **Hujjatlar**: `docs/` (format audit, matematika, algoritm, protokol, manbalar, cheklovlar).

## 3. Muhim topilmalar
1. **Upstream Crackle'da jim ma'lumot buzilishi** (PyPI 0.53.0 va pinned SHA): count maydoni
   short-pin konversiyasidan oldingi pin soni bo'yicha o'lchanadi; reproducer 256 voksel noto'g'ri
   tiklanishini ko'rsatadi, xato chiqmaydi (`docs/format_audit.md` F2). CAPE buni tuzatadi.
   Upstream'ga xabar berish — loyiha egasining qarori.
2. `allow_pins=1/2` pins formatini majburlamaydi (F1); `manual_bgcolor` bool'ga qisqaradi (F3).
3. (3)-bayt formulasi upstream bilan aniq mos; fixed-point `q=2^20` natijani o'zgartirmaydi.
4. Kichik croplarda (32×32×16) Crackle konteyner overhead'i tufayli oddiy zstd kichikroq bo'lishi mumkin.

## 4. Real natijalar (2026-11-05 holati)
- **Smoke** `results/20261105T093354Z_smoke_1af40c74`: COMPLETE, verifikatsiya OK, release ZIP bor.
  Real Crackle croplarida (3 ta, 128×128×64, interval *exploratory*) `cape_m0` / `crackle_pins_opt_m0`
  jami bayt nisbati 0.99665, regressiya 0, encode ~2.05× tez. Oracle: 60 komponent, zid holat 0.
  CAPE 270/270 lossless; 16 ta FAILED_LOSSLESS — hammasi stock usullar, adversarial namunada (F2).
- **Acceptance T1–T12**: 12/12 o'tdi (`tests_acceptance.json`).
- **CREMI** yuklandi (mirror, SHA tekshirildi); `data/manifests/pilot.jsonl` (12 crop A),
  `benchmark.jsonl` (24 crop B/C), `width_sensitivity.jsonl` (4 crop Crackle, Z=512 + scale).
- **Volcanite** qurildi (`-include stdint.h` workaround, runtime DLL'lar qo'lda nusxalangan);
  CSGV/CSGV-R adapterlari lossless sinovdan o'tdi (exit-qatorni o'qib, "Press any key" kutishini yopadi).
- **Pilot** `results/20261105T112549Z_pilot_5fc4a006` (CREMI A, development, 12 crop / 6 klaster,
  3588 o'lchov, hammasi OK, verifikatsiya OK): `cape_m0` / `crackle_pins_opt_m0` nisbati 0.99946
  (CI [0.99935, 0.99958]), regressiya 0; encode 3.42× tez (CI 3.19–3.65), decode 1.01×.
  zstd3 bilan yutuq yo'q (1.00003, 2 regressiya). Birinchi urinish (`..._pilot_34435262`)
  `progress.json` WinError 5 dan to'xtagan; tuzatildi (`replace_with_retry`, `_safe` live outputs).
- **Held-out benchmark** `results/20261105T122347Z_all_d1a76eb7` (CREMI B/C, 24 crop / 12 klaster,
  confirmatory, 8688 o'lchov, hammasi OK, `heldout_complete=true`):
  - asosiy juftlik nisbati **0.99868** (yutuq 0.132%, CI [0.99840, 0.99898]); 23/24 namunada kichik,
    1 tasida teng, regressiya 0; encode **3.41× tez** (CI 3.15–3.70), decode 1.00×;
  - wrapper bilan ham saqlanadi: +zstd3 0.9982 (1 regressiya), +zstd9 0.9983 (0); m5: 0.9982;
  - CAPE lossless 2760/2760, sertifikat 2760/2760 valid; oracle 200/200 CP-SAT OPTIMAL, zid holat 0;
    UB/LB gap butun fayl bo'yicha median 0.024%, max 0.079% (label bo'limi bo'yicha 0.42%; jami ≤148 B);
  - **salbiy:** eng kichik umumiy hajm `crackle_flat_m5+zstd9` (288 123 B) — `cape_m5+zstd3`
    288 677 B; CAPE encode `crackle_flat` dan ~5× sekin (59 ms va 11 ms);
  - zamonaviy raqiblar (hajm, Crackle pins_opt'ga nisbatan): CSGV 8.2×, CSGV-R 11.3×,
    Compresso 6.0×, Neuroglancer 20.4× katta. CSGV vaqtlari CLI jarayonini o'z ichiga oladi.
- **Width-sensitivity** `results/20261105T145305Z_development_c1d12b3e` (Crackle repo, 4 crop,
  2 tasida Z=512, 3 repeat, exploratory, 140 o'lchov OK):
  - nisbat 0.99267 (yutuq 0.73%, namuna bo'yicha 0.62–0.90%); label bo'limi 2.1–9.4% kichik;
    UB/LB gap butun fayl bo'yicha median 0.59%, max 0.84% (label bo'limi 6.7%; model ichida ≤0.70% joy);
  - encode: connectomics croplarida 14–68× tez, lekin `crackle_ws` (ko'p label) da CAPE
    **1.6× sekin** (9.1 s va 5.3 s);
  - depth-regime mexanizmi (Z=512) amalda deyarli foyda bermadi: `cape_fixed_depth_width` bilan farq
    0 B (3 namuna) va 12 B (ws), lekin encode vaqtini Z=512 croplarda ~2× oshirdi;
  - exact DP hissasi: `cape_no_exact` 48–1337 B katta.
- Hisobotdagi "Cheklovlar" bo'limi endi namunalarning haqiqiy Z o'lchamidan hosil qilinadi
  (`cape/reporting.py::_depth_regime_note`, `_csgv_note`); uch run hisoboti `rebuild_reports.py`
  bilan qayta qurilgan (o'lchovlar o'zgarmagan). Testlar: 1211 non-acceptance o'tdi.

## 4b. Ochiq qolgan ishlar
- ROI panel C o'chirilgan (`roi_claim_supported=false`); H01/MICrONS mustaqil oila yo'q (RQ6 qisman).
- Depth-regime qidiruvini foyda bermagan joyda o'tkazib yuborish (vaqt uchun) — ochiq g'oya, freeze'dan
  keyin held-out natijaga ta'sir qilmasligi kerak.
- Upstream'ga F2 xatosi haqida xabar berish — loyiha egasining qarori.

## 5. Davom ettirish
```powershell
.\run_experiment.cmd --stage report --latest      # oxirgi run hisobotini qayta qurish
.\run_experiment.cmd --stage all --manifest ".\data\manifests\benchmark.jsonl" --config ".\configs\benchmark.yaml" --resume
```

## 6. v2 va v2.1 holati (2026-11-06)

**v2** (`run_v2.cmd`, holat `analysis/v2_state.json`): 8/8 qadam DONE.
- pilot → freeze → test (24 ko'rilmagan CREMI B/C crop, 6 840 o'lchov) → width (Z=512, 240 o'lchov) → ceiling → audit → report.
- Audit 3/3 run verified (`analysis/v2_audit`). Audit endi har run'ning o'z primary juftligini tekshiradi.
- Hisobot: `analysis/v2_final/V2_YAKUNIY_HISOBOT_UZ.md`.

**v2.1** (`run_v21.cmd`, holat `analysis/v21_state.json`, loglar `analysis/v21_logs/`): 10/10 qadam DONE. Yangi mexanizm qo'shilmagan.
- `impl_mask` (C++ `types.hpp` `ImplBit`: L=1, R=2, H=4, T=8, S=16) v1→v2 o'zgarishlarini alohida yoqadi.
  `tests/test_impl_mask.py`: 32 kombinatsiya baytma-bayt bir xil.
- Tezlashuv atributsiyasi: `analysis/v21_speedup/` (`scripts/speedup_attribution.py`, 2^5 factorial + Shapley).
- Masshtab: `results/20261106T091815Z_development_73f40dd8` (25 nested crop, 600 o'lchov) va stock
  `results/20261106T100701Z_development_9be56574` (≤2^25 voksel); audit `analysis/v21_audit` verified.
- Refine **EKSPERIMENTAL**: `configs/methods.yaml` da `experimental: true`, `role: internal`; `availability.csv` da ustun.
- SAFE/refine taymerlari (`safe_native_ns`, `safe_zstd_ns`, `refine_native_ns`, `refine_flat_zstd_ns`, `refine_setup_ns`,
  `refine_J0_zstd_ns`, `refine_eval_serialize_ns`, `refine_eval_zstd_ns`) faqat vaqtni yozadi, baytni o'zgartirmaydi.
- **SNEMI3D** (CREMI'dan mustaqil; Zenodo 7142003, CC-BY-4.0) yuklandi va md5 bilan tekshirildi:
  - croplar muzlatilgan: `data/manifests/confirm_snemi3d.jsonl` (32 crop, 16 klaster);
  - tasdiqlovchi config: `configs/confirm_snemi3d.yaml`, **ishga tushirilmagan** (faqat foydalanuvchi so'raganda);
  - batafsil: `docs/MUSTAQIL_DATA_SNEMI3D_UZ.md`.
- Hisobot: `analysis/v21_final/V21_HISOBOT_UZ.md` (+ `figures/`, `plot_data/`, `v21_summary.json`).
- Jonli kuzatish: `watch.cmd` (faqat o'qiydi).

**Ochiq:**
- SNEMI3D tasdiqlovchi run'i (`run_all.py --stage benchmark --config configs/confirm_snemi3d.yaml --manifest data/manifests/confirm_snemi3d.jsonl`) — foydalanuvchi ruxsati bilan.
- LNS va boundary-stream to'xtatilgan. H01/MICrONS hamon ruxsatsiz.

```powershell
.\run_v2.cmd --only report     # v2 hisobotini qayta qurish
.\run_v21.cmd --only report    # v2.1 hisobotini qayta qurish
.\watch.cmd                    # jonli holat
```
