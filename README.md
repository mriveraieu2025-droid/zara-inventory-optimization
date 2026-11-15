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
- Command: `py zara_sensitivity_safe.py --only Baseline --seconds 180`.
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
