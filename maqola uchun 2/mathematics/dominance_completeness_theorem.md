# Dominance completeness of CompleteWindows

**Theorem (extension).** Inside one run let p be extendable to q with C_p subset of C_q and c(p) = c(q). In the
minimum-cost set cover, using q instead of p never increases the cost.

**Proof.** q covers every CC that p covers, so all covering constraints stay satisfied and the cost is unchanged.
If q is already selected, p is redundant and can be dropped, which can only lower the cost. QED

**Corollary (completeness).** In a fixed regime every interval [a, a+l) with l <= h of a run lies in the window that
starts at t = min(a, R - h) (R > h) or in the whole run (R <= h); all these have the same cost c. Hence the optimum over
every interval of every run equals the optimum over CompleteWindows.

**Source audit (2026-11-07).**
- Family: whole run if R <= h, every length-h window otherwise (candidates.cpp, candidate_store.cpp, candidates.hpp:53).
- Cost: c_r = w_I + r independent of the length; s = w_C (byte_model.cpp, certificate_model.md section 1-2).
- Couplings: replacing a pin by a pin of the same label changes neither the written labels K_w nor the counts (w_N);
  inside a fixed regime h_r fits the width r, so extension never widens w_D.

**Scope.** This is a statement about the per-regime set-cover model. The serializer-level bound (width compaction,
regime choice, background) is the one of certificate_model.md sections 4-5. Numerical check: precheck T1
(tables/T03_prechecks.csv).

**Consequence.** No compression gain can come from a wider interval family; inside the family the possible gain is at
most U - L of the certificate.
