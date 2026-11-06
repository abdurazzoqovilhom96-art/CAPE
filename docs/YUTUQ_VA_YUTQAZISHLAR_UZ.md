# CAPE-Pins: qaysi qismlar yutdi, qaysilari yutqazdi

**Holat:** 2026-11-05; v2/v2.1 yangilanishlari 2026-11-06 (7-bo'lim). Barcha raqamlar haqiqiy o'lchovlardan olingan. Hech bir namuna yoki o'lchov
olib tashlanmagan.

## Asosiy manbalar

| Run | Ma'lumot | Hajm | Rol |
|---|---|---|---|
| `20261105T122347Z_all_d1a76eb7` | CREMI B/C, 24 crop (≤256×256×64), 12 klaster | 8688 o'lchov, hammasi OK | **asosiy, held-out, confirmatory** |
| `20261105T112549Z_pilot_5fc4a006` | CREMI A, 12 crop, 6 klaster | 3588 o'lchov, hammasi OK | development (pilot) |
| `20261105T145305Z_development_c1d12b3e` | Crackle repo, 4 crop (2 tasida Z=512) | 140 o'lchov, hammasi OK | exploratory (width/scale) |
| `20261105T093354Z_smoke_1af40c74` | sintetik + 3 kichik real crop | — | to'g'rilik va adversarial |

**Asosiy juftlik** freeze'dan oldin belgilangan: `cape_m0` va `crackle_pins_opt_m0` (PyPI
crackle-codec 0.53.0). Agar boshqa joyda aytilmagan bo'lsa, quyidagi raqamlar held-out run'dan.

**Mustaqil audit (2026-11-06).** Asosiy raqamlar xom `results.csv` dan `cape.statistics` dan
foydalanmasdan qayta hisoblandi va har uch run hisoboti bilan aniq mos keldi (`verified=true`).
Natijalar: `analysis/v1_audit/AUDIT_UZ.md`, skript: `scripts/audit_report.py`.

**Mustaqillik cheklovi.**
- Held-out 24 crop faqat **2 ta original volume**dan (CREMI B va C) olingan. 12 klaster shu ikki
  volume ichidagi macroblocklar, nested croplar esa bir klasterda.
- Shuning uchun CI shu ikki volume ichida shartli baho bo'ladi va boshqa acquisition'larga
  umumlashmaydi. 8688 o'lchov yoki 2760 sertifikat mustaqil namuna soni emas.
- "Held-out" maqomi faqat v1 uchun amal qiladi. Bu natijalarga qarab o'zgartirilgan har qanday
  v2 uchun CREMI A/B/C endi ko'rilgan (development) ma'lumot hisoblanadi.

---

## 0. Qisqa xulosa

- **Moslik va to'g'rilik — yutdi.** Wrapper'siz holatda CAPE stock pins encoder'idan hamma 24 namunada
  kichik yoki unga teng fayl beradi va ~3.4× tez kodlaydi. Fayllar o'zgartirilmagan Crackle dekoderi bilan 100% aniq ochiladi.
- **Yutuq juda kichik.** 24 namunada jami 685 bayt, ya'ni 0.13%. Sabab tuzilmaviy: CAPE faqat label
  bo'limini yaxshilaydi, bu bo'lim esa CREMI B/C faylining ~5% i (pilot CREMI A da ~15.6%).
  - **Ceiling formulasi:** label bo'limi r ulushga kichraysa, butun fayl G = (L/C)·r ga kichrayadi.
    L/C = 0.05 bo'lsa, label −10% faylga atigi −0.5% beradi.
  - **Model ichidagi qolgan joy:** CREMI'da yechim isbotlangan quyi chegaradan butun fayl bo'yicha
    ~0.02% uzoqda (24 namunada jami ≤148 B). Label bo'limi bo'yicha bu median 0.42%. Bu chegara faqat
    sertifikatlangan cheklangan modelga tegishli, butun Crackle formati yoki zstd'dan keyingi baytlarga
    tegishli emas.
- **Eng kichik fayl va eng tez encode CAPE'da emas.** Eng kichik umumiy faylni ko'pincha oddiy
  `crackle_flat` + zstd9 beradi (24 dan 18 namunada). Eng tez encode ham `crackle_flat` da
  (CAPE'dan ~5× tez).

---

## 1. ✅ Yutgan qismlar

### 1.1. Lossless va format mosligi — to'liq yutuq

- Held-out'da **2760/2760** CAPE o'lchovi voksel bo'yicha aniq tiklandi, FAILED_LOSSLESS 0.
- Dekodlash o'zgartirilmagan PyPI `crackle-codec 0.53.0` bilan bajariladi. Shunday qilib CAPE fayli
  oddiy Crackle-v1 fayli bo'lib qoladi.
- Pilot, width va smoke run'larida ham CAPE bo'yicha lossless xatosi yo'q.

### 1.2. Upstream xatosida CAPE to'g'ri ishladi (F2)

- Smoke run'dagi adversarial namunada (`syn_count_width_adversarial`) **16 ta FAILED_LOSSLESS** qayd
  etildi. Ularning hammasi stock Crackle usullariga tegishli: count maydoni kengligi noto'g'ri olinadi,
  natijada 256 voksel jim buziladi.
- CAPE shu namunada 270/270 lossless.
- Xato PyPI 0.53.0 da ham, pinned SHA `14b39b1` da ham takrorlanadi. Batafsil: `docs/format_audit.md`.

### 1.3. Hajm: stock pins encoder'iga nisbatan — kichik, lekin ishonchli yutuq

| Juftlik (held-out, 24 namuna) | CAPE kichik / teng / katta | Jami farq | 95% CI (nisbat) |
|---|---|---|---|
| `cape_m0` va `crackle_pins_opt_m0` | 23 / 1 / 0 | **−0.132%** (685 B) | [0.99840, 0.99898] |
| `cape_m0` va `crackle_vendor_pins_opt_m0` (bir xil kompilyator) | 23 / 1 / 0 | −0.132% | bir xil |
| `cape_m5` va `crackle_pins_opt_m5` | 23 / 1 / 0 | −0.183% | [0.99778, 0.99858] |
| `cape_m0+zstd3` va `pins_opt_m0+zstd3` | 23 / 0 / 1 | −0.181% | [0.99717, 0.99912] |
| `cape_m0+zstd9` va `pins_opt_m0+zstd9` | 22 / 2 / 0 | −0.170% | [0.99795, 0.99871] |
| `cape_m0` va `crackle_pins_fast_m0` | 24 / 0 / 0 | −1.828% | — |

- Label bo'limining o'zi **2.66%** kichiklashdi (25 705 → 25 020 B).
- Yutuq CREMI C da kattaroq: B da 0.097%, C da 0.156%.
- Held-out'da zstd qo'shilganda ham yutuq saqlandi. Pilotda esa saqlanmagan edi (§2.8).

### 1.4. Encode tezligi: stock pins encoder'iga nisbatan

| | Qiymat |
|---|---|
| Geometrik tezlashuv, PyPI stock'ga nisbatan | **3.41×**, CI [3.15, 3.70] |
| Bir xil kompilyatorli vendor build'ga nisbatan | ~2.9× (59 ms va 169 ms) |
| Decode tezligi | o'zgarmadi (1.00×) |

### 1.5. Xotira: stock pins encoder'iga nisbatan

- Peak working set mediani: CAPE **88.6 MiB**, stock pins_opt 139.6 MiB. Bu ~37% kam.
- Maksimum: CAPE 125.9 MiB, stock 246.1 MiB.
- Cheklov: bu yangi ishga tushirilgan jarayon peak'i, Python interpretatori xotirasi ham kiradi.

### 1.6. Optimallik sertifikati (cheklangan model doirasida)

- Held-out'dagi **2760/2760** sertifikat mustaqil verifier'dan o'tdi.
- CP-SAT oracle 200 komponentni tekshirdi: 200/200 OPTIMAL, ziddiyat 0.
- UB/LB gap (UB va LB butun fayl baytlari):
  - butun fayl bo'yicha median **0.024%**, max 0.079%;
  - label bo'limi bo'yicha median 0.42%, max 1.25%;
  - 24 namunada model ichida qolgan joy jami ≤148 B.

  Oldingi versiyada bu "label bo'limi gap'i 0.024%" deb noto'g'ri yozilgan edi, 2026-11-06 da
  tuzatildi.
- CREMI'da CC'larning median 90% i (min 74%) aniq DP bilan yechildi.
- Muhim chegara: bu sertifikat butun Crackle formati uchun global optimum degani emas.

### 1.7. Reduksiyalar

- CREMI'da reduksiyadan keyin kandidatlarning median **0.05%** i qoladi. Masalan, bitta namunada
  147 296 kandidatdan 27 tasi qoldi.
- Dedup o'chirilsa encode 3.6× sekinlashadi, dominance o'chirilsa 1.3×.

### 1.8. Ichki bazaviy selektorlarga nisbatan (panel A, label bo'limi bir xil formatda)

`cape_core` dan katta chiqqan baytlar:

| Selektor | Qo'shimcha bayt | Yomonroq namunalar | Encode vaqti |
|---|---|---|---|
| `stock_cover` (upstream tanlovi) | +685 B | 23/24 | 3.2× sekin |
| `weighted_greedy` | +178 B | 22/24 | 1.4× sekin |
| `greedy_local` | +87 B | 19/24 | 10.6× sekin |

### 1.9. Katta hajmlarda yutuq kattaroq (exploratory, 4 namuna)

| Ko'rsatkich | Qiymat |
|---|---|
| Jami yutuq | **0.73%** (namuna bo'yicha 0.62–0.90%), regressiya 0 |
| Label bo'limi | 2.1–9.4% kichik |
| Encode, connectomics croplari | **14–68×** tez (4 namuna o'rtachasi: 3.6 s va 48.2 s) |

### 1.10. Zamonaviy raqiblarga nisbatan hajm

CAPE hamma namunada ulardan kichik:

| Usul | CAPE'ga nisbatan jami hajmi |
|---|---|
| Neuroglancer (b8) | 20.4× katta |
| CSGV-R | 11.3× katta |
| CSGV | 8.2× katta |
| Blosc2 | 7.8× katta |
| Compresso (native) | 6.0× katta |
| zstd9 | 3.4× katta |
| lzma6 | 2.1× katta |

Bu ustunlikning deyarli hammasi **Crackle formatiga** tegishli. CAPE unga atigi 0.13% qo'shadi. Buni
CAPE'ning o'z yutug'i deb ko'rsatib bo'lmaydi.

---

## 2. ❌ Yutqazgan qismlar

### 2.1. Eng kichik umumiy fayl CAPE'da emas

Har bir namunada eng kichik faylni bergan usul:

| Usul | Namunalar soni |
|---|---|
| `crackle_flat_m5+zstd9` | **16** |
| `cape_m5+zstd3` | 5 |
| `cape_m0+zstd9` | 1 |
| `crackle_flat_m0+zstd9` | 1 |
| `crackle_flat_m5+zstd3` | 1 |

CAPE 24 dan atigi **6 namunada** g'olib.

Jami hajmda ham CAPE g'olib emas:
- `crackle_flat_m5+zstd9`: 288 123 B;
- eng yaxshi CAPE (`cape_m5+zstd3`): 288 677 B (+554 B, +0.192%).

Bu ikki usulning har biri o'zining eng yaxshi wrapper'i bilan olingan global taqqoslash. Bir xil
wrapper va Markov tartibidagi paired taqqoslash §2.2 da alohida berilgan. Ikkalasi alohida metrika,
ularni aralashtirmaslik kerak. Namunalar soni bo'yicha g'oliblar va jami bayt farqi ham alohida
metrikalar.

### 2.2. zstd9 bilan oddiy flat format CAPE'dan kichik

| Juftlik | CAPE kichik / teng / katta | CAPE jami farqi |
|---|---|---|
| `cape_m0+zstd9` va `crackle_flat_m0+zstd9` | 5 / 0 / **19** | **+0.148%** |
| `cape_m5+zstd9` va `crackle_flat_m5+zstd9` | 3 / 2 / **19** | **+0.232%** |
| `cape_m5+zstd3` va `crackle_flat_m5+zstd3` | 10 / 0 / 14 | +0.026% |
| `cape_m0+zstd3` va `crackle_flat_m0+zstd3` | 11 / 0 / 13 | −0.071% (deyarli teng) |

Wrapper'siz holatda esa CAPE flat'dan yaxshi: m0 da −0.32%, m5 da −0.44%. Shunga qaramay **3
namunada flat baribir kichikroq**.

### 2.3. Encode tezligi: oddiy usullar CAPE'dan tez

| Usul | Encode, ms | CAPE'ga nisbatan |
|---|---|---|
| zstd3 | 3.7 | ~16× tez |
| crackle_flat_m0 | 11.0 | **~5.4× tez** |
| neuroglancer_b8 | 14.3 | ~4× tez |
| compresso_native | 16.3 | ~3.6× tez |
| blosc2 | 26.0 | ~2.3× tez |
| csgv_rans_b64 (CLI jarayoni bilan) | 54.9 | taxminan teng |
| **cape_m0** | **59.1** | — |

CAPE faqat stock pins encoder'laridan (141–180 ms) va lzma6 dan (251 ms) tez.

### 2.4. Ko'p label'li hajmda CAPE stock'dan sekin

- `crackle_ws_x0_y0_z0_256x256x512` namunasida CAPE stock'dan **1.6× sekin**: 9.1 s va 5.3 s.
- Hajm bo'yicha yutuq (0.62%) shu namunada ham bor.

### 2.5. Depth-regime mexanizmi foyda bermadi

- CREMI'da 0 B. Kutilgan natija, chunki Z=64 ≤ 256.
- Z=512 bo'lgan 2 namunada: 0 B (connectomics) va 12 B (`crackle_ws`). Qolgan 2 namunada Z ≤ 256,
  u yerda mexanizm umuman ishga tushmaydi.
- Shunga qaramay, Z=512 namunalarda encode vaqtini **~2×** oshirdi: 1.8 s → 3.3 s va 4.8 s → 9.1 s.
- **v2.1 tuzatish (2026-11-06, scaling run, 25 nested crop):** bu xulosa umumiy emas. Z=512 bo'lgan 5 crop'da
  depth-regime qidiruvi FAST'dan kichik stream berdi: 64²×512 −93 B, 128²×512 −1 269 B (0.69%),
  256²×512 −5 199 B (0.68%), connectomics 512³ −24 075 B (0.64%), ws 512³ −45 B. Z ≤ 256 bo'lgan 20 crop'da
  farq 0 B. Narxi: 512³ da encode 3.4 s → 5.8 s. FAST bu baytlarni tezlik uchun qurbon qiladi
  (`analysis/v21_final/V21_HISOBOT_UZ.md` §3, `analysis/v21_audit`).

### 2.6. Katta hajmlarda aniq yechim va kafolat zaiflashadi

| Ko'rsatkich | CREMI | Crackle repo croplari (width run, 4 ta) |
|---|---|---|
| Aniq DP bilan yechilgan CC'lar (median) | 90% | **26%** (min 19%) |
| Eng katta komponent | 103 CC | **8 072 CC** |
| UB/LB gap, butun fayl (median) | 0.024% | **0.59%** (max 0.84%) |
| UB/LB gap, label bo'limi (median) | 0.42% | **6.7%** (max 7.1%) |
| Model ichida qolgan joy (jami) | ≤148 B (0.03%) | **≤61 166 B (0.70%)** |

Katta hajmlarda model ichida faylning ~0.7% igacha imkoniyat qolishi mumkin. Bu yuqori chegara: haqiqiy
optimum UB va LB oralig'ida yotadi. Katta komponentlar uchun yaxshiroq qidiruv (LNS) shu sabab P2
nomzodi bo'lib qoladi.

### 2.7. Evristika har doim optimumga yetmaydi

- Optimumi ma'lum bo'lgan evristik komponentlarda optimumga yetganlar: held-out'da 9 dan 7 tasi,
  pilotda 14 dan 11 tasi.
- Ziddiyat yo'q: sertifikat noto'g'ri chiqmadi, lekin bu holatlar optimal emas.

### 2.8. Pilotda zstd3 yutuqni yo'qotdi

- CREMI A da `cape_m0+zstd3` va `pins_opt_m0+zstd3`: nisbat **1.00003**, 2 regressiya.
- Held-out'da bunday bo'lmadi. Natija dataset'ga bog'liq.

### 2.9. Ayrim namunalarda boshqa usullar CAPE'dan kichik

- `compresso_lzma6` 24 dan **2** namunada `cape_m0` dan kichik. Bu ichki lzma'li usul, uni zstd
  wrapper'li CAPE bilan solishtirsak, CAPE ancha kichik (306 806 B va 560 176 B).
- `crackle_flat_m0` 3 namunada `cape_m0` dan kichik.

### 2.10. Xotira va decode: oddiy usullardan yomonroq

- **Xotira mediani:** CAPE 88.6 MiB; flat 76.3, neuroglancer 74.6, zstd3 71.6 MiB.
- **Decode:** CAPE stock Crackle bilan teng (7.2 ms). zstd3 (4.7 ms) va neuroglancer (5.4 ms) dan
  sekin.

---

## 3. Qismlar bo'yicha hissa (held-out ablation, 24 namuna)

Har satrda bitta komponent o'chirilgan. Raqamlar o'sha komponent o'chirilganda `cape_core` dan qancha
yomonlashganini ko'rsatadi. Ular yig'indisi umumiy yutuqqa teng emas.

| Komponent | Saqlagan bayt (jami) | Foyda bergan namunalar | Vaqtga ta'siri | Baho |
|---|---|---|---|---|
| **Bayt-narxli (weighted) maqsad** (stock_cover → weighted_greedy) | **~507 B** (685−178) | 22–23/24 | — | ✅ asosiy manba (~74%) |
| Local search | 79 B | 14/24 | ~+1% | ✅ kichik |
| Aniq DP | 42 B | 17/24 | ~+3% | ✅ kichik |
| Dedup reduksiyasi | 18 B | 7/24 | **3.6× tezlashtiradi** | ✅ asosan tezlik |
| Dominance reduksiyasi | 17 B | 9/24 | 1.3× tezlashtiradi | ✅ asosan tezlik |
| Fon formulasi (8) | 15 B | 4/24 | ~0 | ⚪ juda kichik |
| Dual gate | 0 B | 0/24 | ~3% tezlashtiradi | ⚪ deyarli ta'sirsiz |
| Kengaytirilgan kandidatlar (maximal runs'dan tashqari) | 0 B | 0/24 | ~0 | ❌ foydasiz (bu ma'lumotda) |
| Depth-regime | 0 B (Z=512 da 0–12 B) | 0/24 | Z=512 da ~2× sekin | ❌ foydasiz |

**Halol talqin:**
- **Weighted maqsad.** stock → weighted_greedy → CAPE ketma-ket taqqoslashida farqning ~74% i (507/685 B)
  birinchi qadamda paydo bo'ladi: pin tanlashda haqiqiy bayt narxini hisobga olish. Bu to'liq
  factorial sababiy dekompozitsiya emas, faqat shu ketma-ket taqqoslashdagi ulush.
- **Qolgan qismlar.** Exact DP, local search va sertifikatlar asosan kafolat va ishonch beradi, hajmga
  qo'shgan hissasi jami ~180 B.
- **Reduksiyalar o'z-o'zidan bayt tejamaydi.** Xavfsiz reduksiyalar aniq modelda optimumni
  o'zgartirmaydi; buni `test_reduction_optimum` brute force va CP-SAT bilan tekshiradi. Dedup yoki
  dominance o'chirilganda chiqqan +18/+17 B boshqa sababdan:
  - incidence keskin o'sadi (median 1 397 → 275 414 yozuv);
  - DP o'tishlari 207 → 5 495 ga ko'tarilib byudjetga uriladi;
  - aniq yechilgan CC ulushi 0.902 → 0.880 ga tushadi va ko'proq komponent evristikaga o'tadi.

  Demak bu farq byudjet va qidiruv yo'liga bog'liq, reduksiyaning o'zi "18 B siqish" bermaydi.

---

## 4. ⚪ Sinalmagan yoki neytral qismlar

- **ROI paneli (C)** o'chirilgan, `roi_claim_supported=false`.
- **H01 va MICrONS** yuklanmagan (foydalanuvchi qarori). Mustaqil test oilasi yo'q, RQ6 qisman.
- **CREMI croplari kichik** (≤256×256×64). Gigavoksel yoki to'liq hajmlar sinalmagan.
- **Width/scale run** 4 namunadan iborat, shuning uchun exploratory. Confirmatory xulosa qilib bo'lmaydi.
- **CSGV/CSGV-R vaqtlari** Volcanite CLI jarayoni orqali o'lchangan: jarayonni ishga tushirish va fayl
  I/O ham kiradi. Tezlik bo'yicha solishtirish adolatli emas, faqat hajm solishtirmasi to'g'ri.
- **Track:** faqat Windows (MinGW g++). Linux track bajarilmagan.
- **Determinizm:**
  - CAPE va barcha Crackle qatorlarining takrorlari bayt-bayt bir xil chiqdi;
  - CSGV-R (Volcanite) esa bir xil o'lchamli, lekin har safar boshqa baytli bitstream beradi:
    held-out'da 7 katak, pilotda 2 katak. Hammasi lossless, o'lcham deterministik.

---

## 5. Umumiy baho

| Yo'nalish | Natija |
|---|---|
| Crackle-v1 bilan moslik, lossless | ✅ to'liq |
| Stock pins'dan kichik | ✅ ishonchli, lekin 0.13% (CREMI) / 0.73% (Z=512) |
| Stock pins'dan tez | ✅ 3.4× (CREMI); ❌ ko'p label'li hajmda 1.6× sekin |
| Eng kichik umumiy fayl | ❌ `crackle_flat` + zstd9 (18/24 namuna) |
| Eng tez encode | ❌ `crackle_flat` va oddiy kompressorlar |
| Optimallik kafolati | ✅ CREMI'da gap ~0.02%; ⚠ katta hajmda 0.6–0.8% |
| Upstream xatosini topish (F2) | ✅ jim buzilish topildi; CAPE undan xoli |
| Zamonaviy raqiblardan kichik | ✅, lekin bu Crackle formatining xizmati |

**Ilmiy ahamiyat:** metodologiya va takrorlanuvchanlik kuchli. Ammo Crackle-v1 mosligi doirasida yutuq
tuzilmaviy jihatdan cheklangan:
- label bo'limi CREMI B/C faylining ~5% i (CREMI A da ~15.6%);
- CREMI'da CAPE isbotlangan chegaraga deyarli yetgan (≤0.03% joy); katta Z=512 hajmlarda esa model ichida ~0.7% gacha joy qolgan.

Shuning uchun hozirgi natija Q1 jurnal uchun yetarli emas. Kuchli tomonlarimiz: 3.4× tez va
kafolatlangan pin tanlash, F2 jim buzilish xatosining topilishi, qat'iy va halol benchmark. Bular
qisqa metod yoki software maqolasi va upstream hissasi uchun mos.

---

## 7. v2 / v2.1 yangilanishlari (2026-11-06)

Manba: `analysis/v2_final/V2_YAKUNIY_HISOBOT_UZ.md`, `analysis/v21_final/V21_HISOBOT_UZ.md`,
`analysis/v21_speedup/`, `analysis/v21_audit` (verified). v2.1 da yangi mexanizm qo'shilmagan.

### ✅ Yutganlar
- **v1 → v2 tezlashuvi, baytlar o'zgarmagan.** 5 ta implementatsiya o'zgarishining 32 kombinatsiyasi baytma-bayt
  bir xil (golden + 16 o'lchov namunasi), decode aniq. Shapley dekompozitsiyasi (log-vaqt, qoldiq 1e-16):
  - CREMI A (12 crop): jami ×1.76 [1.67, 1.86] = kod ×1.37 (55%) + algoritmik ×1.28 (44%) + depth-regime ×1.00;
  - Crackle (4 katta crop): jami ×3.06 [2.04, 4.59] = kod ×1.50 (36%) + algoritmik ×1.54 (39%) + depth-regime ×1.32 (25%).
  Algoritmik = sort o'rniga hash-jadval guruhlash (T) va faqat erishiladigan DP holatlari (S); yangi qisqartirish qoidasi yo'q.
- **Tuzatilgan stock'dan kichik va tez (scaling, 19 crop ≤ 2^25 voksel):** nisbat 0.99360, 15 kichik / 4 teng / 0 katta,
  encode ×5.1 tez (geo). Z=512 width: 0.73% kichik, ×29 tez (4 crop, exploratory).
- **Xotira:** FAST peak legacy'dan ~7% kam (512²×256: 1 070 → 999 MiB); stock'dan ~2× kam.

### ❌ Yutqazganlar / cheklovlar
- **Refinement amalda foydasiz → EKSPERIMENTAL.** Test: SAFE'dan 42 B (0.013%) kichik, encode ×2.73.
  Scaling: 2 758 B (0.010%), encode ×3.6; refine vaqtining asosiy qismi Python serializatsiyasi (median 453 ms), zstd emas (64 ms).
- **FAST Z=512 da depth-regime baytlarini yo'qotadi:** 5 crop'da 0.64–0.69% gacha katta (2.5-bo'limdagi tuzatish).
- **Masshtab chiziqlidan yomonroq:** encode ∝ V^1.07 (CREMI), V^1.25 (connectomics), V^1.12 (ws); connectomics'da
  XY^1.24·Z^1.32. Yechish vaqti eng yirik komponent bilan V^1.4–2.9 tezlikda o'sadi (512³ da 10 369 CC, 540 ms).
  Stock: V^1.87 (connectomics).
- **Xotira kirishdan 2.3–3.5× katta:** 1250²×125 CREMI'da 3.4 GiB, ws 512³ da 3.4 GiB.
- **flat hali ham ~3–4× tez** (scaling median 42.7 ms va 127.9 ms).
- **Mustaqil test oilasi hali o'lchanmagan:** SNEMI3D tayyorlandi (32 crop, 16 klaster), tasdiqlovchi run yo'q.

---

## 6. Fayllar

| Hujjat | Yo'l |
|---|---|
| Held-out hisobot | `results/20261105T122347Z_all_d1a76eb7/15_reports/final_report_UZ.md` |
| Held-out ablation | `results/20261105T122347Z_all_d1a76eb7/08_ablations/ablation_comparison.csv` |
| Komponent statistikasi | `results/20261105T122347Z_all_d1a76eb7/07_component_stats/component_stats.csv` |
| Xotira jadvali | `results/20261105T122347Z_all_d1a76eb7/12_tables/memory.csv` |
| Pilot hisobot | `results/20261105T112549Z_pilot_5fc4a006/15_reports/final_report_UZ.md` |
| Width/scale hisobot | `results/20261105T145305Z_development_c1d12b3e/15_reports/final_report_UZ.md` |
| Format auditi (F1–F9) | `docs/format_audit.md` |
| v2 yakuniy hisobot | `analysis/v2_final/V2_YAKUNIY_HISOBOT_UZ.md` |
| v2.1 hisobot | `analysis/v21_final/V21_HISOBOT_UZ.md` |
| Tezlashuv atributsiyasi | `analysis/v21_speedup/` |
| **Halol yakuniy tahlil va baho (v1+v2+v2.1)** | `docs/HALOL_TAHLIL_VA_BAHO_UZ.md` |
