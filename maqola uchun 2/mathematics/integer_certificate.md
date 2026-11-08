# Integer certificate

A dual is feasible for the FULL family when 0 <= lambda_u <= s and W_max <= c for every useful run (fixed regime).
Then sum lambda <= OPT_LP <= OPT. Scaled integers: lambda_u = a_u / q, q = 2^20 (the native scale of
cpp/src/dual_bound.cpp): a_u <= q*s and every window sum <= q*c; L = sum over components ceil(sum a / q) plus s for
every CC outside the LP (each component optimum is an integer).

From float LP duals: a_u = floor(q * lambda_u) clipped to [0, q*s], then every violated window is repaired
deterministically (reduce from the window's last position) and the whole family is re-checked independently in
integers. A float result is never rounded into a "certificate". Runs with min(R, h)*s <= c need no check: their
window sums are at most len*q*s <= q*c. Check: precheck T3 (exact optimum, deliberately infeasible duals).

The native solver already computes such a bound (dual ascent, same scale); the prototype compares against it
(T06), with the same regime and the same background.
