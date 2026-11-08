# Problem definition (B protocol)

One regime of CAPE's PINS label section is fixed (certificate_model.md section 2): depth width r = w_D, longest pin
h = min(Z, 2^(8r)), pin cost c = w_I + r, singleton cost s = w_C, background label b (not covered).
A run is a maximal same-label z-interval of one column (x, y). Its CCs u_0..u_{R-1} are distinct (one 2D 4-connected
CC per slice). The CompleteWindows family takes the whole run if R <= h and every length-h window if R > h
(cpp/src/candidates.cpp lines 28-34, cpp/src/candidate_store.cpp lines 63-69).

    OPT = min  c * sum_j x_j + s * sum_u y_u   s.t.  sum_{j contains u} x_j + y_u >= 1  for every non-background CC u,
               x, y in {0, 1}

Question studied: can this problem be solved without materializing the candidate and incidence lists (pricing over
runs), with the same output quality, less memory or time, and a valid certificate?
