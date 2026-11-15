# Zara Inventory Optimization — Optimization I Final Project

A synthetic, single-period inventory-allocation study inspired by Caro et al. (2010), *Zara Uses Operations Research to Reengineer Its Global Distribution Process*.

## Project at a glance
- **Method:** Mixed-Integer Linear Programming (MILP) using Python/Pyomo and HiGHS.
- **Network:** one warehouse, ten stores, five articles, four sizes, one replenishment period.
- **Decision:** integer shipments by store/article/size and retained warehouse quantities.
- **Sales model:** size-exposure thresholds plus concave piecewise-linear saturation.
- **Objective:** modeled expected current sales revenue **plus assigned retained-inventory value**; **not net profit**.
- **Data:** synthetic, not actual Zara records.

## Step 1: numerical verification status
Saved results passed an independent arithmetic and feasibility audit:
- **EUR 45,657.45** total modeled value = **EUR 43,996.00** sales revenue + **EUR 1,661.45** retained-stock value.
- **483 warehouse units = 392 shipped + 91 retained**.
- All **50** store–article combinations qualify for full exposure.
- The separate two-store validation problem has an independently proved optimum of **EUR 57.60**.

**Important: still pending.** The final Pyomo/HiGHS solver must be rerun locally; historical solver optimality labels have not been independently recertified. The exact original synthetic data-generation script and raw solver logs are still to be confirmed. The model settings CSV was reconstructed from the report, so compare it with the original local file.

## Planned layout
- `data/` — six input CSVs and data provenance.
- `src/` — model, benchmark, sensitivity, ablation and verification code.
- `results/` — saved solutions and audited summary files.
- `figures/` — plots generated from solutions.
- `report/` — technical report.
- `poster/` — final academic poster.

Reproduction instructions, exact software versions and full experiments will be added as files are checked and uploaded. Do not treat the reported numerical values as results from a newly rerun solver.

## Citation
Caro, F., Gallien, J., Díaz, M., García, J., Corredoira, J. M., Montes, M., Ramos, J. A., and Correa, J. (2010). *Zara Uses Operations Research to Reengineer Its Global Distribution Process*. Interfaces, 40(1), 71–84. https://doi.org/10.1287/inte.1090.0472


### Fresh local baseline solver run (15 November 2026)
- Executed on Windows using **Pyomo 6.10.1**, **highspy 1.15.1**.
- Command: `py src/zara_sensitivity_safe.py --only Baseline --seconds 180`.
- Console reported six CSV inputs loaded, saturation/big-M checks passed, and one scenario with **optimal** termination.
- Saved result: `results/baseline_reproduction_2026-11-15.csv`.
- Objective: **EUR 45,657.45**, expected sales revenue **EUR 43,996.00**, retained-inventory value **EUR 1,661.45**, 392 units shipped, 91 retained, and 50/50 full exposure.
- The CSV records **`status=optimal`** but does **not include a solver bound or MIP-gap column**. Do not claim an independently verified exactly-zero gap from this output alone.
- Note: the fresh local run verifies the baseline solve, but does not yet rerun all sensitivity, benchmark, and ablation experiments.


### Main-model reproduction (15 November 2026)
- On Windows, ran `py solve_zara_final.py` with Pyomo 6.10.1 and highspy 1.15.1.
- Console: all six CSVs loaded; saturation/big-M checks passed; **Solver termination: optimal**; **ALL SOLUTION CHECKS PASSED!**
- Objective **EUR 45,657.45** = EUR 43,996.00 modeled sales revenue + EUR 1,661.45 assigned retained-inventory value.
- **392 shipped**, **91 retained**, **566.20 modeled expected sales**, **50/50 full exposure**.
- Script saved `revised_allocation.csv` and `revised_remaining_stock.csv` on the user's computer. These fresh output files are archived in `results/revised_allocation.csv` and `results/revised_remaining_stock.csv`.
- Reported solver status is optimal; no raw solver bound/gap shown in the captured terminal output. Separate sensitivity and ablation experiment reruns are pending.


## Re-run the verified baseline from this repository

From the repository root, with Python, Pyomo and HiGHS installed:

```powershell
py -m pip install -r requirements.txt
py src/verify_saved_results.py
py src/solve_zara_final.py
```

The main script loads the six input CSVs from `data/` and saves the baseline allocation to `results/`. Keep a copy of saved outputs before rerunning if you need to preserve an earlier allocation variant.

## Demand-scarcity stress test (two scenarios completed)

```powershell
py src/demand_stress_test.py --factor 0.40 --seconds 180
py src/demand_stress_test.py --factor 0.20 --seconds 180
```

The script changes **forecast demand only**, with integer half-up rounding, and writes `results/zara_demand_stress_test.csv`. It does **not** modify the original inputs or baseline outputs. If a solve hits the time limit, it records the status without asserting optimality. Additional factors can be tested in separate runs. Both runs have been completed and the output CSV has been saved to this repository. The saved statuses are solver-reported optimal; numerical MIP gaps and raw bounds were not exported.


### Demand sensitivity: 40% forecast scenario (15 November 2026)

A new local Pyomo/HiGHS run with `py src/demand_stress_test.py --factor 0.40 --seconds 180` reports **optimal** termination. Forecast demand alone was rescaled, with all original stock, capacities, prices, exposure and saturation parameters unchanged. The result is archived at `results/zara_demand_stress_test.csv`.

- Modeled objective: **EUR 44,883.00**, consisting of **EUR 43,200.55** modeled current sales revenue and **EUR 1,682.45** assigned retained-stock value.
- 392 units shipped; 91 retained; 559.15 expected sales units; all 50 store–article pairs full exposure.
- **11 of 200 positive forecast-demand ceilings bind**, compared with zero at baseline.
- **53 of 200 individual shipment quantities differ** from the archived baseline solution (a count of changed entries, not the number of units reallocated).
- Same aggregate retained quantity but different article/size composition: retained value differs from baseline.

**Interpretation:** reducing all synthetic forecasts to 40% of their original levels decreases modeled value and changes the allocation, but demand is still nonbinding in most combinations. This is an intentionally severe sensitivity scenario, not an estimate of actual Zara demand. A 20% demand stress test below produces a more strongly demand-constrained case.

### Demand sensitivity: 20% forecast scenario (15 November 2026)

The additional local HiGHS run with `py src/demand_stress_test.py --factor 0.20 --seconds 180` reports **optimal** termination, archived together with the 40% result at `results/zara_demand_stress_test.csv`. Forecasts were independently multiplied by 0.20 with half-up integer rounding; original input CSVs were unchanged.

- Objective: **EUR 35,977.57** = **EUR 32,674.62** expected sales revenue + **EUR 3,302.95** assigned retained-stock value.
- **446.48** expected sales units, **360** units shipped and **123** units retained (warehouse total remains 483).
- **49 full-exposure**, **1 partial-exposure** store–article combination, **0 no-exposure**.
- **139/200** positive demand ceilings binding, versus zero in the original baseline.
- **106/200** individual shipment variables differ from the baseline solution; this counts changed decisions, not the total quantity of stock relocated.
- Compared with baseline EUR 45,657.45, the modeled objective declines by approximately **21.2%**. This comparison changes the demand assumptions and is not an estimate of actual retailer losses.

Together, the 40% and 20% scenarios show an increasingly demand-constrained model: demand reductions initially change shipment composition without aggregate shipment reduction, then also reduce aggregate shipments and increase warehouse retention. These intentionally extreme shocks explore model behavior, not likely fluctuations in actual Zara sales. Additional sensitivity scenarios or repeated synthetic datasets would be needed to establish broad robustness.
