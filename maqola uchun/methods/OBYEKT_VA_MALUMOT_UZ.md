# Obyekt va ma'lumot

**Nima siqiladi.** Neyronlarning 3D obyekt-ID segmentatsiya xaritalari: har voksel o'zi tegishli neyrit ID'sini
saqlaydi. Bu elektron mikroskop intensivlik tasviri emas. Siqish lossless: dekodlangan hajm kirish bilan voksel
bo'yicha bir xil, ID va chegaralar aynan saqlanadi.

**Kodek.** Crackle (seung-lab, 14b39b1 commit). CAPE PINS label bo'limidagi yozuvlarni tanlaydi; oqimni o'zgartirilmagan
upstream dekoder ochadi.

**Datasetlar** (T01):
- j0126 (zebra finch, SBEM): 33 ta zich qo'lda belgilangan hajm, uint64; YANGI asosiy test.
- SNEMI3D: 32 crop + butun hajm va 4 kvadrant, uint16; avval ko'rilgan (v3 holdout), ikkilamchi.
- hemibrain v1.2 (FIB-SEM 8 nm): 4 ta oldindan belgilangan 512x512x256 kesma, uint64; tavsifiy.
- Faqat development: CREMI A/B/C va Crackle repo namunalari.

**Qo'llanmagan joylar.** Intensivlik tasvirlari, RGB, tibbiy tasvirlar, qisman dekodlash (kodda yo'q).
