# Complexity and measured cost model

One full pricing pass: O(sum of useful run lengths) <= O(V) time, O(1) extra memory per run. k passes plus k LP solves.
Native Eθ: linear passes over V (CC, runs) plus candidate generation, reductions and the solver. The projection model
(protocol section 10) replaces the native candidate + reduction + component + solver time by k pricing passes (each
priced as one native candidate pass), the measured HiGHS LP time and the native greedy time, and keeps runs and chain
resident in memory. It is favourable to CG on purpose; failing it is a robust negative result.
