"""Recovered original detailed 120-second Zara sensitivity producer.

Adapted to the repository layout so the original results are protected.
Use --check-archive to verify the 11 historical rows without solving.
A full rerun writes results/zara_sensitivity_detailed_rerun.csv only.
Corrects an old reporting issue that forced all solver-optimal gaps to 0.000%%,
even when the reported upper bound and incumbent implied a small nonzero gap.
Original scenario definitions and MILP constraints are unchanged.
"""


import argparse
import csv
import math
import time

from copy import deepcopy
from pathlib import Path

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs
from pyomo.contrib.appsi.base import TerminationCondition

from solve_zara_final import load_data, build_model


# ============================================================
# ZARA FINAL PROJECT
# SENSITIVITY ANALYSIS WITH FEASIBLE SOLUTIONS AND MIP GAPS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
OUTPUT = RESULTS / "zara_sensitivity_detailed_rerun.csv"
ARCHIVED = RESULTS / "zara_sensitivity_detailed.csv"

FIELDS = [
    "group",
    "scenario",
    "status",
    "best_feasible_objective_eur",
    "best_upper_bound_eur",
    "gap_percent",
    "sales_revenue_eur",
    "retained_inventory_value_eur",
    "expected_sales_units",
    "units_shipped",
    "units_retained",
    "full_exposure",
    "partial_only",
    "no_exposure",
    "elapsed_seconds",
    "note",
]


# ============================================================
# 1. SCENARIO DEFINITIONS
# ============================================================

def rounded_units(value, factor):
    return int(math.floor(value * factor + 0.5))


def make_scenarios():
    return [
        (
            "Base case",
            "Baseline",
            lambda d: None
        ),
        (
            "Partial factor",
            "rho=0.4",
            lambda d: d["settings"].update(
                partial_exposure_factor=0.4
            )
        ),
        (
            "Partial factor",
            "rho=0.8",
            lambda d: d["settings"].update(
                partial_exposure_factor=0.8
            )
        ),
        (
            "Full threshold",
            "threshold=2",
            lambda d: d["settings"].update(
                full_threshold=2.0
            )
        ),
        (
            "Full threshold",
            "threshold=4",
            lambda d: d["settings"].update(
                full_threshold=4.0
            )
        ),
        (
            "Warehouse stock",
            "stock=0.8x",
            lambda d: d.update(
                warehouse={
                    k: rounded_units(v, 0.8)
                    for k, v in d["warehouse"].items()
                }
            )
        ),
        (
            "Warehouse stock",
            "stock=1.2x",
            lambda d: d.update(
                warehouse={
                    k: rounded_units(v, 1.2)
                    for k, v in d["warehouse"].items()
                }
            )
        ),
        (
            "Store capacity",
            "capacity=0.8x",
            lambda d: d.update(
                capacity={
                    k: rounded_units(v, 0.8)
                    for k, v in d["capacity"].items()
                }
            )
        ),
        (
            "Store capacity",
            "capacity=1.2x",
            lambda d: d.update(
                capacity={
                    k: rounded_units(v, 1.2)
                    for k, v in d["capacity"].items()
                }
            )
        ),
        (
            "Retention value",
            "rate=0.20",
            lambda d: d.update(
                retention={
                    (a, s): 0.20 * d["price"][a]
                    for a in d["articles"]
                    for s in d["sizes"]
                }
            )
        ),
        (
            "Retention value",
            "rate=0.50",
            lambda d: d.update(
                retention={
                    (a, s): 0.50 * d["price"][a]
                    for a in d["articles"]
                    for s in d["sizes"]
                }
            )
        ),
    ]


# ============================================================
# 2. READ AND SAVE PREVIOUS RESULTS
# ============================================================

def load_previous_results():
    if not OUTPUT.exists():
        return {}

    with OUTPUT.open(
        "r", newline="", encoding="utf-8-sig"
    ) as f:
        return {
            row["scenario"]: row
            for row in csv.DictReader(f)
        }


def save_results(rows):
    RESULTS.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=FIELDS
        )
        writer.writeheader()
        writer.writerows(rows.values())


# ============================================================
# 3. SOLVE USING DIRECT APPSI HIGHS
# ============================================================

def solve_with_reporting(model, seconds):

    solver = Highs()

    if not solver.available():
        raise RuntimeError(
            "HiGHS is not available. Install highspy."
        )

    solver.config.time_limit = seconds

    # Important:
    # Do not automatically load a solution if optimality
    # has not been proven.
    solver.config.load_solution = False

    start = time.perf_counter()
    result = solver.solve(model)
    elapsed = time.perf_counter() - start

    condition = result.termination_condition

    incumbent = result.best_feasible_objective
    upper_bound = result.best_objective_bound

    optimal = (
        condition == TerminationCondition.optimal
    )

    has_solution = (
        incumbent is not None
        and math.isfinite(float(incumbent))
    )

    if optimal:
        status = "optimal"
    elif condition == TerminationCondition.maxTimeLimit:
        status = (
            "feasible_time_limit"
            if has_solution
            else "time_limit_no_solution"
        )
    else:
        status = (
            "feasible_not_optimal"
            if has_solution
            else "no_solution"
        )

    gap = None

    if (
        has_solution
        and upper_bound is not None
        and math.isfinite(float(upper_bound))
    ):
        incumbent = float(incumbent)
        upper_bound = float(upper_bound)

        # The objective is MAXIMIZED.
        # Incumbent is a lower bound on the optimum.
        # Dual bound is an upper bound on the optimum.
        gap = (
            max(0.0, upper_bound - incumbent)
            / max(abs(incumbent), 1e-10)
            * 100.0
        )

    # Preserve the numerical bound-derived gap even when HiGHS reports
    # optimal termination within its configured solver tolerance.
    # The historical producer overrode such gaps with 0.000%.

    # Load the best available feasible solution.
    # This works even if the solver reached the time limit,
    # as long as a feasible incumbent was found.
    if has_solution:
        result.solution_loader.load_vars()

    return {
        "status": status,
        "incumbent": (
            float(incumbent)
            if has_solution else None
        ),
        "upper_bound": (
            float(upper_bound)
            if upper_bound is not None
            and math.isfinite(float(upper_bound))
            else None
        ),
        "gap": gap,
        "elapsed": elapsed,
        "condition": str(condition),
        "has_solution": has_solution,
    }


# ============================================================
# 4. SUMMARIZE A FEASIBLE SOLUTION
# ============================================================

def summarize_solution(model):
    v = pyo.value

    revenue = sum(
        v(model.P[a] * model.z[i, a, s])
        for i in model.I
        for a in model.A
        for s in model.S
    )

    retained_value = sum(
        v(model.R[a, s] * model.r[a, s])
        for a in model.A
        for s in model.S
    )

    sales = sum(
        v(model.z[i, a, s])
        for i in model.I
        for a in model.A
        for s in model.S
    )

    shipped = sum(
        round(v(model.x[i, a, s]))
        for i in model.I
        for a in model.A
        for s in model.S
    )

    retained = sum(
        round(v(model.r[a, s]))
        for a in model.A
        for s in model.S
    )

    full = sum(
        round(v(model.v[i, a]))
        for i in model.I
        for a in model.A
    )

    partial = sum(
        round(v(model.u[i, a]))
        - round(v(model.v[i, a]))
        for i in model.I
        for a in model.A
    )

    total = len(model.I) * len(model.A)

    # Verify the objective calculation.
    assert abs(
        v(model.obj) - revenue - retained_value
    ) < 1e-3

    # Verify warehouse balance.
    for a in model.A:
        for s in model.S:
            total_stock = (
                sum(
                    v(model.x[i, a, s])
                    for i in model.I
                )
                + v(model.r[a, s])
            )

            assert abs(
                total_stock - v(model.H[a, s])
            ) < 1e-3

    # Verify store capacities.
    for i in model.I:
        total_shipments = sum(
            v(model.x[i, a, s])
            for a in model.A
            for s in model.S
        )

        assert (
            total_shipments
            <= v(model.C[i]) + 1e-3
        )

    # Verify that all other active constraints
    # are also satisfied.
    for c in model.component_data_objects(
        pyo.Constraint, active=True
    ):
        body = v(c.body)

        if c.has_lb():
            assert body >= v(c.lower) - 1e-3

        if c.has_ub():
            assert body <= v(c.upper) + 1e-3

    return {
        "sales_revenue_eur": round(revenue, 4),
        "retained_inventory_value_eur": round(
            retained_value, 4
        ),
        "expected_sales_units": round(sales, 4),
        "units_shipped": shipped,
        "units_retained": retained,
        "full_exposure": full,
        "partial_only": partial,
        "no_exposure": total - full - partial,
    }


# ============================================================
# 5. RUN ALL SCENARIOS
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seconds", type=int, default=120
    )

    parser.add_argument(
        "--only", type=str, default=None
    )

    parser.add_argument(
        "--retry", action="store_true"
    )
    parser.add_argument(
        "--check-archive", action="store_true",
        help="read-only check of original 120-second sensitivity CSV"
    )

    args = parser.parse_args()

    if args.seconds <= 0:
        parser.error(
            "Time limit must be positive."
        )

    print("\n" + "=" * 65)
    print("ZARA SENSITIVITY ANALYSIS - DETAILED RESULTS")
    print("=" * 65)

    print(
        f"Solver time limit: {args.seconds} seconds"
    )

    data = load_data()
    if args.check_archive:
        if not ARCHIVED.exists():
            raise FileNotFoundError(f"Original archived results not found: {ARCHIVED}")
        with ARCHIVED.open(newline="", encoding="utf-8-sig") as f:
            recorded = list(csv.DictReader(f))
        expected_names = {name for _, name, _ in make_scenarios()}
        if len(recorded) != len(expected_names) or {r["scenario"] for r in recorded} != expected_names:
            raise AssertionError("Original CSV does not contain exactly the 11 expected scenarios")
        counts = {"optimal": 0, "feasible_time_limit": 0}
        for row in recorded:
            if row["status"] not in counts:
                raise AssertionError(f"Unexpected archived status: {row['status']}")
            counts[row["status"]] += 1
            objective = float(row["best_feasible_objective_eur"])
            revenue = float(row["sales_revenue_eur"])
            retained = float(row["retained_inventory_value_eur"])
            if abs(objective - revenue - retained) > 0.02:
                raise AssertionError(f"Objective decomposition differs: {row['scenario']}")
            if int(row["full_exposure"]) + int(row["partial_only"]) + int(row["no_exposure"]) != 50:
                raise AssertionError(f"Exposure count differs: {row['scenario']}")
            print(f"PASS {row['scenario']}: EUR {objective:,.2f} ({row['status']})")
        if counts != {"optimal": 7, "feasible_time_limit": 4}:
            raise AssertionError(f"Unexpected status totals: {counts}")
        print("PASS: All 11 original 120-second sensitivity records checked; no files changed.")
        print("NOTE: Original CSV records 0.000% for optimal statuses even where its upper bound exceeds the incumbent.")
        print("The separately rerun rho=0.8 result is archived in its own CSV and supersedes that historical row.")
        return
    rows = load_previous_results()

    for group, name, change in make_scenarios():

        if args.only is not None and name != args.only:
            continue

        if name in rows and not args.retry:
            print(
                f"\nSKIP {name}: already recorded"
            )
            continue

        print(
            f"\nSTART: {name}",
            flush=True
        )

        row = {field: "" for field in FIELDS}

        row["group"] = group
        row["scenario"] = name

        try:
            scenario_data = deepcopy(data)
            change(scenario_data)

            model = build_model(scenario_data)

            result = solve_with_reporting(
                model, args.seconds
            )

            row["status"] = result["status"]
            row["elapsed_seconds"] = round(
                result["elapsed"], 3
            )
            row["note"] = result["condition"]

            if result["incumbent"] is not None:
                row["best_feasible_objective_eur"] = (
                    round(result["incumbent"], 4)
                )

            if result["upper_bound"] is not None:
                row["best_upper_bound_eur"] = (
                    round(result["upper_bound"], 4)
                )

            if result["gap"] is not None:
                row["gap_percent"] = round(
                    result["gap"], 4
                )

            if result["has_solution"]:

                row.update(
                    summarize_solution(model)
                )

                print(
                    f"STATUS: {result['status']}"
                )

                print(
                    f"Best feasible objective: "
                    f"EUR {result['incumbent']:,.2f}"
                )

                if result["upper_bound"] is not None:
                    print(
                        f"Upper bound: "
                        f"EUR {result['upper_bound']:,.2f}"
                    )

                if result["gap"] is not None:
                    print(
                        f"Optimality gap: "
                        f"{result['gap']:.3f}%"
                    )

                print(
                    f"Full exposure: "
                    f"{row['full_exposure']}"
                )

                print(
                    f"Units shipped: "
                    f"{row['units_shipped']}"
                )

            else:
                print(
                    "No feasible solution available "
                    "for this scenario."
                )

                print(
                    "Solver status:",
                    result["status"]
                )

        except Exception as exc:

            row["status"] = "error"
            row["note"] = (
                f"{type(exc).__name__}: {exc}"
            )[:300]

            print(
                f"ERROR: {row['note']}"
            )

        # Save after every scenario.
        rows[name] = row
        save_results(rows)

        print(
            "Progress saved.",
            flush=True
        )

    print("\n" + "=" * 65)
    print("SENSITIVITY ANALYSIS COMPLETED")
    print("=" * 65)

    optimal_count = sum(
        r["status"] == "optimal"
        for r in rows.values()
    )

    feasible_count = sum(
        r["status"] in {
            "optimal",
            "feasible_time_limit",
            "feasible_not_optimal"
        }
        for r in rows.values()
    )

    print(
        f"Proven optimal scenarios: {optimal_count}"
    )

    print(
        f"Scenarios with feasible solutions: "
        f"{feasible_count}"
    )

    print(
        f"Total scenarios recorded: {len(rows)}"
    )

    print(
        f"Results file: {OUTPUT.name}"
    )


if __name__ == "__main__":
    main()