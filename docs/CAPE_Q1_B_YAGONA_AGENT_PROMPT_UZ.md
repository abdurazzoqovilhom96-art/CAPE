# CAPE Q1, B yo'nalishi: candidate-qamrov teoremasi va implicit pricing (column generation) prototipi

**Yagona agent prompti, versiya 3 (2026-11-07).** U ikki manbadan tuzildi:
- foydalanuvchi bergan B rejasi ("candidate-qamrov teoremasi → ixcham hisoblash");
- `CAPE_Q1_YAGONA_AGENT_PROMPT_UZ_1.md` (v2) dagi bajarish protokoli.

Barcha boshlang'ich faktlar 2026-11-07 da xom natijalar va source'dan qayta tekshirilgan (2-bo'lim). Hujjat tadqiqot protokoli. U ijobiy natija, ilmiy yangilik yoki Q1 qabulini va'da qilmaydi.

## 0. Ruxsat va doira

- **Ruxsat.** Foydalanuvchi 2026-11-07 da B yo'nalishini tanladi va quyidagilarga ruxsat berdi: shu hujjat bo'yicha kod yozish, 0-bosqich tuzatishlari, uchta oldindan tekshiruv, development prototipi, gate, natijalar paketini alohida papkada avtomatik yaratish. Oddiy bosqichlar uchun qayta ruxsat so'ralmaydi.
- **Ruxsatga kirmaydi:**
  - maqolani jurnalga yuborish, natijalarni tashqariga e'lon qilish, `git push`;
  - yangi pullik xizmat yoki noma'lum litsenziyali manba;
  - H01/MICrONS yuklash (2026-11-05 qarori). Bu rejada umuman yangi ma'lumot yuklanmaydi;
  - native LP solver'ni vendor qilish yoki C++ encoder'ga katta yangi modul qo'shish (11-bo'lim). Bu alohida qaror.
- **Loyiha.** `D:\CAPE_PINS`. Yangi branch `q1b` `q1` HEAD'idan ochiladi. Eski run'lar, freeze'lar, `.pyd` fayllar va hisobotlar o'chirilmaydi. Hozirgi `maqola uchun/` ga faqat 0-bosqich render orqali tegiladi: `place()` eski nusxani arxivlaydi.
- **Timing qoidasi** (Q1 dagi 07:28–07:31 xatosidan saboq). Vaqt yoki xotira o'lchovi ketayotganda agentning o'zi ham CPU-og'ir ish qilmaydi: render, tahlil, test, build. O'lchov tugaguncha kutadi.
- AGENTS.md qoidalari to'liq amal qiladi: raqam uydirilmaydi, regressiya yashirilmaydi, primary pair o'zgartirilmaydi, har oqim original decoder bilan voksel-voksel tekshiriladi.

## 1. Maqsad va halollik

Asosiy savol: CAPE ning hozirgi candidate oilasi (CompleteWindows) bo'yicha set-cover masalasini barcha candidate va incidence yozuvlarini xotirada yaratmasdan, pricing orqali yechish mumkinmi? Bunda fayl hajmi va sertifikat sifati saqlanishi, xotira yoki hisoblash xarajati esa amalda kamayishi kerak.

Asosiy tekshiriladigan foyda xotira va vaqt. Siqish hajmi yaxshilanishi kutilmaydi (5-bo'lim). "Kamroq candidate yaratildi" o'z-o'zidan yutuq emas.

Natija salbiy bo'lsa ham ish halol yakunlanadi: teorema, tekshiruvlar, prototip o'lchovlari va rad etish sababi paketga yoziladi. Mezonlar, data va comparator natijani ko'rgandan keyin o'zgartirilmaydi.

## 2. Tekshirilgan boshlang'ich faktlar (2026-11-07)

| Fakt | Qiymat | Manba |
|---|---|---|
| j0126 Eθ/E0 | S_T = 1.073947, R_M = 0.915371, baytlar 33/33 teng | `maqola uchun/raw_results/j0126_results.csv` |
| Sertifikat (U−L)/U | j0126: mediana 0.0414%, maks 0.3471%. SNEMI: mediana 0.0236%, maks 0.0573%. hemibrain: mediana 0.5498%, maks 0.7192%. U = to'liq fayl uzunligi | `cape_q1_certified_m0` qatorlari, `certificate_valid = True` |
| Candidate oilasi | R ≤ h bo'lsa butun run, R > h bo'lsa uzunligi h bo'lgan barcha oynalar. h = min(Z, 2^(8·w_D)) | `cpp/src/candidates.cpp:28–34`, `candidate_store.cpp:63–69`, `candidates.hpp:53` |
| Narx modeli | Regime r da pin narxi c_r = w_I + r (uzunlikka bog'liq emas), singleton s = w_C | `maqola uchun/mathematics/certificate_model.md` §1–2 |
| Integer dual sertifikat | q = 2^20, a_u ≤ q·s, Σ_{u∈C_j} a_u ≤ q·c_r, L = ⌈Σa/q⌉. Faqat butun sonlar | `cpp/src/dual_bound.cpp`, `certificate_model.md` §3 |
| Eθ xotira profili (SNEMI 1024×1024×100, alohida jarayon, peak 784.8 MB) | Kirish va jarayon 246.3 MB (31%). Chain (O3, 2 B/voksel) +214.5 MB (27%). **runs 16 B × 16 346 512 = +261.6 MB (33%)**. Candidate'lar 12 B × 1 326 552 = +16.0 MB (2%). Reduksiya vaqtinchalik +46.5 MB (6%) | `profile_scale_results.csv`, `cape_q1_fast_profile_m0`, MEM paneli |
| Oynalar qanday kamayadi | 16 346 512 oyna → singleton qoidasi 11 026 087 → M1a 1 326 552 (saqlanadi) → equal 314 791 → subset 45 386 | o'sha qator, diagnostika |
| Eθ vaqt profili (o'sha hajm, 1199 ms) | Candidate yaratish 198 ms, reduksiyalar 291 ms (jami 41%). Solver ≈ 38 ms (3%). runs 168, cc 282, boundary 186 ms | o'sha qator, B paneli (profil build, 1 takror, faqat yo'nalish uchun) |
| Eng yaxshi holatda xotira tejash | Candidate va reduksiya xotirasi 0 bo'lsa ham peak = mem_peak_runs = 722.3 MB, ya'ni ko'pi bilan −62.5 MB (−8.0%) | o'sha qator |
| j0126 klasterlari | 2 juft hajm ustma-ust tushadi (1.4% va 30.9%), shuning uchun 31 klaster. S_T CI: e'lon qilingan [1.0650, 1.0832], 31 klaster bilan [1.0653, 1.0833], 26 klaster bilan (gap ≤ 150 voksel) [1.0645, 1.0837] | `data/manifests/q1_external_j0126.jsonl` `bbox_xyz` |
| Paketdagi xatolar | `METHODS_EN.md` (2-qadam va pseudokod) rad etilgan O1 ni faol deb yozadi. Eθ = 6719 = 575 + O2 (2048) + O3 (4096); O1 development'da rad etilgan (S_T 0.993). I13: `neuroglancer_b8_u32` uint16 da 0/704 | `analysis/q1_select/selected.json`, `cape/runner.py:291` |
| `CAPE_MUSTAQIL_Q1_TAHLIL_UZ.md` | Diskda yo'q, ishlatilmaydi | — |

**Oldindan kutilgan natija (ochiq yoziladi).** Profilga ko'ra candidate va reduksiya tuzilmalari SNEMI butun hajmda peak'ning ~8% ini, vaqtning ~41% ini egallaydi. Pricing runs, chain va dual qiymatlarni baribir talab qiladi. Har pricing o'tishi barcha run'larni o'qiydi: Σ R = V. Shuning uchun xotira yo'nalishi bo'yicha 5% chegaraga yetish qiyin. Vaqt yo'nalishi esa pricing iteratsiyalari soni va LP vaqtiga bog'liq. Prototip yiqilishi ehtimoli yuqori. Bu holda salbiy natija hujjatlanadi.

## 3. 0-bosqich: Q1 paketidagi kamchiliklarni tuzatish

Bu bosqich qayta o'lchovsiz bajariladi, faqat 0.3 da bitta amendment run bor. U B prototipidan oldin keladi va o'z commit'iga ega.

- **0.1 O1 matni** (`tools/q1_article.py` generatori):
  - `METHODS_EN.md` encoder ro'yxati va pseudokodida O1 faqat "tested, rejected (S_T 0.993, CI lower 0.986)" deb yoziladi. Faol pseudokod 6719 maskasiga mos bo'ladi: CC `start_label = N`, `local` nusxasi va `cc_values` o'tishi E0 dagidek.
  - `mathematics/q1_output_preserving.md` dagi xotira jadvali sarlavhasi "O1+O2+O3 (profiling mask, not the final Eθ)" bo'ladi.
  - `CONTRIBUTION_AND_PRIOR_ART_EN.md` dagi O1 qatoriga "rejected in development" qo'shiladi.
  - Validator'ga yangi tekshiruv qo'shiladi: pseudokoddagi faol bitlar = `selected_bits`.
- **0.2 j0126 klasterlari:**
  - Klaster xaritasi `bbox_xyz` dan quriladi: [start, end), musbat kesishish → bitta klaster.
  - Oldindan qayd etilgan 33 klasterli natija "as registered" bo'lib qoladi.
  - Tuzatilgan 31 klasterli natija va 26 klasterli sezgirlik (barcha o'qlarda gap ≤ 150 voksel) "amendment" sifatida qo'shiladi.
  - Matn "33 volumes; 31 non-overlapping clusters" bo'ladi.
- **0.3 I13:**
  - `cape/runner.py` dtype gate'i adapter instansiyasining `check_dtype` usulini chaqiradi, class darajasidagi `supported_dtypes` ni emas. Test qo'shiladi: `widen_to: uint32` bilan uint16 qabul qilinadi; oddiy `neuroglancer_b8` uint16 da hamon UNSUPPORTED_DTYPE.
  - Keyin faqat `neuroglancer_b8_u32` uchun alohida AMENDMENT run (yangi run ID va source hash) o'tkaziladi: SNEMI 32 crop. Protokol Q1 bilan bir xil: 1 thread, warmup 2, takror 7, wrapper'lar none/zstd3/zstd9, alohida jarayonda xotira (`configs/q1b_amend_ng_snemi.yaml`).
  - Run'dan oldingi tuzatish: muzlatilgan scale treki neuroglancer'ni umuman o'z ichiga olmagan. I13 faqat SNEMI trekiga tegishli (704 = 32 crop × 22 qator), shuning uchun scale bu amendment'ga kirmaydi.
  - Eski qatorlarga tegilmaydi. Natija Q1 paketiga alohida amendment jadval sifatida qo'shiladi.
- **0.4 Render va tekshiruv:**
  - `tools/q1_pipeline.py --mode render` ishga tushiriladi. Validator 9-bandi (numbers digest) birinchi renderda o'zgargan raqamlarni ko'rsatadi; bu kutilgan, sababi hujjatlanadi. Ikkinchi render bir xil bo'lishi shart.
  - PNG'lar ko'z bilan tekshiriladi, keyin commit qilinadi.

## 4. Masalani qat'iy chegaralash

Bitta format rejimi mahkamlanadi: regime r (w_D = r), widths w = (w_L, w_I, w_G, w_N, w_D, w_C), background label b, h = h_r = min(Z, 2^(8r)), pin narxi c = c_r = w_I + r, singleton narxi s = w_C.

Prototipda rejim Eθ FAST oqimi tanlagan rejim bilan bir xil bo'ladi: o'sha regime, background va width'lar native diagnostikadan o'qiladi. Natijada olingan bound o'sha regime uchun. Global format bound'i (barcha regime va background bo'yicha) faqat `certificate_model.md` §4–5 qoidasi bilan birlashtirilganda da'vo qilinadi.

- **Run:** bitta ustunda (x, y) bir xil labelli maksimal z-oraliq, uzunligi R.
- **Komponentlar:** run bo'ylab u_0, …, u_{R−1}. Har slice'da 2D 4-bog'lanishli CC olinadi, shuning uchun bitta run'dagi komponentlar har doim har xil.
- **Pin:** run ichidagi uzluksiz oraliq; C_p — u qoplaydigan CC'lar to'plami.
- Background label CC'lari qoplanmaydi va masalaga kirmaydi.

Per-label xarajat K_w·(w_L + 2·w_N) tanlovdan deyarli mustaqil. Pin ni pin bilan almashtirish K_w ni ham, sonlarni ham o'zgartirmaydi. w_N/w_D compaction alohida tekshiriladi (5-bo'lim).

## 5. Teorema: qisqa pinlarni uzaytirish (dominance)

**Teorema.** Bitta run ichida p ni q ga uzaytirish mumkin bo'lsin va C_p ⊆ C_q, c(p) = c(q). U holda minimum xarajatli set-cover'da p o'rniga q ishlatish xarajatni oshirmaydi.

**Isbot.** q p qoplagan barcha komponentlarni qoplaydi, shuning uchun qoplash cheklovlari saqlanadi va xarajat o'zgarmaydi. q allaqachon tanlangan bo'lsa, p olib tashlanadi va xarajat kamayadi. □

**Natija (CompleteWindows'ning to'liqligi).**
- R ≤ h bo'lsa, butun run har qanday qisqaroq pindan ustun.
- R > h bo'lsa, uzunligi ℓ ≤ h bo'lgan har qanday [a, a+ℓ) oraliq t = min(a, R−h) dan boshlanuvchi uzunligi h oynaga to'liq tushadi.
- Fixed regime ichida narx bir xil. Demak run ichidagi barcha yaroqli oraliqlar oilasida set-cover optimumi CompleteWindows optimumiga teng.

**Source auditi natijasi.**
- Shartlar source'da bajariladi (2-bo'lim jadvali).
- Fixed regime ichida h_r w_D kengligiga sig'adi, shuning uchun uzaytirish compaction'ni oshirmaydi.
- Yozuvlar soni va labellar o'zgarmaydi.

**Doirasi.** Bu set-cover modeli uchun isbot. Butun serializer uchun xulosa (width compaction, regime almashinuvi, background) `certificate_model.md` §4–5 bilan birga beriladi. Avtomatik "format optimumi" deb atalmaydi.

**Qaror.** "Kengroq interval oilasi orqali siqish yutug'i" yo'nalishi yopiladi. Bu 1-oldindan tekshiruv bilan raqamli tasdiqlanadi. Mavjud oila ichida yaxshiroq yechim berishi mumkin bo'lgan yutuq ko'pi bilan U−L (2-bo'lim).

## 6. Pinlarni aniq izlash (pricing)

LP dualidagi og'irliklar λ_u ≥ 0. Pinning reduced cost qiymati:

    r(p) = c − Σ_{u ∈ C_p} λ_u

Run bo'ylab a_t = λ_{u_t}, prefiks yig'indilar P_0 = 0, P_{t+1} = P_t + a_t. Uzunligi h, t dan boshlanuvchi oyna:

    W_t = P_{t+h} − P_t,   t ∈ [0, R−h]   (R > h)
    W   = P_R                               (R ≤ h, faqat butun run)

    t* = eng kichik argmax_t W_t    (teng maksimumlarda eng kichik t; deterministik)
    r_min = c − W_{t*}

- **Kafolat:** barcha oynalarni shu formula bilan tekshirish run ichidagi minimum reduced cost'ni aniq topadi.
- **Murakkablik:** bitta run uchun O(R) vaqt. Sirg'aluvchi yig'indi uchun qo'shimcha ishchi xotira O(1) (λ ga tasodifiy murojaat bilan). Bu butun algoritm xotirasi O(1) degani emas: λ (N_cc ta), runs va chain saqlanadi.
- **Bitta to'liq pricing o'tishi** barcha run'larni o'qiydi, Σ R = V (background bundan mustasno).
- **Integer variant (sertifikat uchun):** a_u butun sonlar, W_t int64 da overflow tekshiruvi bilan hisoblanadi.
- **Bir xil qamrovli oynalar:** M1a qo'shni ustun egizaklari takroriy ustunlar beradi. Pricing ularni bitta ustun deb qo'shadi (CC ketma-ketligi bo'yicha hash).

## 7. Pastki chegarani to'g'ri chiqarish (sertifikat)

Faqat tanlangan subset uchun yechilgan LP ning duali to'liq oila uchun feasible bo'lmasligi mumkin. To'liq tekshiruv har bir run va mahkamlangan rejim uchun bajariladi:

    0 ≤ λ_u ≤ s,    W_max(run) ≤ c

Shu bajarilsa: Σ_u λ_u ≤ OPT_LP ≤ OPT_integer.

**Integer masshtab.** λ_u = a_u / q, a_u ∈ Z≥0, q = 2^20 (native bilan bir xil). Shartlar:

    a_u ≤ q·s,    Σ_{u ∈ C_p} a_u ≤ q·c   (har oyna uchun, sirg'aluvchi tekshiruv)
    L = ⌈ Σ_u a_u / q ⌉

- **Floatdan butun songa o'tish:** a_u = ⌊q·λ_u⌋, [0, q·s] ga kesiladi. Keyin to'liq integer feasibility tekshiruvi qilinadi. Buzilish qolsa, buzilgan oynadagi a_u lar deterministik ravishda kamaytiriladi (eng katta indeksdan boshlab), so'ng qayta tekshiriladi.
- Float natijani shunchaki yaxlitlab "sertifikat" deb yozish taqiqlanadi.
- W_max > c bo'lsa, buzilgan cheklov topilgan bo'ladi va tegishli ustun LP ga qo'shiladi. Bu fayl albatta kichrayadi degani emas.

## 8. Chegaralangan column generation (prototip algoritmi)

Ikki rejim ajratiladi. Rejadagi mantiqiy kamchilik shu yerda tuzatildi: mavjud greedy yechim to'liq candidate pipeline'ni talab qiladi, shuning uchun u saqlansa xotira yutug'i bo'lishi mumkin emas.

- **CG-cert (sertifikat rejimi).** Native Eθ greedy yechimi (to'liq pipeline) boshlang'ich integer yechim sifatida saqlanadi. CG faqat qattiqroq pastki chegara uchun ishlaydi. Xotira foydasi bo'lmaydi; mumkin bo'lgan foyda — qattiqroq L va kichikroq U−L.
- **CG-implicit (xotira/vaqt rejimi).** To'liq candidate ro'yxati yaratilmaydi:
  1. Boshlang'ich ustunlar: barcha singletonlar va har run'dan bitta oyna (R ≤ h bo'lsa butun run, aks holda t = 0 oynasi).
  2. LP restricted master yechiladi (`scipy.optimize.linprog`, HiGHS, lock'dagi scipy 1.18.1).
  3. To'liq pricing o'tishi bilan r_min < −ε bo'lgan oynalar topiladi. Har run'dan ko'pi bilan bittasi, eng manfiy reduced cost'lilar qo'shiladi; bir iteratsiyada ko'pi bilan K_add = 50 000 ustun.
  4. LP qayta yechiladi. To'xtash sharti: buzilish yo'q (oxirgi to'liq o'tish bilan tasdiqlangan) yoki byudjet tugadi (40 iteratsiya yoki namuna uchun 1800 s).
  5. Integer yechim faqat yaratilgan ustunlar va singletonlar ustida olinadi: deterministik greedy (narx / yangi qoplangan CC soni, teng holatda kichik ustun indeksi), keyin redundant pinlar olib tashlanadi.
  6. U_CG = shu yechimning model baytlari (aniq byte formulasi, `certificate_model.md` §1, compaction bilan).

**Cheklovlar:**
- LP optimumi integer optimumga teng bo'lishi shart emas.
- Byudjet tugashi optimallik isboti emas.
- Feasible dual topilmasa, sertifikat da'vo qilinmaydi.
- CG-implicit ning U_CG si Eθ dan katta bo'lsa, fallback greedy to'liq pipeline'ni talab qiladi. Bunday namunada xarajat "native + CG" deb hisoblanadi, sifat esa "saqlanmadi" deb yoziladi.

## 9. Oldindan tekshiruvlar (G1 gate)

Bularning hammasi tasodifiy testlardan tashqari chegaraviy holatlarni ham o'z ichiga oladi: R ∈ {1, h−1, h, h+1, 2h, 3h}, h ∈ {1, 2, 3, 4, 8}, nol og'irliklar, teng maksimumlar, 2^40 gacha katta butun sonlar, R < h.

| Tekshiruv | Aniq dalil | Muvaffaqiyatsiz bo'lsa |
|---|---|---|
| T1. Candidate qamrovi | Kichik hajmlarda (sintetik va development crop'laridan kichik kesmalar) run ichidagi barcha yaroqli oraliqlar oilasi va CompleteWindows oilasi uchun aniq set-cover optimumlari (CP-SAT, ortools 9.15) teng | Dominance shartlari tuzatiladi; xato model ustida ishlanmaydi (BLOCKED) |
| T2. Pricing to'g'riligi | Prefiks/sirg'aluvchi natija (W_max, t*, r_min) barcha oynalarni sanash natijasiga butun sonlarda aynan teng; tie qoidasi deterministik | Pricing tuzatiladi |
| T3. Sertifikat to'g'riligi | Har holatda L ≤ OPT ≤ U (OPT CP-SAT bilan). Integer feasibility mustaqil tekshiriladi. Ataylab buzilgan float dual repair qilinadi yoki rad etiladi, hech qachon sertifikat deb qabul qilinmaydi | Sertifikat rad etiladi; prototip boshlanmaydi |
| T4. Prototip kirishi = native | Python'da qurilgan CC/run'lar soni native diagnostikadagi `cc_count`, `run_count` ga, model baytlari Eθ selection uchun haqiqiy label-section baytlariga teng (development crop'lari) | Kirish yoki model tuzatiladi; prototip boshlanmaydi |

G1 = T1 ∧ T2 ∧ T3 ∧ T4. Yiqilsa, holat BLOCKED_PRECHECK bo'ladi va 10-bo'limga o'tilmaydi.

## 10. Development prototipi va G2 gate

**Data** (oldindan muzlatilgan, 11 crop, ≥ 2 acquisition, faqat development; j0126/SNEMI/hemibrain ishlatilmaydi):
- CREMI A: `cremi_A_x0_y768_z0_256x256x64`, `cremi_A_x256_y0_z0_256x256x64`, `cremi_A_x512_y0_z0_256x256x64`;
- CREMI B: `cremi_B_x0_y256_z64_256x256x60`, `cremi_B_x256_y0_z64_256x256x60`, `cremi_B_x256_y512_z64_256x256x60`;
- CREMI C: `cremi_C_x0_y256_z64_256x256x60`, `cremi_C_x0_y768_z64_256x256x60`, `cremi_C_x256_y512_z64_256x256x60`;
- Crackle: `crackle_connectomics_x256_y256_z0_256x256x512` (uint32), `crackle_ws_x0_y0_z0_256x256x512` (uint64).

Tanlash qoidasi: har CREMI source'idan sample_id bo'yicha saralangan birinchi uchta 256×256 crop, Crackle'dan esa 256×256×512 crop'lar. Hammasi `data/manifests/v3_dev_*.jsonl` da.

**Native comparator** (bir xil mashina, 1 thread, P-core pinning, ketma-ket):
- `cape_q1_fast_m0` (Eθ): B paneli 2 warmup + 7 takror; alohida jarayonda bitta xotira o'lchovi.
- `cape_q1_fast_profile_m0`: faza vaqtlari (B paneli, 7 takror mediani) va `mem_*` belgilari (MEM paneli, bitta alohida jarayon).
- `cape_q1_certified_m0`: L_ascent va vaqt (B paneli, 7 takror).
- O'lchovdan oldingi tuzatish: runner har namuna va metod uchun bitta MEM vazifa yaratadi (`cape/runner.py`, `memory_profile_separate`). Bu Q1 final protokoli bilan bir xil, shuning uchun "3 takror" bitta alohida jarayon o'lchoviga almashtirildi.

**Prototip o'lchovlari** (har namuna, har rejim):
- yaratilgan ustunlar va incidence soni (native candidate'lar bilan: generatsiyadan keyin, equal'dan keyin, oxirida);
- pricing iteratsiyalari k va to'liq o'tishlar soni;
- LP vaqti (HiGHS, native kod) va LP davridagi RSS o'sishi;
- pricing va integer bosqich vaqtlari (Python, alohida belgilanadi);
- U_CG, Eθ U, L_CG, L_ascent, (U−L)/U;
- timeoutlar.

Prototip vaqti Python'da o'lchanadi. U native vaqt bilan bevosita solishtirilmaydi, faqat quyidagi oldindan qayd etilgan proyeksiya modelida ishlatiladi.

**Proyeksiya modeli** (native o'lchovlar va prototip sanoqlaridan; i namuna indeksi):

    S_CG,i      = 12·#ustun + 4·#incidence + 8·N_cc + LP_rss,i                  (bayt)
    Peak_proj,i = max( mem_peak_runs,i ,  mem_ws_runs,i + S_CG,i )
    T_cr,i      = candidate_ns + reduction_ns + component_ns + solver_ns       (native profil)
    T_pass,i    = candidate_ns                     (bitta to'liq run o'tishining native proksisi)
    T_int,i     = greedy_ns                        (native greedy vaqti, integer bosqich proksisi)
    T_proj,i    = T_Eθ,i − T_cr,i + k_i·T_pass,i + T_LP,i + T_int,i
    k_i         = CG davomidagi to'liq pricing o'tishlari soni (M/T yo'llari);
                  C yo'lida integer sertifikat repair o'tishlari ham qo'shiladi
    T_cert,i    = T_Eθ,i + k_i·T_pass,i + T_LP,i    (C yo'li: greedy saqlanadi, CG qo'shiladi)
    R_M,proj    = geo-mean_i( Peak_proj,i / Peak_Eθ,i )
    R_T,proj    = geo-mean_i( T_proj,i / T_Eθ,i )

Model CG-implicit foydasiga yon bosadi:
- integer bosqich native greedy vaqti bilan olinadi (Python vaqti emas);
- LP vaqti HiGHS (native kod) bilan o'lchanadi;
- runs va chain native qoladi;
- pricing o'tishi bir candidate yaratish o'tishiga teng deb olinadi.

Prototipning o'z Python vaqti va peak'i ham yoziladi, lekin faqat ma'lumot uchun.

**LP optimumi bir xilligi.** CG to'liq yaqinlashsa, LP optimumining qiymati boshlang'ich ustunlarga bog'liq emas. Shuning uchun C yo'lining L_CG qiymati CG-implicit run'idan olinadi; U esa Eθ niki. Byudjet tugasa, oxirgi duallar repair qilinib ishlatiladi: har qanday feasible dual valid L beradi.

Shuning uchun model bo'yicha yiqilish mustahkam salbiy dalil bo'ladi. Model bo'yicha o'tish esa faqat native implementatsiyaga asos, isbot emas.

**G2 gate** (oldindan qayd etilgan; hammasi development'da):
- **Majburiy:** G1 PASS. Barcha sertifikatlar integer tekshiruvdan o'tgan. Har namunada voksel tekshiruvi (Eθ oqimi uchun) PASS. Hech bir timeout tashlab yuborilmaydi: timeout bo'lsa, natija GATE_INCONCLUSIVE.
- **Kamida bitta yo'l:**
  - **(M) xotira (CG-implicit):** U_CG,i ≤ U_Eθ,i har namunada, R_M,proj ≤ 0.95 va R_T,proj ≤ 1.02.
  - **(T) vaqt (CG-implicit):** U_CG,i ≤ U_Eθ,i har namunada, R_T,proj ≤ 0.95 va R_M,proj ≤ 1.02.
  - **(C) sertifikat (CG-cert):** L_CG,i ≥ L_ascent,i har namunada (bir xil regime va background); pooled (U−L) kamayishi ≥ 50%; geo-mean_i(T_cert,i / T_certified,i) ≤ 1.0, bu yerda T_certified — native `cape_q1_certified_m0` vaqti.

Bu chegaralar Q1 standarti emas. Ular ortiqcha ishni to'xtatish uchun amaliy mezon. Natijani ko'rgandan keyin yumshatilmaydi.

## 11. Gate'dan keyin

- **G2 yiqilsa** (kutilgan holat): STOPPED_GATE_FAILED. Native implementatsiya va final benchmark boshlanmaydi. Ular NOT_RUN_GATE_FAILED deb yoziladi. Salbiy natija paketi to'liq yaratiladi (13-bo'lim).
- **G2 o'tsa:** agent shu yerda to'xtaydi va native reja bilan hisobot beradi. Native CG uchun C++ LP solver kerak (masalan HiGHS, MIT). Uni vendor qilish va encoder'ga ulash katta yangi modul va resurs, shuning uchun alohida foydalanuvchi qarorini talab qiladi (0-bo'lim). Paket "pilot passed; native not implemented" holati bilan yaratiladi.
- **Ilmiy yangilik** faqat CAPE formatining tuzilishidan kelib chiqadigan yangi teorema, mavjud usullardan farqli implicit algoritm yoki isbotlangan murakkablik yaxshilanishi bilan da'vo qilinadi. Prefiks yig'indi va column generation o'z-o'zidan yangilik emas. Dominance-to'liqlik teoremasi kichik nazariy element sifatida yoziladi.

## 12. Boshqaruv (yagona runner, uzilishdan davom etish)

- **Runner:** `tools/run_research.py` — mavjud infratuzilma (`cape/runner.py`, SQLite store, `resume_key` / `task_id_from_key`, `run_all.py`) ustidagi yupqa bosqich mashinasi. Yangi runner yozilmaydi.
- **Bosqichlar:** INVENTORY → STAGE0_FIXES → PRECHECKS (G1) → NATIVE_BASELINE → PROTOTYPE → GATE (G2) → ANALYSIS → ARTICLE → VALIDATION.
- **Holat:** `results/<run_id>/research_state.json` atomik yoziladi (temp → rename).
- **Native o'lchov kaliti:** mavjud `resume_key` (input_hash, source_hash, config_hash, method, wrapper, panel = measurement kind, repeat). Environment lock hash `config_hash` ga kiritilgani tekshiriladi; kirmagan bo'lsa qo'shiladi.
- **Prototip vazifalari** alohida SQLite jadvalida saqlanadi. Kalit: hash(source_hash, input_hash, mode, config, env_lock_hash). Har tugagan vazifa transaction bilan yoziladi.
- **Statuslar:**

| Native | Bu protokolda |
|---|---|
| OK | SUCCESS |
| UNSUPPORTED_DTYPE | UNSUPPORTED |
| TIMEOUT | TIMEOUT |
| OOM | OOM |
| FAILED | ERROR |

Qo'shimcha statuslar: NOT_RUN_GATE_FAILED, NOT_RUN_GATE_INCONCLUSIVE. Terminal xato hech qachon SUCCESS emas.
- **Resume:** eski RUNNING vazifa stale deb olinadi va qayta bajariladi. SUCCESS qayta bajarilmaydi. Source, config yoki input o'zgarsa, yangi run ID ochiladi.
- **Retry:** namuna uchun timeout belgilangan, retry soni cheklangan (≤ 1), disk nazorati bor.
- **Buyruqlar:**
  - `.venv\Scripts\python tools\run_research.py --mode full --fresh-run`
  - `--resume-run <id>`
  - `--mode render --run-id <id>`

## 13. Natijalar: alohida papka

- **Xom natijalar:** `results/<run_id>/` (native run'lar, prototip SQLite, loglar). Overwrite qilinmaydi.
- **Maqola paketi:** `maqola uchun 2/` va `maqola_uchun_2.zip` (venv va datasetsiz). Faqat VALIDATION PASS dan keyin, staging orqali ko'chiriladi. Hozirgi `maqola uchun/` ga tegilmaydi.

**`maqola uchun 2/` tarkibi:**
- **`mathematics/`:**
  - `problem_definition.md`;
  - `dominance_completeness_theorem.md` (teorema, isbot, source auditi, doira);
  - `pricing_exactness.md`;
  - `integer_certificate.md`;
  - `column_generation_scope.md`;
  - `complexity.md`.
- **`methods/`:** `METHODS_EN.md`, `RESULTS_EN.md`, `LIMITATIONS_EN.md`, `CONTRIBUTION_AND_PRIOR_ART_EN.md` (tasdiqlangan hissa, ma'lum tamoyil va taxmin ajratilgan), `MANUSCRIPT_DRAFT_EN.md` (gate yiqilsa "negative-result draft"), `CAPTIONS_EN.md`, `references.bib` (faqat tekshirilgan manbalar).
- **Jadvallar** (CSV, MD va LaTeX):
  - T01: development crop'lari (source, dtype, shape, voxel soni, rol);
  - T02: metodlar va versiyalar;
  - T03: G1 tekshiruvlari (holatlar soni, PASS/FAIL);
  - T04: har namuna bo'yicha native va prototip sanoqlari, vaqt va xotira;
  - T05: proyeksiya va G2 qarori;
  - T06: sertifikat (L_ascent, L_CG, U, gap);
  - T07: muvaffaqiyatsizlik, timeout va istisnolar.
- **Rasmlar** (PNG, SVG/PDF va plot_data CSV):
  - F01: run va oyna dominance illyustratsiyasi (haqiqiy crop'dan bitta ustun);
  - F02: algoritm oqimi;
  - F03: native xotira taqsimoti (input, chain, runs, candidate, reduksiya) va CG proyeksiyasi;
  - F04: vaqt taqsimoti va CG proyeksiyasi;
  - F05: CG yaqinlashuvi (iteratsiya → LP qiymati, L, buzilishlar soni);
  - F06: har namuna bo'yicha R_M,proj, R_T,proj va gap.
- **Qolgan fayllar:**
  - `audit/` (0-bosqich tuzatishlari, source auditi);
  - `checks/` (validator hisoboti, vizual ko'rik);
  - `reproducibility/` (`REPRODUCE.md`, hash'lar, lock, seed 20261107);
  - `raw_results/`, `scripts/`;
  - `claims_ledger.csv` (SUPPORTED, CONDITIONAL, UNSUPPORTED va dalil);
  - `artifact_manifest.csv` (fayl, vazifa, hash, holat; yaratilmagan narsa uchun aniq sabab);
  - `YAKUNIY_HISOBOT_UZ.md` (haqiqiy yutuq va muvaffaqiyatsizlik, mezonlar, 10 ballik asoslangan baho).

Raqamlar qo'lda yozilmaydi: hammasi bitta tahlil datasetidan generator orqali chiqadi. Yo'q natija uchun soxta grafik chizilmaydi; NOT_RUN va sababi yoziladi.

## 14. Validator va tugash holatlari

Validator (`tools/validate_cg_package.py`) tekshiradi:
- fayllar mavjud va bo'sh emas;
- har da'vo xom qator yoki test ID'siga kuzatiladi;
- formulalar xom ma'lumotdan mustaqil qayta hisoblanadi;
- CSV, MD, TeX va plot_data qiymatlari bir xil;
- missing ≠ 0;
- voksel va sertifikat tekshiruvlari bor;
- faol modul va pseudokod mos;
- statuslar ajratilgan;
- render rejimida raqamlar bir xil;
- `visual_review.json` PASS.

Tugash holatlari:

| Holat | Qachon |
|---|---|
| COMPLETE_VALIDATED | G2 o'tgan, paket to'liq |
| COMPLETE_WITH_FAILURES | Paket bor, lekin ba'zi o'lchovlar yo'q |
| STOPPED_GATE_FAILED | G2 yiqilgan |
| STOPPED_GATE_INCONCLUSIVE | Timeout yoki missing bor |
| BLOCKED_PRECHECK | G1 yiqilgan |
| INVALID_LOSSLESS | Lossless buzilgan |

Gate yiqilsa ham ANALYSIS → ARTICLE → VALIDATION bajariladi. Texnik COMPLETE ilmiy muvaffaqiyat yoki Q1 degani emas.

## 15. Yakuniy javob

Yakuniy javobda quyidagilar bo'ladi:
- 0-bosqichda nima tuzatildi;
- teorema va tekshiruvlar natijasi;
- prototip raqamlari va G2 qarori;
- yo'llar bo'yicha yutish va yutqazish;
- qolgan cheklovlar;
- paket manzili va resume/render buyrug'i.

Eng yaxshi raqam kontekstsiz sarlavha qilinmaydi.

## 16. Manba hujjatlarga nisbatan tuzatishlar

| Manba | Tuzatish va sababi |
|---|---|
| B rejasi §6 "greedy saqlansin" | CG-cert va CG-implicit ga ajratildi. Greedy saqlansa to'liq pipeline ishlaydi va xotira foydasi bo'lishi mumkin emas |
| B rejasi §8 davom etish sharti | Raqamli chegaralar, proyeksiya modeli va uch yo'l (M/T/C) oldindan qayd etildi |
| B rejasi §5 | Native'da allaqachon borligi (`dual_bound.cpp`) yozildi. Prototip shu q = 2^20 bilan mos |
| B rejasi §4 | Bir xil qamrovli ustunlar (M1a egizaklari), background va int64 overflow qo'shildi |
| B rejasi §2 | Source auditi natijasi va doirasi (fixed regime, compaction) yozildi |
| v2 prompt (SPS) | Bu rejaga kirmaydi (foydalanuvchi B ni tanladi). Undagi protokol talablari (freeze, statuslar, papka, validator, timing qoidasi) saqlandi |
| v2 prompt §6 T_ratio ≤ 3 | Bu rejada qo'llanmaydi: o'rniga G2 dagi R_T,proj |
| Q1 paketi | O1 matni, j0126 31 klaster va I13 0-bosqichda tuzatiladi |
| Kutilgan natija | Profil bo'yicha prototip yiqilishi ehtimoli yuqori; bu oldindan ochiq yozildi (2-bo'lim) |
