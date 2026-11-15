"""Demand-scarcity stress test for the Zara inventory allocation MILP.

Run from the repository root:
    py src/demand_stress_test.py --factor 0.40 --seconds 180

Uses unchanged baseline input CSVs in data/. Multiplies *forecast demand only*
using round-half-up to keep unit counts integral. Writes a separate results CSV.
Does not overwrite the baseline allocation, original data, or prior sensitivity
experiments. Never reports a time-limited solution as proven optimal.
"""
import argparse
import csv
from copy import deepcopy
from math import floor
from pathlib import Path

import pyomo.environ as pyo
from solve_zara_final import load_data, build_model
from zara_sensitivity_safe import solve_with_limit, summarize

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "zara_demand_stress_test.csv"
BASELINE = ROOT / "results" / "revised_allocation.csv"
COLUMNS = [
    "demand_factor", "status", "objective_eur", "sales_revenue_eur",
    "retained_value_eur", "expected_sales_units", "units_shipped",
    "units_retained", "full_exposure", "partial_only_exposure", "no_exposure",
    "positive_demand_binding_count", "zero_demand_count",
    "changed_shipment_variables", "note",
]


def round_half_up(x):
    return int(floor(x + 0.5))


def reference_shipments():
    if not BASELINE.exists():
        return {}
    with BASELINE.open(newline="", encoding="utf-8-sig") as handle:
        return {
            (r["store"], r["article"], r["size"]): int(
                round(float(r["shipped_units"]))
            )
            for r in csv.DictReader(handle)
        }


def save_row(row):
    existing = {}
    if OUT.exists():
        with OUT.open(newline="", encoding="utf-8-sig") as handle:
            for old in csv.DictReader(handle):
                existing[old["demand_factor"]] = old
    existing[row["demand_factor"]] = row
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for key in sorted(existing, key=float):
            writer.writerow(existing[key])


def main():
    parser = argparse.ArgumentParser(description="Zara forecast-demand stress test")
    parser.add_argument(
        "--factor", type=float, default=0.40,
        help="Multiply all baseline demand forecasts by this positive factor (default 0.40)",
    )
    parser.add_argument(
        "--seconds", type=int, default=180,
        help="HiGHS time limit in seconds (default 180)",
    )
    args = parser.parse_args()
    if not (args.factor > 0 and args.seconds > 0):
        parser.error("--factor and --seconds must be positive")

    original = load_data()
    data = deepcopy(original)
    data["demand"] = {
        key: round_half_up(value * args.factor)
        for key, value in original["demand"].items()
    }

    print(f"DEMAND STRESS TEST: {args.factor:.2f}x original forecasts")
    print("Only forecast demand changes; stock, capacities and prices are unchanged.")
    print(f"Solver time limit: {args.seconds} seconds")
    print(f"Positive forecasts: {sum(v > 0 for v in data['demand'].values())}/200")

    model = build_model(data)
    row = {column: "" for column in COLUMNS}
    row["demand_factor"] = f"{args.factor:.2f}"
    row["zero_demand_count"] = sum(v == 0 for v in data["demand"].values())

    try:
        status, note = solve_with_limit(model, args.seconds)
        row["status"] = status
        row["note"] = note
        if status == "optimal":
            row.update(summarize(model))
            v = pyo.value
            row["positive_demand_binding_count"] = sum(
                1 for i in model.I for a in model.A for s in model.S
                if v(model.D[i, a, s]) > 0
                and abs(v(model.z[i, a, s]) - v(model.D[i, a, s])) < 1e-5
            )
            reference = reference_shipments()
            if reference:
                row["changed_shipment_variables"] = sum(
                    1 for i in model.I for a in model.A for s in model.S
                    if abs(v(model.x[i, a, s]) - reference[i, a, s]) > 1e-5
                )
            print(f"OBJECTIVE: EUR {row['objective_eur']:,.2f}")
            print(f"MODELED SALES REVENUE: EUR {row['sales_revenue_eur']:,.2f}")
            print(f"UNITS SHIPPED: {row['units_shipped']}")
            print(f"UNITS RETAINED: {row['units_retained']}")
            print(f"FULL EXPOSURE: {row['full_exposure']}/50")
            print(f"POSITIVE DEMAND CEILINGS BINDING: {row['positive_demand_binding_count']}/200")
            print(f"CHANGED SHIPMENT DECISIONS: {row['changed_shipment_variables']}")
        else:
            print(f"Solver status: {status}; no optimality claim.")
            print("This run did not save a numerical solution. Try a longer limit.")
    except Exception as exc:
        row["status"] = "error"
        row["note"] = (type(exc).__name__ + ": " + str(exc))[:300]
        print("ERROR:", row["note"])
    save_row(row)
    print(f"SAVED: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
