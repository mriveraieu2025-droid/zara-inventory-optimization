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

**Current verification status (16 November 2026):** The baseline model has been rerun locally with solver-reported optimal termination; saved allocations have also passed independent feasibility and objective checks. Additional local solves completed the 40%/20% demand stress tests, rho=0.8 sensitivity rerun, residual-exposure robustness test, and exposure-aware greedy benchmark. The original synthetic-data generator, the original data-generation script and the script/logs that produced the detailed 120-second sensitivity table are not currently in this repository. Archived results are retained, but their original generation workflow is not yet fully reproducible.

## Current repository layout
- `data/` — six authoritative synthetic input CSVs.
- `src/` — Pyomo MILP, greedy benchmark, demand and exposure robustness, sensitivity rerun, and independent verification scripts.
- `results/` — archived and freshly reproduced numerical results.
- `requirements.txt` — recorded Python dependencies.

The report, figures and poster are not yet committed here. The original synthetic-data generator and historical 120-second sensitivity-result producer remain unarchived. The ablation producer is now restored, with safe rerun outputs; the archived result CSVs are also available. The baseline and selected additional experiments have been rerun locally, as documented below.

## Citation
Caro, F., Gallien, J., Díaz, M., García, J., Corredoira, J. M., Montes, M., Ramos, J. A., and Correa, J. (2010). *Zara Uses Operations Research to Reengineer Its Global Distribution Process*. Interfaces, 40(1), 71–84. https://doi.org/10.1287/inte.1090.0472


### Fresh local baseline solver run (15 November 2026)
- Executed on Windows using **Pyomo 6.10.1**, **highspy 1.15.1**.
- Command: `py src/zara_sensitivity_safe.py --only Baseline --seconds 180`.
- Console reported six CSV inputs loaded, saturation/big-M checks passed, and one scenario with **optimal** termination.
- Saved result: `results/baseline_reproduction_2026-11-15.csv`.
- Objective: **EUR 45,657.45**, expected sales revenue **EUR 43,996.00**, retained-inventory value **EUR 1,661.45**, 392 units shipped, 91 retained, and 50/50 full exposure.
- The CSV records **`status=optimal`** but does **not include a solver bound or MIP-gap column**. Do not claim an independently verified exactly-zero gap from this output alone.
- Note: this run verifies the baseline solve. Later local runs additionally verified demand-stress scenarios, rho=0.8 sensitivity, residual-exposure robustness and the exposure-aware greedy benchmark; historical ablation and other detailed sensitivity scenarios have not all been freshly rerun.


### Main-model reproduction (15 November 2026)
- On Windows, ran `py solve_zara_final.py` with Pyomo 6.10.1 and highspy 1.15.1.
- Console: all six CSVs loaded; saturation/big-M checks passed; **Solver termination: optimal**; **ALL SOLUTION CHECKS PASSED!**
- Objective **EUR 45,657.45** = EUR 43,996.00 modeled sales revenue + EUR 1,661.45 assigned retained-inventory value.
- **392 shipped**, **91 retained**, **566.20 modeled expected sales**, **50/50 full exposure**.
- Script saved `revised_allocation.csv` and `revised_remaining_stock.csv` on the user's computer. These fresh output files are archived in `results/revised_allocation.csv` and `results/revised_remaining_stock.csv`.
- Reported solver status is optimal; no raw solver bound/gap shown in the captured terminal output. Selected sensitivity/robustness runs have since been completed, while the full historical 120-second sensitivity producer remains to be recovered or recreated; the ablation producer has now been restored.


## Reproducing the original ablation experiment

The original ablation experiment script was recovered from the author's local files and adapted for this repository's `src/`, `data/`, and `results/` layout. Its three experimental formulations and fixed-allocation evaluation are retained.

**First, a fast read-only archival check** (does not rerun HiGHS or overwrite outputs):

```powershell
py src/zara_ablation_experiment.py --check-archive
```

This validates the original archived shipment policies against the six input CSVs and common full-model evaluation. Expected values are EUR 45,657.45 (full), EUR 30,920.85 (no exposure), and EUR 42,975.55 (linear sales).

**Optional full three-scenario rerun** (each solve can use up to 180 seconds):

```powershell
py src/zara_ablation_experiment.py --seconds 180
```

This rerun records solver incumbents/bounds and writes **new files only**: `results/zara_ablation_comparison_rerun.csv` and `results/zara_ablation_shipments_rerun.csv`. The original `results/zara_ablation_comparison.csv`, `results/zara_ablation_shipments.csv`, input data, and baseline allocation remain unchanged. Because MILP allocations need not be unique, a rerun may give different shipment details while matching or nearly matching the archived objective.

### Verified ablation rerun (16 November 2026)

The original ablation experiment was rerun locally with `py src/zara_ablation_experiment.py --seconds 180`. All three HiGHS models returned solver-reported optimal termination within the configured **0.01% relative MIP-gap tolerance**.

New outputs are archived separately as:
- `results/zara_ablation_comparison_rerun.csv`
- `results/zara_ablation_shipments_rerun.csv`

Independent checks confirmed that every one of the 200 shipment decisions per policy exactly matches the original archived shipment CSV. Re-evaluation under the common full-model rules gives:
- Full MILP: **EUR 45,657.45** (50 full exposure)
- No exposure: **EUR 30,920.85** (17 full, 14 partial, 19 none)
- Linear sales: **EUR 42,975.55** (50 full)

All three policies ship 392 units and retain 91. Original archived files were **not overwritten**. Solver-reported relative gaps in the rerun summary: approximately 0.010%, 0.000%, and 0.010% for full, no-exposure, and linear-sales variants, respectively. These are numerical tolerance certificates rather than mathematical proofs of exact zero gap.

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


### Partial-exposure sensitivity: rho=0.8 rerun (15 November 2026)

The local command `py src/zara_sensitivity_safe.py --only "rho=0.8" --seconds 300 --retry-timeouts` reran ONLY the partial-exposure factor 0.8 scenario, keeping all other input assumptions unchanged. It reported **optimal** termination and was archived at `results/zara_sensitivity_rho_0_8_2026-11-15.csv`.

- Modeled objective **EUR 45,665.60** = EUR 44,058.05 expected sales revenue + EUR 1,607.55 assigned retained-stock value.
- 564.67 expected sales units, 392 units shipped, 91 retained, 48 full-exposure + 2 partial-only combinations.
- Compared with reproduced baseline `rho=0.6` objective EUR 45,657.45, this is **EUR 8.15 higher** (approximately **0.0179%**). It is possible for expected sales units to decline while revenue rises because product prices differ.
- The older 120-second sensitivity output contained a time-limited feasible incumbent EUR 45,625.90; that is **not** the proven optimum and should be replaced in the principal sensitivity results table.
- The new output CSV reports `status=optimal` but does not record the solver bound or numeric relative MIP gap. The 300-second rerun must be identified separately from the original 120-second sensitivity experiments. The older `results/zara_sensitivity_detailed.csv` is retained as an archival record, not the authoritative `rho=0.8` result.


## Exposure-assumption robustness experiment (completed; reproduction instructions)

The baseline synthetic model assumes **zero** expected current sales if a store/article fails to meet the partial-exposure threshold for every major size. This is deliberately strong. The new script `src/exposure_robustness.py` changes only that assumption:

- No exposure: `e = eta` (proposed `eta=0.20`, meaning 20% of the concave saturation potential).
- Partial exposure: `e = rho = 0.60`, unchanged.
- Full exposure: `e = 1.00`, unchanged.

The script verifies that the archived no-exposure-policy and full-MILP allocations reproduce their original **zero-residual** ablation evaluations. It then (a) values both saved shipment allocations under the **same softened exposure rule** and (b) reoptimizes the MILP using a separate set of linear constraints that implement this rule. This avoids comparing objectives from different economic models.

Run after downloading the latest GitHub ZIP, inside the **innermost project folder**:

```powershell
py src/exposure_robustness.py --residual 0.20 --seconds 300
```

Results will be written to `results/zara_exposure_robustness.csv`. Original baseline data, earlier ablation/sensitivity outputs, and the report are left untouched. If HiGHS times out, the script records the termination status without mislabeling the result as a proved optimum. Any new result requires numerical verification before inclusion in the report. The 20% residual level is hypothetical, not calibrated to observed Zara sales.


### Completed residual-exposure robustness check (15 November 2026)

**Local command:** `py src/exposure_robustness.py --residual 0.20 --seconds 300`. The CSV `results/zara_exposure_robustness.csv` has been uploaded and its arithmetic independently checked.

- No-exposure factor `eta=0.20`; partial exposure `rho=0.60`; full exposure `1.00`.
- The reoptimized softened-exposure MILP reported `optimal` termination with objective **EUR 45,657.45** (sales revenue EUR 43,996.00, retention EUR 1,661.45), 392 units shipped and 91 retained; 50/50 full exposure.
- Fixed baseline shipment allocation evaluated under the softened model: **EUR 45,657.45**.
- Fixed exposure-ignorant shipment allocation evaluated under the **same** softened model: **EUR 32,819.82**. Under the original zero-residual rule this fixed allocation was worth EUR 30,920.85.
- Difference vs the softened optimized model: **28.12% lower**, vs 32.28% lower under the original exposure rule.
- **Scope note:** the exposure-ignorant allocation was *not* reoptimized for the softened sales rule; it is the previously saved no-exposure allocation evaluated under the new common rule. The 20% residual factor is hypothetical, not an estimate of observed retail behavior.
- The CSV records solver-reported optimal termination but does not include a numerical solver bound or MIP gap.


## Stronger benchmark: deterministic exposure-aware greedy policy

Source: \`src/exposure_aware_greedy.py\`. This script is deliberately **not** a MILP solver and does **not** use the saved MILP allocation to choose shipments. It uses the six synthetic input CSV files to make a deterministic greedy decision at each step:

1. Consider feasible bundles of missing major sizes that would activate partial/full exposure.
2. Consider feasible one-unit additions for individual store/article/size combinations.
3. For each action, compute its incremental current-sales value using the **full original exposure and piecewise saturation model**, minus the retained-stock opportunity value of the shipped units.
4. Select the strictly positive action with the largest net gain per unit; use stable input order to resolve ties.
5. Repeat until no improving feasible action remains.

The policy respects article/size warehouse stock and each store's receiving capacity. It evaluates both its own shipments and the saved baseline MILP shipments under the **same original model**, and checks the baseline objective is EUR 45,657.45. The script outputs:
- \`results/zara_exposure_aware_greedy_summary.csv\`
- \`results/zara_exposure_aware_greedy_shipments.csv\`

Run in the project root:

\`\`\`powershell
py src/exposure_aware_greedy.py
\`\`\`

An independently tested copy on the preserved input dataset obtained a preliminary objective **EUR 45,507.60**, with 392 shipped, 91 retained, 47 fully exposed, two partially exposed and one non-exposed store/article combinations. This is approximately **0.33%** below the reproduced MILP objective, but is **not** a measured gain in real Zara sales. Before inclusion in the final report, reproduce the output from the GitHub script and preserve both output CSVs.

This is a much stronger heuristic than the request-based or demand-proportional baselines, since it **explicitly uses the model's exposure, saturation, price, and retention assumptions**. Accordingly, it is not an independent empirical validation of those assumptions.


### Verified exposure-aware greedy benchmark (15 November 2026)

Local reproduction using `py src/exposure_aware_greedy.py` passed the warehouse-stock and store-capacity checks and reproduced the same full-model evaluation of the saved MILP allocation.

Saved results:
- `results/zara_exposure_aware_greedy_summary.csv` (reported outcomes)
- `results/zara_exposure_aware_greedy_shipments.csv` (200 integer shipment decisions)

Independent recalculation from the six input CSVs verified:
- **EUR 45,507.60 modeled objective** = **EUR 43,872.75 current sales revenue** + **EUR 1,634.85 assigned retained value**.
- **562.29 expected sales units**, **392 shipped**, **91 retained**; all warehouse article/size balances and all ten receiving-capacity inequalities satisfied.
- **47 full-exposure, 2 partial-only, 1 no-exposure** store–article combinations.
- **80 of 200** individual shipment quantities differ from the saved full MILP; because the total shipment count is identical, **77 units are reallocated** between shipment locations/categories (half of sum of absolute shipment differences).
- MILP objective **EUR 45,657.45**, which is **EUR 149.85 (0.3293%) greater relative to the greedy benchmark**.
- This is a deterministic **model-aware heuristic**, using the same exposure, saturation, prices, and retention assumptions as the MILP. Near-optimality on this ONE synthetic instance does not prove greedy always performs this well, nor does it independently validate the sales assumptions.

Final paper should present this strong comparator along with the original simpler request and demand-proportional benchmarks, avoiding claims of guaranteed large MILP improvements over well-informed heuristics.
