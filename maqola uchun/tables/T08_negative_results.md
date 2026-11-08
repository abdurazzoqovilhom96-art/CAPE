**T08. Negative results, non-success statuses, trade-offs**

| kind | dataset | item | value | note |
|---|---|---|---|---|
| status | snemi | neuroglancer_b8 (none, timing) | UNSUPPORTED x224 | neuroglancer_b8 supports ['uint32', 'uint64']; input is uint16 (no silent cast) |
| status | snemi | neuroglancer_b8 (none, memory) | UNSUPPORTED x32 | neuroglancer_b8 supports ['uint32', 'uint64']; input is uint16 (no silent cast) |
| status | snemi | neuroglancer_b8 (zstd3, timing) | UNSUPPORTED x224 | neuroglancer_b8+zstd3 supports ['uint32', 'uint64']; input is uint16 (no silent cast) |
| status | snemi | neuroglancer_b8 (zstd9, timing) | UNSUPPORTED x224 | neuroglancer_b8+zstd9 supports ['uint32', 'uint64']; input is uint16 (no silent cast) |
| status | snemi | neuroglancer_b8_u32 (none, timing) | UNSUPPORTED x224 | neuroglancer_b8_u32 supports ['uint32', 'uint64']; input is uint16 (no silent cast) |
| status | snemi | neuroglancer_b8_u32 (none, memory) | UNSUPPORTED x32 | neuroglancer_b8_u32 supports ['uint32', 'uint64']; input is uint16 (no silent cast) |
| status | snemi | neuroglancer_b8_u32 (zstd3, timing) | UNSUPPORTED x224 | neuroglancer_b8_u32+zstd3 supports ['uint32', 'uint64']; input is uint16 (no silent cast) |
| status | snemi | neuroglancer_b8_u32 (zstd9, timing) | UNSUPPORTED x224 | neuroglancer_b8_u32+zstd9 supports ['uint32', 'uint64']; input is uint16 (no silent cast) |
| larger | j0126 | A_z3_stock | 3/33 samples larger | cape_q1_fast_m0+zstd3 vs crackle_pins_opt_corrected_m0+zstd3 |
| larger | j0126 | SAFE3_stock | 3/33 samples larger | safe_q1_fast_m0_zstd3 vs safe_stock_m0_zstd3 |
| larger | snemi | A_z3_stock | 1/32 samples larger | cape_q1_fast_m0+zstd3 vs crackle_pins_opt_corrected_m0+zstd3 |
| larger | snemi | SAFE3_stock | 1/32 samples larger | safe_q1_fast_m0_zstd3 vs safe_stock_m0_zstd3 |
| larger | scale_stock | SAFE9_stock | 1/4 samples larger | safe_q1_fast_m0_zstd9 vs safe_stock_m0_zstd9 |
| trade-off | j0126 | Eθ vs Crackle flat | 3.09% smaller, S_T 0.501 | CAPE is slower than flat |
| trade-off | snemi | Eθ vs Crackle flat | 5.40% smaller, S_T 0.537 | CAPE is slower than flat |
| trade-off | hemibrain | Eθ vs Crackle flat | 8.27% smaller, S_T 0.431 | CAPE is slower than flat |
| trade-off | scale | Eθ vs Crackle flat | 7.40% smaller, S_T 0.429 | CAPE is slower than flat |
