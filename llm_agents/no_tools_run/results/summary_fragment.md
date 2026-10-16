| condition | policy | nh to 1st qual | found rate | mean quals | labels/nh | fail rate | validity | R-gain | H-gain | leak ok | win-win |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CTCE_P0 | scripted | 269 | 0.92 | 1.85 | 0.0294 | 0.019 | 0.975 | 0.25 | 0.46 | 0.00 | 0.00 |
| CTCE_P0 | llm | 426 | 0.90 | 1.23 | 0.0105 | 0.020 | 0.975 | 0.08 | 0.08 | 0.00 | 0.00 |
| DTDE_P4 | scripted | 299 | 0.83 | 1.67 | 0.0251 | 0.027 | 0.966 | 0.00 | 0.00 | 1.00 | 0.00 |
| DTDE_P4 | llm | 382 | 0.88 | 1.33 | 0.0127 | 0.025 | 0.969 | 0.00 | 0.00 | 1.00 | 0.00 |
| CEDT_P4 | scripted | 286 | 0.85 | 1.81 | 0.0267 | 0.029 | 0.958 | 0.08 | 0.17 | 1.00 | 0.04 |
| CEDT_P4 | llm | 396 | 0.88 | 1.25 | 0.0121 | 0.013 | 0.983 | 0.04 | 0.00 | 1.00 | 0.00 |
| CEDT_P3_eps2 | scripted | 326 | 0.90 | 1.73 | 0.0266 | 0.023 | 0.973 | 0.25 | 0.17 | 0.33 | 0.00 |
| CEDT_P3_eps2 | llm | 419 | 0.85 | 1.21 | 0.0120 | 0.023 | 0.976 | 0.08 | 0.04 | 0.00 | 0.00 |

Decision agreement with the scripted policy: R seat 36.0%, H seat 12.2%.
Calls: R 2147 (fallbacks 0), H 2147 (fallbacks 0); wall 888 s.
Leakage at CEDT-P3 (llm vs scripted): r_mi_auc 0.849/0.603, r_id_acc 0.058/0.059, h_tel_auc 0.510/0.523, h_rank_corr 0.116/0.110
