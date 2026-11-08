# Results (B protocol, development data only; terminal status STOPPED_GATE_FAILED)

- Prechecks (G1): True. Tables T03 (T1 coverage, T2 pricing, T3 certificate, T4 instance).
- Native Eθ memory: the part that CG could remove (peak minus the peak reached by the end of the runs phase) is a median 1.2% of the encode-inclusive peak over 11 crops; the most favourable memory ratio (CG structures cost 0) is a geo-mean 0.9639.
- Native Eθ time: candidates + reductions + components + solver are a median 21.9% of the profiled encode time.
- Structure: in the regime Eθ writes, h = Z on 11/11 crops, so CompleteWindows is one window per run and CG converged at the first LP on 11/11 crops: pricing never added a column (mathematics/column_generation_scope.md).
- CG-implicit converged on 11/11 crops; its greedy integer cover was not worse than Eθ on 1/11 crops (Eθ also uses exact DP and local search).
- Projected CG-implicit / Eθ: memory 1.5349, time 6.1074 (geo-means; table T05).
- Certificate: L_CG >= L_ascent on 11/11 crops; pooled gap 42489 (ascent) vs 1896 (CG) payload bytes; median gap 0.689% -> 0.138% of U; projected CG-cert / native certified time 6.0827 (table T06).
- Post hoc (not part of the gate, table T08): with the warm HiGHS time instead of the run's first-call LP time, the time ratio is 2.5016 and the certificate time ratio 2.7568 (geo-means); the conclusion does not change.
- Gate G2: route M False, route T False, route C False -> G2 = False.

Negative result: the pre-registered gate was not met; native implementation and a final benchmark were not run (NOT_RUN_GATE_FAILED).
