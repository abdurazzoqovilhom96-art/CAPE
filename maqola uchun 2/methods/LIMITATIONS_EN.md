# Limitations

- Development data only (11 crops, CREMI and Crackle samples); no held-out or new acquisition was used.
- One machine, one thread. Time and memory of a native CG are projected (protocol section 10), not measured.
- The projection prices a pricing pass as one native candidate pass and the integer step as the native greedy; both
  favour CG. The LP time is HiGHS through scipy (native code), measured on this machine.
- One fresh-process memory measurement per sample (as in the Q1 final protocol).
- The certificate and the theorem concern the per-regime set-cover model; the serializer-level bound is that of
  certificate_model.md.
- Column generation and prefix-sum pricing are known techniques; nothing here is claimed as a new algorithm.
- The LP time of the run includes the sparse-matrix assembly and, on the first call of each process, the import of
  scipy.optimize; table T08 gives the warm time post hoc. The gate uses the run's measured time as pre-registered.
- In the Eθ stream regime h = Z, so on these data the window pricing had nothing to price (one window per run); a
  narrower regime (h < Z) was not tested by the prototype.
- One development smoke run (one CREMI crop, 300 s budget) checked the pipeline before the formal run; it is not
  evidence and no threshold was changed.
