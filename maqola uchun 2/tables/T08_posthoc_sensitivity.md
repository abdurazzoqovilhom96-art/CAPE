# T08_posthoc_sensitivity: POST-HOC sensitivity (not part of the gate): warm HiGHS time instead of the run's first-call LP time

| sample_id | LP s (run) | LP s (warm, post hoc) | R_T (gate) | R_T (warm LP) | R_cert (gate) | R_cert (warm LP) | R_M if CG structures cost 0 |
|---|---|---|---|---|---|---|---|
| crackle_connectomics_x256_y256_z0_256x256x512 | 3.7303 | 3.7578 | 6.9395 | 6.9873 | 5.0334 | 5.0648 | 0.8392 |
| crackle_ws_x0_y0_z0_256x256x512 | 19.6448 | 18.7535 | 16.542 | 15.8157 | 11.8161 | 11.3178 | 0.862 |
| cremi_A_x0_y768_z0_256x256x64 | 0.2083 | 0.0819 | 6.0445 | 2.9128 | 6.5319 | 3.3467 | 0.9851 |
| cremi_A_x256_y0_z0_256x256x64 | 0.1793 | 0.0564 | 5.7539 | 2.4322 | 6.1037 | 2.7776 | 0.9943 |
| cremi_A_x512_y0_z0_256x256x64 | 0.1712 | 0.0514 | 5.8093 | 2.3818 | 6.0316 | 2.6548 | 1.0019 |
| cremi_B_x0_y256_z64_256x256x60 | 0.148 | 0.0118 | 5.6102 | 1.3357 | 6.0336 | 1.711 | 0.9916 |
| cremi_B_x256_y0_z64_256x256x60 | 0.1374 | 0.0135 | 5.2795 | 1.3804 | 5.6195 | 1.7304 | 0.991 |
| cremi_B_x256_y512_z64_256x256x60 | 0.1246 | 0.0125 | 5.02 | 1.3725 | 5.293 | 1.6862 | 0.9935 |
| cremi_C_x0_y256_z64_256x256x60 | 0.1464 | 0.0271 | 4.7685 | 1.6413 | 5.2616 | 2.0972 | 0.9877 |
| cremi_C_x0_y768_z64_256x256x60 | 0.154 | 0.0267 | 5.4764 | 1.721 | 5.893 | 2.1023 | 0.9876 |
| cremi_C_x256_y512_z64_256x256x60 | 0.1525 | 0.0337 | 4.8963 | 1.8011 | 5.2996 | 2.2451 | 0.9871 |
| geo-mean |  |  | 6.1074 | 2.5016 | 6.0827 | 2.7568 | 0.9639 |

Post hoc (after the run, same machine, pinned core, nothing else running): LP matrix assembly + HiGHS solve measured warm on the converged LP of each sample. The pre-registered gate uses the run's measured LP time and is not changed by this table.
