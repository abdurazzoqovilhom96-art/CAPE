# Exact pricing

Duals lambda_u >= 0. Reduced cost of a pin p: r(p) = c - sum_{u in C_p} lambda_u. Along a run a_t = lambda_{u_t},
P_0 = 0, P_{t+1} = P_t + a_t, W_t = P_{t+h} - P_t for t in [0, R-h] (R > h), W = P_R (R <= h);
t* = smallest argmax W_t, r_min = c - W_{t*}.

**Guarantee.** Scanning every window with this formula finds the exact minimum reduced cost in the run, in O(R) time
and O(1) extra working memory (random access to lambda). This does not make the whole algorithm O(1) in memory:
lambda (one value per CC), the runs and the chain stay resident. One full pricing pass reads every useful run.

**Exactness in practice.** The LP pricing uses floor(lambda * 2^30) in int64 (float prefix sums over ~10^7 positions
carry ~1e-7 rounding), tolerance 1e-6 absolute; the certificate pricing uses the integer duals a_u exactly.
Check: precheck T2 (brute-force enumeration, ties, zero and large weights).
