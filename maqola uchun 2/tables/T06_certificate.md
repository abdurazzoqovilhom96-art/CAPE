# T06_certificate: payload bounds (same regime, same background; cost units = bytes of the labels payload)

| sample_id | U (Eθ) | L ascent (native) | L CG | gap ascent | gap CG | gap ascent % of U | gap CG % of U | U CG-implicit | U_CG <= U_Eθ | certificate feasible | CG converged | CG stop |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| crackle_connectomics_x256_y256_z0_256x256x512 | 91242 | 86820 | 89918 | 4422 | 1324 | 4.8465 | 1.4511 | 93586 | False | True | True | converged |
| crackle_ws_x0_y0_z0_256x256x512 | 966464 | 928482 | 965909 | 37982 | 555 | 3.93 | 0.0574 | 971744 | False | True | True | converged |
| cremi_A_x0_y768_z0_256x256x64 | 2363 | 2354 | 2361 | 9 | 2 | 0.3809 | 0.0846 | 2371 | False | True | True | converged |
| cremi_A_x256_y0_z0_256x256x64 | 2978 | 2958 | 2976 | 20 | 2 | 0.6716 | 0.0672 | 2978 | True | True | True | converged |
| cremi_A_x512_y0_z0_256x256x64 | 1938 | 1919 | 1938 | 19 | 0 | 0.9804 | 0.0 | 1946 | False | True | True | converged |
| cremi_B_x0_y256_z64_256x256x60 | 705 | 701 | 704 | 4 | 1 | 0.5674 | 0.1418 | 710 | False | True | True | converged |
| cremi_B_x256_y0_z64_256x256x60 | 677 | 669 | 675 | 8 | 2 | 1.1817 | 0.2954 | 687 | False | True | True | converged |
| cremi_B_x256_y512_z64_256x256x60 | 682 | 680 | 682 | 2 | 0 | 0.2933 | 0.0 | 686 | False | True | True | converged |
| cremi_C_x0_y256_z64_256x256x60 | 1034 | 1025 | 1028 | 9 | 6 | 0.8704 | 0.5803 | 1046 | False | True | True | converged |
| cremi_C_x0_y768_z64_256x256x60 | 723 | 719 | 722 | 4 | 1 | 0.5533 | 0.1383 | 734 | False | True | True | converged |
| cremi_C_x256_y512_z64_256x256x60 | 1451 | 1441 | 1448 | 10 | 3 | 0.6892 | 0.2068 | 1474 | False | True | True | converged |
| pooled |  |  |  | 42489 | 1896 |  |  |  |  |  |  |  |
