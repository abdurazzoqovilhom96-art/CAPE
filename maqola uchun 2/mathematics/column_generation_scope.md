# Bounded column generation: modes and limits

- CG-cert: the native greedy stream is kept (full pipeline) and CG only seeks a tighter lower bound. No memory gain is
  possible in this mode.
- CG-implicit: no candidate list; columns = singletons + one window per useful run, plus violated windows found by
  exact pricing; integer solution = greedy over the generated columns, then redundant-pin removal.
- Limits: the LP optimum need not equal the integer optimum; a budget stop is not an optimality proof; without a
  feasible full-family dual no certificate is claimed; column generation may need many iterations and is not
  guaranteed to be faster.
- If CG-implicit is converged, the LP optimum value does not depend on the initial columns, so CG-cert reuses its L.

**Structural observation (fixed_depth_width, the regime Eθ writes).** The stream regime takes the narrowest depth width
that fits Z: 2^(8 w_D) >= Z, so h = min(Z, 2^(8 w_D)) = Z. Every run then has R <= Z = h and CompleteWindows is exactly
one window per run: the "implicit" family IS the run list, and window pricing cannot add any column. Window pricing
matters only in narrower regimes (h < Z), which the native solver bounds dual-only for the certificate.
