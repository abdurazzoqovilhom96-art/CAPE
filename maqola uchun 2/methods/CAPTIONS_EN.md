# Figure captions

**F01** (OK): One real column of cremi_A_x0_y768_z0_256x256x64: a run of length R = 64 and its length-8 windows for an ILLUSTRATIVE h = 8. Every interval of length <= h lies in one window with the same pin cost, so the wider family cannot lower the set-cover optimum (theorem). In the regime that Eθ actually writes, h = 64 = Z: every run is a single window.
  - UZ: Haqiqiy ustun: run va uning h-oynalari; qisqa oraliq bitta oynaga to'liq tushadi.

**F02** (OK): Bounded column generation evaluated in this study (prototype). Runs and the column-major chain stay native and resident; candidate and incidence lists are replaced by exact pricing.
  - UZ: Prototip oqimi: runs/chain native qoladi, candidate ro'yxati o'rniga pricing.

**F03** (OK): Native Eθ encode-inclusive memory by structure (profile build, one fresh process per sample) and the projected CG peak (black dash). The CG can only remove the candidate and reduction parts; runs and the chain stay.
  - UZ: Native xotira taqsimoti va CG proyeksiyasi.

**F04** (OK): Native Eθ encode time by phase (profile build, median of 7 repeats) and the projected CG time (black dash; pricing passes x native candidate-pass time + measured HiGHS LP time + native greedy time). Log scale.
  - UZ: Native vaqt taqsimoti va CG proyeksiyasi (log).

**F05** (OK): Candidate family sizes per development sample: native windows (equal to the runs, since h = Z), what the native reductions keep, and the deduplicated columns of the CG prototype. CG converged at the first LP on 11/11 samples, so its pricing never added a column (the protocol's convergence plot would be a single point; see T04).
  - UZ: Oila hajmlari: native reduksiyalar va CG ustunlari; CG birinchi LP'da yaqinlashdi.

**F06** (OK): Projected CG-implicit / native Eθ ratios per sample (memory, time) and the memory ratio of the most favourable case where the CG structures cost nothing (runs and chain kept). Hollow markers: post-hoc time ratio with the warm HiGHS solve time (the run's LP time included the first-call scipy import); not part of the gate. Dashed line: the pre-registered 0.95 gate. Log scale.
  - UZ: Har namuna bo'yicha proyeksiya nisbatlari va gate chizig'i.
