# CAPE-Pins v2: modernizatsiya hujjatidan olingan qarorlar

**Manba:** `CAPE_PINS_MODERNIZATSIYA_VA_Q1_DALIL_REJASI_UZ.md` (foydalanuvchi bergan, 2026-11-05).
**Qaror sanasi:** 2026-11-06.
**Foydalanuvchi tanlovi:** P0 + P1; yangi dataset hozircha yuklanmaydi.

Har bir band mavjud xom ma'lumot bilan tekshirildi. Dalillar `analysis/v1_audit/` da, audit esa
`scripts/audit_report.py` bilan qayta yaratiladi.

## 1. Bandlar bo'yicha qarorlar

| # | Hujjat bandi | Qaror | Dalil | Bosqich |
|---|---|---|---|---|
| 1 | Raqamlarni xom CSV'dan audit qilish (§1, §2) | ✅ qabul | `scripts/audit_report.py`: 3 run'ning asosiy raqamlari `summary.json` bilan rel_tol 1e-9 da mos | P0, bajarildi |
| 2 | Mustaqillik: 24 crop = 2 volume (§2.2) | ✅ qabul | audit: `n_source_volumes=2`, `n_clusters=12` | P0, hujjatga yozildi |
| 3 | v2 uchun CREMI B/C endi ko'rilgan ma'lumot (§2.2) | ✅ qabul | — | v2 run'lari `development` |
| 4 | Reduksiya ablation talqini (§2.3) | ✅ qabul, dalil bilan | no_dedup: incidence 1 397 → 275 414, DP o'tishlari 207 → 5 495, exact ulushi 0.902 → 0.880 | P0, hujjatga yozildi |
| 5 | "74%" ifodasi (§2.3) | ✅ qabul | ketma-ket taqqoslashdagi ulush deb qayta yozildi | P0 |
| 6 | Ceiling formulasi G = (L/C)·r (§3) | ✅ qabul | label ulushi CREMI'da median 5.1% | P0 |
| 7 | UB/LB gap talqini (§3) | ✅ qabul, **o'z xatomiz tuzatildi** | `ub_bytes`/`lb_bytes` butun fayl baytlari. CREMI: model ichida ≤148 B (0.03%), label bo'limi gap'i 0.42%. Z=512: ≤0.70% fayl, label bo'limi gap'i 6.7% | P0 |
| 8 | Depth-regime default off (§1, §5.2) | ✅ qabul, yangi metodlarda (narxi o'lchangan) | width: Z=512 da 0–12 B foyda, ~2× vaqt. **v2.1 tuzatish:** scaling'da 5 ta Z=512 crop'da regime'lar 0.64–0.69% gacha kichik (512³: −24 075 B, 3.4 s → 5.8 s); Z ≤ 256 da 0 B | P1: `cape_fast_*` |
| 9 | Reduksiyalarni tezlatish (§5.3) | ✅ bajarildi (v2), **o'lchandi (v2.1)** | `reduction_ns` v1 da encode'ning median 61% i. v2.1 Shapley: CREMI A ×1.76 = kod ×1.37 + algoritmik ×1.28; Crackle ×3.06 = kod ×1.50 + algoritmik ×1.54 + depth-regime ×1.32; 32 `impl_mask` kombinatsiyasi baytma-bayt bir xil (`analysis/v21_speedup`) | P1 |
| 10 | FAST/CERTIFIED ajratish (§5.1) | ✅ amalga oshirildi (2026-11-06, foydalanuvchi talabi) | `certificate: off|regime|all_regimes`; `cape_fast_*` sertifikatsiz, `cape_certified_*` FAST bilan bayt-bayt bir xil stream + barcha depth regime'lar uchun LB; vaqt ustamasi alohida o'lchanadi | P1 |
| 11 | Profiling bosqichlari (§5.1) | ✅ qabul | — | P1 |
| 12 | F2: historical / corrected / current upstream qatorlari (§2.4) | ✅ qabul | F2 reproducer PyPI 0.53.0 va 14b39b1 da bor | P1 |
| 13 | SAFE-ARCHIVE selektori (§4.1) | ✅ faqat engineering baseline sifatida | post-hoc (held-out): zstd9 da flat'dan −0.029/−0.038%; stock pins bilan −0.019/−0.023% | P1 |
| 14 | Entropy-aware refinement (§4.2) | 🧪 **EKSPERIMENTAL** (v2.1, 2026-11-06). Test (24 ko'rilmagan crop): SAFE'dan atigi 42 B (0.013%) kichik, encode vaqti ×2.73 | `cape/refine.py`, `safe_refine_*`: `experimental: true`, `role: internal`; standart konfiguratsiyalarda yo'q, hisobotlarda g'olib yoki "new" deb ko'rsatilmaydi (`availability.csv` da `experimental` ustuni) | eksperimental |
| 15 | Katta komponentlar uchun LNS (§6) | ⏸ to'xtatilgan (v2.1: yangi mexanizm qo'shilmaydi) | Z=512 da model ichida ≤0.70% joy; CREMI'da ≤0.03%. Oldingi "≤0.05%" bahosi noto'g'ri edi | P2 |
| 16 | Boundary-stream pilot (§7) | ⏸ to'xtatilgan (v2.1: yangi mexanizm qo'shilmaydi) | CREMI B/C da faylning ~95% i, CREMI A da ~84% i label bo'limidan tashqarida (crack codes va boshqalar); Crackle mosligi yo'qoladi | foydalanuvchi qarori |
| 17 | Yangi mustaqil holdout (§9) | 🟡 SNEMI3D tayyorlandi (v2.1, foydalanuvchi ruxsati 2026-11-06), tasdiqlovchi run hali o'tkazilmagan | Zenodo 7142003, CC-BY-4.0, md5 tekshirilgan; 32 crop / 16 klaster muzlatilgan (`data/manifests/confirm_snemi3d.jsonl`), oldindan ro'yxatdan o'tgan `configs/confirm_snemi3d.yaml`; `docs/MUSTAQIL_DATA_SNEMI3D_UZ.md`. v2 da: yangi dataset yuklanmagan, o'rniga CREMI B/C ning hech qachon o'lchanmagan z 64–123 croplari (`data/manifests/test_v2_unseen.jsonl`, voksel kesishmasi 0) — volume ichida umumlashuv testi, mustaqil emas | test run |
| 18 | CLI va library-core vaqtini ajratish (§8) | ✅ qabul | CSGV vaqtlari `cli_process_file_to_file` deb belgilangan, hisobotda ogohlantirish bor | bajarilgan |
| 19 | Upstream'ga issue yuborish | ❌ avtorizatsiya yo'q | faqat reproducer va draft | — |

## 2. Audit davomida topilgan qo'shimcha faktlar

- **CSGV-R determinizmi:** takrorlarda bir xil o'lchamli, lekin har xil baytli bitstream chiqadi
  (held-out'da 7 katak, pilotda 2 katak). CAPE va Crackle to'liq deterministik.
- **Asosiy raqamlar mos keldi:** 0.99868, 685 B va 3.4115× aniq qayta chiqdi.

## 3. Q1 uchun 10 bandlik tekshiruv (v1 holati, 2026-11-06; v2/v2.1 yangilanishlari belgilangan)

| # | Talab | Holat | Dalil |
|---|---|---|---|
| 1 | Aniq muammo va 3D label identity | passed | lossless 2760/2760; uint8–uint64; `tests/test_cape_streams.py` |
| 2 | Eng yaqin prior-art bilan formula va kod darajasidagi farq | partial | `docs/related_work_matrix.md`, `docs/format_audit.md`; entropy-aware set cover adabiyoti tekshirilmagan |
| 3 | Formal kafolat qaysi modelga tegishli | passed | `certificate_scope`, `docs/mathematics.md`; gap talqini 2026-11-06 da tuzatildi |
| 4 | Bit-exact roundtrip va buzilgan kirish testlari | partial | roundtrip to'liq; buzilgan kirish uchun alohida test to'plami yo'q (F6: dekoder labels crc'ni tekshirmaydi) |
| 5 | Kuchli, tuzatilgan, matched baseline'lar | partial → yaxshilandi (v2) | bir xil kompilyatorli vendor build, flat+zstd va tuzatilgan stock (`crackle_pins_opt_corrected_*`, v2) bor |
| 6 | CREMI'dan mustaqil test oilasi | **failed → tayyorlanmoqda** | SNEMI3D (sichqon korteksi, Lichtman lab, boshqa annotator) yuklandi va croplar muzlatildi; tasdiqlovchi run foydalanuvchi so'ragandagina o'tkaziladi. Bitta volume = 16 klaster |
| 7 | Encode/decode/RSS/size o'lchovlarining adolatliligi | partial | bitta P-core protokoli; CSGV CLI vaqti teng emas; RSS interpretatorni ham o'z ichiga oladi |
| 8 | Matched ablation | partial → yaxshilandi (v2.1) | bittalab olib tashlash ablation'lari; v2.1 da tezlik uchun to'liq 2^5 factorial + Shapley (`analysis/v21_speedup`); hajm uchun factorial hali yo'q |
| 9 | Deterministik repro, raw data, loglar, versiya, salbiy natijalar | passed | pipeline, `analysis/v1_audit` verified; CREMI SHA bilan qayta yuklanadi (qayta tarqatilmaydi) |
| 10 | Cheklovlar va regressiyalar ochiq | passed | `docs/YUTUQ_VA_YUTQAZISHLAR_UZ.md` |

10 bandning bajarilishi Q1 qabulini kafolatlamaydi. Bu ro'yxat faqat ishning tekshiriluvchanligini
o'lchaydi.
