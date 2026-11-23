# Zara Inventory Optimization — Optimization I Final Project

**A synthetic, single-period inventory-allocation study inspired by Caro et al. (2010).**

This project uses mixed-integer linear programming (MILP) to determine how a warehouse should distribute clothing across stores and sizes. It incorporates **size exposure**, **diminishing marginal sales potential (saturation)**, **store receiving capacities**, and the **economic value of inventory retained at the warehouse**.

> **Scope:** All numerical inputs are synthetic. This is an academic model, not an implementation of Zara's operational system. The objective is *modeled economic value* (expected sales revenue plus assigned retained-stock value), **not net profit** or a prediction of actual Zara sales.

## 1. Project at a glance

| Component | Description |
|---|---|
| Network | 1 warehouse, 10 hypothetical European stores |
| Products | 5 clothing articles, each in XS, S, M and L |
| Periods | 1 replenishment period |
| Method | Pyomo MILP solved with HiGHS |
| Decisions | Integer shipments, warehouse stock retained, modeled expected sales, binary exposure indicators |
| Sales assumptions | Three exposure levels combined with concave piecewise-linear saturation |
| Operational limits | Warehouse stock by article/size and each store's receiving capacity |
| Data | Reproducibly generated synthetic CSVs; random seed `20261031` |

In the baseline model, sizes **S, M and L** determine whether a store–article assortment qualifies for partial or full exposure. The resulting sales factor applies to **all four sizes**, including XS. The partial-exposure factor is `rho = 0.60`, and full exposure requires at least three units of each major size. Warehouse stock retained after allocation receives a hypothetical value equal to `0.35 ×` the article's selling price per unit.

The baseline formulation contains **520 decision variables** (200 integer shipments, 200 continuous expected-sales variables, 20 integer warehouse-retention variables and 100 binary exposure indicators) and **2,580 linear constraints**.

## 2. Main verified findings

**Verification status: 23 November 2026.** The project has been rerun locally, and saved allocations and numerical outputs have been checked for consistency. Historical outputs and later reruns are kept separately.

| Baseline result | Value |
|---|---:|
| Total modeled economic objective | **EUR 45,657.45** |
| Modeled expected sales revenue | EUR 43,996.00 |
| Assigned value of retained warehouse inventory | EUR 1,661.45 |
| Warehouse stock available | 483 units |
| Warehouse stock shipped | **392 units** |
| Warehouse stock retained | **91 units** |
| Modeled expected sales | 566.20 units |
| Store–article combinations with full exposure | 50 of 50 |

**Main operational finding:** All ten stores reach their receiving capacities even though 91 warehouse units remain unshipped. Receiving capacity is therefore a binding operational bottleneck in this synthetic instance. Exposure, saturation and retained-stock value help determine *which* stores, articles and sizes receive the available shipments.

The baseline solve reported **optimal termination within its configured numerical MIP-gap tolerance**. The archived baseline output does not contain a raw best bound or measured final MIP-gap value, so an exactly-zero gap is **not** claimed.

### No-shipment baseline and incremental value

Shipping nothing is a valid reference policy: existing store inventory can still generate modeled sales, and all warehouse units retain their assigned value.

- Modeled sales revenue from initial store inventory: **EUR 3,566.94**.
- Value of all warehouse inventory retained: **EUR 12,651.45**.
- **No-shipment objective: EUR 16,218.39**.

The incremental modeled value of policy `m` is `Delta Z_m = Z_m - Z_no_shipment`.

| Allocation policy | Total objective (EUR) | Increment over no shipment (EUR) |
|---|---:|---:|
| **Full MILP** | **45,657.45** | **29,439.06** |
| Exposure-aware greedy | 45,507.60 | 29,289.21 |
| Demand-proportional | 38,075.47 | 21,857.08 |
| Request-based | 22,615.67 | 6,397.28 |

On **incremental value**, the MILP improves upon the request-based, demand-proportional and exposure-aware greedy policies by **360.18%**, **34.69%** and **0.51%**, respectively. The corresponding comparisons of *total* objectives are different (approximately **101.88%**, **19.91%** and **0.33%**). The report prioritizes incremental comparisons because all total objectives include value present without replenishment.

All four policies ship 392 units; their performance differences result from the **composition of shipments**, not the number of units shipped. The greedy comparator is explicitly exposure-aware and performs nearly as well as the MILP on this one synthetic dataset.

## 3. Repository structure

```text
zara-inventory-optimization/
├── data/                         # Six authoritative synthetic input CSVs
├── src/                          # Model and experiment scripts
│   ├── build_zara_data.py
│   ├── solve_zara_final.py
│   ├── verify_saved_results.py
│   ├── compare_zara_revised.py
│   ├── exposure_aware_greedy.py
│   ├── zara_ablation_experiment.py
│   ├── zara_sensitivity_detailed_repro.py
│   ├── zara_sensitivity_safe.py
│   ├── demand_stress_test.py
│   ├── exposure_robustness.py
│   └── plot_threshold_sensitivity.py
├── results/                      # Archived and independently reproduced outputs
│   └── figures/
│       ├── threshold_sensitivity_updated.png
│       └── threshold_sensitivity_updated.pdf
├── zara_no_shipment_incremental.py
├── requirements.txt
└── README.md
```

The six original input files are `stores.csv`, `articles.csv`, `warehouse.csv`, `store_article_size.csv`, `saturation_segments.csv` and `model_settings.csv`. Together, they provide 10 stores, 5 articles, 20 warehouse article–size records, 200 store–article–size records and 800 saturation segment records.

The updated threshold-sensitivity figure is available in **PNG and PDF** under `results/figures/`, with its generating code in `src/plot_threshold_sensitivity.py`. The final report and poster are not included in this repository at the time of this README revision.

## 4. Installation and baseline verification

Use Python from the project root. The commands below use the Windows Python launcher (`py`); on other systems, substitute `python` where appropriate.

```powershell
py -m pip install -r requirements.txt
py src/verify_saved_results.py
```

`requirements.txt` pins **Pyomo 6.10.1** and **highspy 1.15.1**, the packages used in the documented Windows reproductions. `verify_saved_results.py` performs read-only checks of stored data and results.

To re-solve the baseline MILP:

```powershell
py src/solve_zara_final.py
```

This script reads the six input files from `data/`, solves with HiGHS, checks the resulting allocation and writes `results/revised_allocation.csv` and `results/revised_remaining_stock.csv`. **Back up these two files before rerunning** if you wish to preserve the exact previously committed allocation; the solver can return another equally good allocation.

The baseline was also reproduced on **15 November 2026** using:

```powershell
py src/zara_sensitivity_safe.py --only Baseline --seconds 180
```

Its recorded result is `results/baseline_reproduction_2026-11-15.csv`. That file reports solver-optimal termination and the baseline objective, but **does not export the numerical best bound or MIP gap**.


### Two-store analytical validation

The report includes a two-store, one-article
validation example with a mathematically
proven global optimum of EUR 57.60.

Reproduce the computational validation with:

```powershell
py src/validate_two_store.py
```

The script solves the small MILP using
Pyomo and HiGHS and checks that the solver
reproduces the analytical optimum of
EUR 57.60, with 5.76 expected sales units,
six warehouse units shipped, and none retained.

This validates the small example independently
of the full 10-store model. It does not establish
exact global optimality of the full model.


### Exact regeneration of the synthetic inputs

```powershell
py src/build_zara_data.py
```

The generator uses `random.Random(20261031)` and writes regenerated files into the separate, Git-ignored `generated_data/` directory, **not** over the authoritative `data/` files. Independent regeneration confirmed that all six CSVs matched the committed inputs byte-for-byte. The underlying totals are **2,356 forecast-demand units**, **279 initial store inventory units**, **483 warehouse units**, and **392 units of store receiving capacity**.

## 5. Reproducing the benchmark comparisons

The request-based and demand-proportional policies are implemented in `src/compare_zara_revised.py`. The demand-proportional implementation allocates article–size units iteratively to the eligible store with the smallest fulfilled fraction of initial unmet demand; ties favor larger unmet demand and then fixed store order. Neither simple benchmark chooses shipments using exposure, saturation or retained-inventory value.

A fast, **read-only** check of the existing policy shipments and evaluations:

```powershell
py src/compare_zara_revised.py --check-only
```

To regenerate the benchmark evaluations using Pyomo/HiGHS:

```powershell
py src/compare_zara_revised.py
```

The outputs include:

- `results/revised_benchmark_comparison_rerun.csv`
- `results/revised_request_based_shipments_rerun.csv`
- `results/revised_demand_proportional_shipments_rerun.csv`

These reproduce **EUR 22,615.67** for request-based allocation and **EUR 38,075.47** for demand-proportional allocation under the common original model. The reported policies are generated by this *revised* implementation, not an older version with a different tie-breaking rule.

The stronger, exposure-aware greedy policy is in `src/exposure_aware_greedy.py`:

```powershell
py src/exposure_aware_greedy.py
```

It evaluates one-unit shipments and exposure-completing bundles based on their positive incremental modeled value per shipped unit. It respects stock and store-capacity constraints but **does not guarantee the global MILP optimum**. The verified result is **EUR 45,507.60** (392 shipped, 91 retained; 47 full-, 2 partial- and 1 no-exposure store–article combinations). Its near-optimal performance is specific to this dataset and does not independently validate the assumed sales model.

Reproduce the no-shipment reference and incremental comparisons with:

```powershell
py zara_no_shipment_incremental.py
```

Output: `results/no_shipment_incremental_comparison.csv`. This script reads the original synthetic inputs and saved benchmark results; it **does not change model assumptions or allocate shipments**.

## 6. Sensitivity analysis: archived versus updated solves

The original eleven-scenario archive is `results/zara_sensitivity_detailed.csv`. It contains **7 solver-optimal terminations and 4 feasible solutions stopped by the original 120-second limit**. Those are *historical statuses*, not the status of the final analysis.

The four previously time-limited cases have since been rerun: the **baseline**, **`rho=0.8`**, **`threshold=4`**, and **`stock=0.8x`**. The **`capacity=0.8x`** case was also rerun to confirm its previous optimal status. These runs reported optimal termination within their solver tolerances. This is numerical certification, **not an exact analytical proof**.

| Scenario | Final modeled objective (EUR) | Updated evidence |
|---|---:|---|
| Baseline | 45,657.45 | Separate reproduced baseline solve |
| Partial exposure `rho=0.8` | 45,665.60 | `zara_sensitivity_rho_0_8_2026-11-15.csv` |
| Full threshold `threshold=4` | 44,638.06 | 300-second rerun, 0.0099% reported gap |
| Warehouse stock `stock=0.8x` | 41,874.40 | 300-second rerun, 0.0097% reported gap |
| Receiving capacity `capacity=0.8x` | 42,844.50 | Independently repeated, 0.0007% reported gap |

The last three results are in **`results/zara_sensitivity_detailed_rerun.csv`**, while the separate `rho=0.8` and baseline reproductions are stored in the files named above. The other seven scenarios retain their archived solver-optimal status; they have not all been independently rerun in the same 300-second batch.

The other reported sensitivity objectives are:

| Scenario | Modeled objective (EUR) |
|---|---:|
| Partial factor `rho=0.4` | 45,657.45 |
| Full threshold `threshold=2` | 45,853.10 |
| Warehouse stock `stock=1.2x` | 48,640.85 |
| Receiving capacity `capacity=1.2x` | 47,686.95 |
| Retained value `rate=0.20` | 44,945.40 |
| Retained value `rate=0.50` | 46,369.50 |

**Preserving historical evidence:** The recovered original script had written `gap_percent=0` when a run terminated with status `optimal`, even when the recorded upper bound exceeded the incumbent. Those historical zeros must **not** be interpreted as measured zero gaps. The restored script records bound-derived numerical gaps for new reruns.

Read-only check of the original eleven archived scenarios:

```powershell
py src/zara_sensitivity_detailed_repro.py --check-archive
```

To reproduce one of the updated detailed scenarios, for example:

```powershell
py src/zara_sensitivity_detailed_repro.py --only "threshold=4" --seconds 300 --retry
```

**Caution:** This command can update the corresponding row in `results/zara_sensitivity_detailed_rerun.csv`. Make a copy before rerunning if you need to retain the exact recorded result. The original `results/zara_sensitivity_detailed.csv` is never overwritten by this script.

### Threshold-sensitivity figure

The updated graph uses `threshold=2` and the baseline from the original archive, plus the updated `threshold=4` result from the rerun CSV:

```powershell
py -m pip install matplotlib
py src/plot_threshold_sensitivity.py
```

`matplotlib` is an **additional dependency for plotting** and is not currently included in `requirements.txt`. The script writes `results/figures/threshold_sensitivity_updated.png` and `.pdf`.

## 7. Demand-scarcity stress tests

Forecast demand is intentionally large enough that **none of the 200 baseline forecast-demand ceilings binds**. The demand tests investigate this limitation by reducing forecasts while keeping other model inputs unchanged. This is a model-calibration limitation, not evidence about Zara's actual demand.

```powershell
py src/demand_stress_test.py --factor 0.40 --seconds 180
py src/demand_stress_test.py --factor 0.20 --seconds 180
```

The results are saved separately in `results/zara_demand_stress_test.csv`.

| Measure | Baseline | 40% demand | 20% demand |
|---|---:|---:|---:|
| Modeled objective (EUR) | 45,657.45 | 44,883.00 | 35,977.57 |
| Expected sales units | 566.20 | 559.15 | 446.48 |
| Units shipped | 392 | 392 | 360 |
| Units retained | 91 | 91 | 123 |
| Fully exposed store–article combinations | 50 | 50 | 49 |
| Binding forecast-demand ceilings | 0 | 11 | 139 |
| Changed shipment variables vs baseline | — | 53 | 106 |

Both stress-test runs reported solver-optimal termination; their output CSV does not export the numerical best bound or final MIP gap. These are **hypothetical, severe demand reductions**, not estimates of realistic market changes.

## 8. Ablation experiments: exposure and saturation

The ablation experiments optimize three policies on identical baseline inputs: (1) the original exposure-and-saturation MILP, (2) a model **without exposure**, and (3) a model with exposure but **linear sales** instead of saturation.

Because their internal objective functions differ, **native objectives must not be compared directly**. We instead fix each resulting shipment allocation and evaluate it using the original MILP's sales and retained-stock assumptions.

Read-only archival check:

```powershell
py src/zara_ablation_experiment.py --check-archive
```

Fresh three-model solve:

```powershell
py src/zara_ablation_experiment.py --seconds 300
```

The rerun writes `results/zara_ablation_comparison_rerun.csv` and `results/zara_ablation_shipments_rerun.csv`, preserving the original archived results. The verified rerun reproduced the **same 200 shipment decisions per policy** as the original archive.

| Shipment allocation, evaluated under original model | Value (EUR) | Loss vs full MILP | Full exposure |
|---|---:|---:|---:|
| Full MILP | 45,657.45 | 0.00% | 50 |
| Without exposure | 30,920.85 | 32.28% | 17 |
| Linear sales | 42,975.55 | 5.87% | 50 |

The exposure-ignorant allocation has 17 full-, 14 partial- and 19 no-exposure store–article combinations under the original model's eligibility rules. The linear-sales allocation achieves full exposure everywhere but loses modeled value under the original concave saturation functions. These losses measure **allocation quality under the assumed model**, not changes in observed retail sales.

## 9. Residual-exposure robustness experiment

The baseline assumes zero modeled sales for assortments that fail the partial-exposure requirement. To test that strong assumption, the robustness experiment allows **20% residual sales potential** when exposure is absent; the partial factor remains 60% and full exposure remains 100%.

```powershell
py src/exposure_robustness.py --residual 0.20 --seconds 300
```

This script reoptimizes the **softened-exposure MILP** and evaluates saved full-MILP and exposure-ignorant allocations under the **same softened sales assumptions**. Its default saved exposure-ignorant input is `results/zara_ablation_shipments.csv`. We independently reran that exposure-ignorant model and verified that its **entire shipment CSV matches the archive exactly**; therefore this saved policy is also the freshly reproduced exposure-ignorant allocation. The exposure-ignorant *optimization problem itself* does not depend on `eta`, so this is **not** a policy that adapts its shipments in response to residual exposure.

| Common evaluation | Zero residual exposure | 20% residual exposure |
|---|---:|---:|
| Optimized MILP value (EUR) | 45,657.45 | 45,657.45 |
| Exposure-ignorant allocation value (EUR) | 30,920.85 | 32,819.82 |
| Exposure-ignorant loss relative to MILP | 32.28% | 28.12% |

The softened MILP reported solver-optimal termination and still achieved full exposure for all 50 store–article combinations. Its **numerical final bound and MIP gap were not saved**. The residual factor `eta = 0.20` is a hypothetical scenario, not a calibrated sales parameter.

Output: `results/zara_exposure_robustness.csv`.

## 10. Analytical validation, reproducibility limits and interpretation

The project report also presents an independently proved, **two-store / one-article** validation problem. With six warehouse units, the analytical global optimum is **EUR 57.60**, reproduced by Pyomo. This separate example checks the formulation's exposure, saturation, inventory-conservation and objective logic; it does **not** establish exact global optimality of the full 10-store model.

**What is verified:**

- The original synthetic inputs can be regenerated exactly from the fixed seed.
- The saved baseline allocation passes inventory, exposure, sales and objective checks.
- The request-based, demand-proportional, greedy and ablation results have been independently reproduced or checked against fixed shipment allocations.
- The formerly time-limited baseline and selected sensitivity scenarios were rerun with solver-reported optimal termination within configured tolerances.
- The no-shipment and residual-exposure comparisons use the same economic evaluation rules within each experiment.

**Limitations:**

- All prices, stock, demand, exposure thresholds, saturation functions and retained-stock values are synthetic or hypothetical.
- The model has one period and deterministic forecasts; transportation, procurement, holding and expansion costs are omitted.
- The model assigns future economic value to warehouse retention but not to unsold store inventory, a simplifying asymmetry.
- No baseline forecast-demand ceiling binds; stress testing partially explores this weakness.
- Several original solver results were time-limited; subsequent numerical solves improve the evidence but are not exact proofs. Raw historical solver logs are unavailable, and numerical MIP gaps were not exported by every reproduction script.
- The exposure-aware greedy policy is nearly as good as the MILP on this one instance; performance across other synthetic seeds or real datasets is not established.

The project's numerical results describe **the consequences of its assumptions**, rather than measured effects of Zara's real inventory decisions.

## 11. Reference

Caro, F., Gallien, J., Díaz, M., García, J., Corredoira, J. M., Montes, M., Ramos, J. A., & Correa, J. (2010). **Zara Uses Operations Research to Reengineer Its Global Distribution Process.** *Interfaces, 40*(1), 71–84. https://doi.org/10.1287/inte.1090.0472
