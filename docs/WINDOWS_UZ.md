# Windows'da o'rnatish va ishga tushirish

Tekshirilgan muhit (2026-11-05): Windows 11 Pro, i7-13700F (8 P + 8 E yadro), 32 GB RAM,
CPython 3.12.10, MinGW-w64 g++ 16.2 (WinLibs UCRT, POSIX threads), CMake 4.4.4, Ninja.

## 1. Kerakli dasturlar
1. **CPython 3.12** — https://www.python.org/downloads/windows/ (`py -3.12 --version` ishlashi kerak).
   Tizimdagi `py` sukut bo'yicha boshqa versiyani olishi mumkin; skriptlar har doim `py -3.12` ni chaqiradi.
2. **MinGW-w64 g++ (C++20)**, **CMake**, **Ninja** — masalan `winget install BrechtSanders.WinLibs.POSIX.UCRT`.
   MSVC kerak emas: CAPE va vendor Crackle bir xil g++ bilan quriladi (adolatli timing).
3. **git** — pinned manbalarni olish uchun.

## 2. Birinchi ishga tushirish
```powershell
cd D:\CAPE_PINS
.\run_experiment.cmd --stage smoke
```
Wrapper o'zi: `.venv` yaratadi, `requirements.lock` bo'yicha (hash tekshiruvi bilan) o'rnatadi,
`vendor/crackle` ni pinned commit'da oladi, native modullarni quradi, `doctor` tekshiruvini o'tkazadi.
Keyingi ishga tushirishlarda bu qadamlar fingerprint o'zgarmagan bo'lsa o'tkazib yuboriladi.

Muammo bo'lsa: `results\<run_id>\14_logs\bootstrap.log`, `build\native_build.log`.

## 3. CSGV / CSGV-R (Volcanite) — ixtiyoriy, administrator ruxsati kerak
Volcanite Windows'da faqat MinGW bilan quriladi va **LunarG Vulkan SDK** talab qiladi.
1. Vulkan SDK: https://vulkan.lunarg.com/sdk/home (o'rnatuvchi UAC ruxsatini so'raydi).
2. `python scripts\fetch_sources.py --only volcanite` (commit `sources.lock.json` da pin qilinadi).
3. `cmake -G Ninja -DHEADLESS=ON -DCMAKE_BUILD_TYPE=Release -S vendor\volcanite -B vendor\volcanite\cmake-build-release`
   va `cmake --build vendor\volcanite\cmake-build-release --target volcanite`.
Build bo'lmasa CSGV qatorlari `UNAVAILABLE` bo'lib qoladi va "zamonaviy kodeklardan ustun" da'vosi
bloklanadi — boshqa natijalar baribir chiqadi.

## 4. Timing uchun tavsiyalar
- Benchmark paytida og'ir dasturlarni yopib qo'ying; quvvat rejimi `environment.json` ga yoziladi.
- Timing ikkinchi P-core'ning birinchi thread'ida bajariladi (avtomatik aniqlanadi).
- Natijalar diski (D:) lokal disk bo'lishi kerak (SQLite tarmoq diskida ishonchli emas).
