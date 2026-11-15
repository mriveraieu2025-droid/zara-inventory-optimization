"""Resumable sensitivity analysis for the revised Zara MILP.

Place alongside solve_zara_final.py and the six input CSV files.
Does not modify original inputs or previous optimization outputs.
"""
import argparse
import csv
from copy import deepcopy
from math import floor
from pathlib import Path

import pyomo.environ as pyo
from solve_zara_final import load_data, build_model

BASE = Path(__file__).resolve().parent.parent
OUTPUT = BASE / "results" / "zara_sensitivity_results.csv"
FIELDS = [
    "group", "scenario", "setting", "status", "objective_eur",
    "sales_revenue_eur", "retained_value_eur", "expected_sales_units",
    "units_shipped", "units_retained", "full_exposure",
    "partial_only_exposure", "no_exposure", "change_vs_baseline_pct",
    "note",
]


def scaled_integer(number, factor):
    return int(floor(number * factor + 0.5))


def scenarios():
    # (group, scenario name, setting, mutation function)
    return [
        ("Base case", "Baseline", "original CSVs", lambda d: None),
        ("Partial factor", "rho=0.4", "0.4", lambda d: d["settings"].update(partial_exposure_factor=0.4)),
        ("Partial factor", "rho=0.8", "0.8", lambda d: d["settings"].update(partial_exposure_factor=0.8)),
        ("Full threshold", "threshold=2", "2", lambda d: d["settings"].update(full_threshold=2.0)),
        ("Full threshold", "threshold=4", "4", lambda d: d["settings"].update(full_threshold=4.0)),
        ("Warehouse stock", "stock=0.8x", "0.8", lambda d: d.update(warehouse={k: scaled_integer(v, 0.8) for k, v in d["warehouse"].items()})),
        ("Warehouse stock", "stock=1.2x", "1.2", lambda d: d.update(warehouse={k: scaled_integer(v, 1.2) for k, v in d["warehouse"].items()})),
        ("Store capacity", "capacity=0.8x", "0.8", lambda d: d.update(capacity={k: scaled_integer(v, 0.8) for k, v in d["capacity"].items()})),
        ("Store capacity", "capacity=1.2x", "1.2", lambda d: d.update(capacity={k: scaled_integer(v, 1.2) for k, v in d["capacity"].items()})),
        ("Retention value", "rate=0.20", "0.20", lambda d: d.update(retention={(a, s): 0.20 * d["price"][a] for a in d["articles"] for s in d["sizes"]})),
        ("Retention value", "rate=0.50", "0.50", lambda d: d.update(retention={(a, s): 0.50 * d["price"][a] for a in d["articles"] for s in d["sizes"]})),
    ]


def load_previous():
    if not OUTPUT.exists():
        return {}
    with OUTPUT.open(newline="", encoding="utf-8-sig") as f:
        return {row["scenario"]: row for row in csv.DictReader(f)}


def save_progress(rows):
    # Rewrite the checkpoint after EVERY scenario, including errors/timeouts.
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows.values())


def solve_with_limit(model, seconds):
    solver = pyo.SolverFactory("appsi_highs")
    if not solver.available(exception_flag=False):
        solver = pyo.SolverFactory("highs")
    if not solver.available(exception_flag=False):
        raise RuntimeError("HiGHS is unavailable. Install highspy.")
    solver.options["time_limit"] = float(seconds)
    # Do NOT load an unproven or missing solution into the model.
    result = solver.solve(model, load_solutions=False)
    condition = result.solver.termination_condition
    if condition == pyo.TerminationCondition.optimal:
        model.solutions.load_from(result)
        return "optimal", str(condition)
    if condition == pyo.TerminationCondition.maxTimeLimit:
        return "time_limit", str(condition)
    return "not_optimal", str(condition)


def summarize(model):
    v = pyo.value
    revenue = sum(v(model.P[a] * model.z[i, a, s]) for i in model.I for a in model.A for s in model.S)
    retained_value = sum(v(model.R[a, s] * model.r[a, s]) for a in model.A for s in model.S)
    shipped = sum(round(v(model.x[i, a, s])) for i in model.I for a in model.A for s in model.S)
    kept = sum(round(v(model.r[a, s])) for a in model.A for s in model.S)
    sales = sum(v(model.z[i, a, s]) for i in model.I for a in model.A for s in model.S)
    full = sum(round(v(model.v[i, a])) for i in model.I for a in model.A)
    partial = sum(round(v(model.u[i, a])) - round(v(model.v[i, a])) for i in model.I for a in model.A)
    objective = v(model.obj)
    assert abs(objective - revenue - retained_value) <= 1e-4
    return dict(objective_eur=round(objective, 4), sales_revenue_eur=round(revenue, 4),
                retained_value_eur=round(retained_value, 4), expected_sales_units=round(sales, 4),
                units_shipped=shipped, units_retained=kept, full_exposure=full,
                partial_only_exposure=partial, no_exposure=len(model.I) * len(model.A) - full - partial)


def main():
    parser = argparse.ArgumentParser(description="Resumable Zara MILP sensitivity")
    parser.add_argument("--seconds", type=int, default=60, help="Time limit for each scenario (default 60)")
    parser.add_argument("--retry-timeouts", action="store_true", help="Retry previously timed-out scenarios")
    parser.add_argument("--only", help="Run one named scenario, e.g. threshold=4")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be positive")

    data = load_data()
    rows = load_previous()
    print(f"\nSENSITIVITY ANALYSIS: {args.seconds}s limit per scenario")
    print(f"Checkpoint: {OUTPUT.name}", flush=True)

    for group, name, setting, mutate in scenarios():
        if args.only and name != args.only:
            continue
        previous = rows.get(name)
        if previous and previous.get("status") == "optimal":
            print(f"SKIP {name}: previously solved optimally", flush=True)
            continue
        if previous and previous.get("status") == "time_limit" and not args.retry_timeouts:
            print(f"SKIP {name}: previously timed out (use --retry-timeouts)", flush=True)
            continue

        print(f"\nSTART {group}: {name}", flush=True)
        row = {key: "" for key in FIELDS}
        row.update(group=group, scenario=name, setting=setting)
        try:
            d = deepcopy(data)
            mutate(d)
            model = build_model(d)
            status, note = solve_with_limit(model, args.seconds)
            row.update(status=status, note=note)
            if status == "optimal":
                row.update(summarize(model))
                print(f"DONE {name}: EUR {row['objective_eur']:,.2f}; full={row['full_exposure']}", flush=True)
            else:
                print(f"SKIPPED RESULT {name}: {status}; no optimality claim", flush=True)
        except Exception as exc:
            row.update(status="error", note=f"{type(exc).__name__}: {exc}"[:300])
            print(f"ERROR {name}: {row['note']}", flush=True)
        rows[name] = row

        baseline = rows.get("Baseline")
        if baseline and baseline.get("status") == "optimal":
            base_obj = float(baseline["objective_eur"])
            for saved in rows.values():
                if saved.get("status") == "optimal" and base_obj > 0:
                    saved["change_vs_baseline_pct"] = round(
                        100 * (float(saved["objective_eur"]) / base_obj - 1), 4
                    )
        save_progress(rows)
        print(f"SAVED {OUTPUT.name}", flush=True)

    optimal = sum(row["status"] == "optimal" for row in rows.values())
    print(f"\nFINISHED. {optimal} scenarios proven optimal; {len(rows)} recorded.")
    print("Other scenarios may have timed out or returned errors; check the status column.")
    print("When retention/warehouse capacity changes, objective values have different assumptions.")


if __name__ == "__main__":
    main()
