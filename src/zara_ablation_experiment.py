"""Zara MILP ablation study: isolate exposure and diminishing returns.

Run this archived experiment script from the repository root. It imports
src/solve_zara_final.py and uses the authoritative data/ CSV inputs.
It does not modify the original inputs or baseline allocation.

Three models are solved with the same data:
  full                 exposure + piecewise-linear saturation
  no_exposure          remove exposure and keep saturation
  linear_sales         keep exposure, use only the first sales segment

IMPORTANT: Native objective values from different models use different
sales assumptions and are NOT directly comparable as economic performance.
We therefore re-evaluate all resulting shipments under the ORIGINAL full
model's sales formula (same data, prices, exposure and saturation).

Run from the repository root:
    py src/zara_ablation_experiment.py --check-archive
    py src/zara_ablation_experiment.py --seconds 180

The quick check re-evaluates the original archived allocations without solving.
Full reruns write ONLY to:
    results/zara_ablation_comparison_rerun.csv
    results/zara_ablation_shipments_rerun.csv
The original archived result CSVs are never overwritten.

If results/revised_allocation.csv is present, the program also checks the
previously saved baseline as an additional reference policy.
"""

import argparse
import csv
from math import isfinite
from pathlib import Path

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers import Highs

from solve_zara_final import load_data, build_model

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
TOL = 1e-4
MODELS = ("full", "no_exposure", "linear_sales")


def build_variant(data, variant):
    """Change only the sales mechanism being examined."""
    model = build_model(data)

    if variant == "full":
        return model

    if variant == "no_exposure":
        # Keep warehouse balance, receiving capacity, inventory, and demand.
        # Drop all exposure eligibility and exposure-adjusted sales restrictions.
        for name in (
            "partial", "full", "hierarchy", "no_exposure",
            "partial_sales", "full_sales",
        ):
            getattr(model, name).deactivate()

        def saturation_only(m, i, a, s, k):
            line = m.alpha[i, a, s, k] * m.q[i, a, s] + m.beta[i, a, s, k]
            return m.z[i, a, s] <= line

        model.saturation_only = pyo.Constraint(
            model.I, model.A, model.S, model.K, rule=saturation_only
        )
        # Exposure variables have no role in this scenario.
        for i in model.I:
            for a in model.A:
                model.u[i, a].fix(0)
                model.v[i, a].fix(0)
        return model

    if variant == "linear_sales":
        # Preserve binary exposure decisions and eligibility constraints.
        # Replace the concave envelope by its initial affine segment.
        model.partial_sales.deactivate()
        model.full_sales.deactivate()
        first_segment = data["segments"][0]
        rho = data["settings"]["partial_exposure_factor"]

        def initial_line(m, i, a, s):
            return (
                m.alpha[i, a, s, first_segment] * m.q[i, a, s]
                + m.beta[i, a, s, first_segment]
            )

        model.linear_partial = pyo.Constraint(
            model.I, model.A, model.S,
            rule=lambda m, i, a, s: (
                m.z[i, a, s]
                <= rho * initial_line(m, i, a, s)
                + m.D[i, a, s] * (1 - m.u[i, a] + m.v[i, a])
            ),
        )
        model.linear_full = pyo.Constraint(
            model.I, model.A, model.S,
            rule=lambda m, i, a, s: (
                m.z[i, a, s]
                <= initial_line(m, i, a, s)
                + m.D[i, a, s] * (1 - m.v[i, a])
            ),
        )
        return model

    raise ValueError("Unknown variant: " + variant)


def solve_one(data, variant, seconds, gap):
    model = build_variant(data, variant)
    solver = Highs()
    if not solver.available():
        raise RuntimeError("HiGHS is unavailable. Install highspy in VS Code.")
    solver.config.time_limit = float(seconds)
    solver.config.load_solution = False
    solver.highs_options["mip_rel_gap"] = float(gap)

    print(f"\nSOLVING: {variant} (limit {seconds}s)", flush=True)
    result = solver.solve(model)
    termination = str(result.termination_condition).split(".")[-1]
    feasible_obj = result.best_feasible_objective
    bound = result.best_objective_bound

    if feasible_obj is None or not isfinite(float(feasible_obj)):
        print(f"  {termination}; no feasible solution to analyze", flush=True)
        return {
            "status": termination,
            "objective_bound": float(bound) if bound is not None else None,
            "relative_gap": None,
            "allocation": None,
            "native_objective": None,
        }

    # Explicitly load the incumbent, including when time limit was reached.
    solver.load_vars()
    allocation = {
        (i, a, s): int(round(pyo.value(model.x[i, a, s])))
        for i in data["stores"]
        for a in data["articles"]
        for s in data["sizes"]
    }
    native_obj = float(pyo.value(model.obj))
    best_bound = float(bound) if bound is not None and isfinite(float(bound)) else None
    rel_gap = (
        max(0.0, (best_bound - native_obj) / max(1.0, abs(native_obj)))
        if best_bound is not None else None
    )
    print(
        f"  termination={termination}, incumbent=EUR {native_obj:,.2f}, "
        f"relative gap={'unknown' if rel_gap is None else f'{100 * rel_gap:.3f}%'}",
        flush=True,
    )
    return {
        "status": termination,
        "objective_bound": best_bound,
        "relative_gap": rel_gap,
        "allocation": allocation,
        "native_objective": native_obj,
    }


def check_shipments(data, shipments):
    expected = {
        (i, a, s)
        for i in data["stores"]
        for a in data["articles"]
        for s in data["sizes"]
    }
    if set(shipments) != expected:
        raise ValueError("Shipment allocation does not have all 200 combinations")
    if any(q < 0 or int(q) != q for q in shipments.values()):
        raise ValueError("Invalid shipment quantity")
    for i in data["stores"]:
        used = sum(shipments[i, a, s] for a in data["articles"] for s in data["sizes"])
        if used > data["capacity"][i]:
            raise ValueError(f"Store capacity violated: {i}")
    for a in data["articles"]:
        for s in data["sizes"]:
            used = sum(shipments[i, a, s] for i in data["stores"])
            if used > data["warehouse"][a, s]:
                raise ValueError(f"Warehouse inventory violated: {(a, s)}")


def evaluate_policy(data, shipments, sales_mode="full"):
    """Exact best modeled sales for FIXED shipments; no second solve needed.

    With positive prices and no extra coupling between exposure decisions,
    the best available exposure level is activated for each store/article.
    """
    check_shipments(data, shipments)
    rho = data["settings"]["partial_exposure_factor"]
    tp = data["settings"]["partial_threshold"]
    tf = data["settings"]["full_threshold"]
    k_first = data["segments"][0]
    revenue = 0.0
    expected_sales = 0.0
    full_eligible = 0
    partial_eligible = 0

    for i in data["stores"]:
        for a in data["articles"]:
            major_quantities = [
                data["initial"][i, a, s] + shipments[i, a, s]
                for s in data["major"]
            ]
            if all(q >= tf for q in major_quantities):
                exposure = 1.0
                full_eligible += 1
            elif all(q >= tp for q in major_quantities):
                exposure = rho
                partial_eligible += 1
            else:
                exposure = 0.0

            if sales_mode == "no_exposure":
                exposure = 1.0

            for s in data["sizes"]:
                q = data["initial"][i, a, s] + shipments[i, a, s]
                kvalues = [
                    data["slope"][i, a, s, k] * q
                    + data["intercept"][i, a, s, k]
                    for k in data["segments"]
                ]
                saturation = (
                    kvalues[0] if sales_mode == "linear_sales"
                    else min(kvalues)
                )
                z = min(q, data["demand"][i, a, s], exposure * saturation)
                if z < -TOL:
                    raise ValueError("Negative expected sales from data")
                revenue += data["price"][a] * max(0.0, z)
                expected_sales += max(0.0, z)

    remaining = {
        (a, s): data["warehouse"][a, s]
        - sum(shipments[i, a, s] for i in data["stores"])
        for a in data["articles"] for s in data["sizes"]
    }
    retention_value = sum(
        data["retention"][a, s] * n for (a, s), n in remaining.items()
    )
    objective = revenue + retention_value
    return {
        "objective": objective,
        "sales_revenue": revenue,
        "retained_value": retention_value,
        "expected_sales_units": expected_sales,
        "units_shipped": sum(shipments.values()),
        "units_retained": sum(remaining.values()),
        "full_eligible": full_eligible,
        "partial_eligible": partial_eligible,
        "none_eligible": len(data["stores"]) * len(data["articles"])
        - full_eligible - partial_eligible,
    }


def load_saved_baseline(data):
    """Optional: previous saved feasible policy, checked against current data."""
    path = RESULTS / "revised_allocation.csv"
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8-sig") as f:
        records = list(csv.DictReader(f))
    shipments = {}
    for row in records:
        key = (row["store"], row["article"], row["size"])
        if key in shipments:
            raise ValueError("Duplicate row in saved baseline: " + str(key))
        if int(row["initial_inventory"]) != data["initial"][key]:
            raise ValueError("Saved baseline was generated using different initial stock")
        shipments[key] = int(row["shipped_units"])
    check_shipments(data, shipments)
    return shipments


def fmt(x, decimals=2):
    return "" if x is None else round(x, decimals)


def save_results(data, runs, saved):
    rows = []
    for name, entry in runs.items():
        if entry["allocation"] is None:
            rows.append({
                "policy": name, "status": entry["status"],
                "native_model_objective_eur": "",
                "native_model_upper_bound_eur": fmt(entry["objective_bound"]),
                "solver_relative_gap_pct": "",
                "full_model_objective_eur": "",
            })
            continue
        x = entry["allocation"]
        check = evaluate_policy(data, x, name)
        if abs(check["objective"] - entry["native_objective"]) > 0.1:
            raise ValueError(
                f"Native and direct objective disagree for {name}: "
                f"{check['objective']}, {entry['native_objective']}"
            )
        common = evaluate_policy(data, x, "full")
        rows.append({
            "policy": name,
            "status": entry["status"],
            "native_model_objective_eur": fmt(entry["native_objective"]),
            "native_model_upper_bound_eur": fmt(entry["objective_bound"]),
            "solver_relative_gap_pct": fmt(
                100 * entry["relative_gap"] if entry["relative_gap"] is not None else None,
                4,
            ),
            "full_model_objective_eur": fmt(common["objective"]),
            "full_model_sales_revenue_eur": fmt(common["sales_revenue"]),
            "full_model_retained_value_eur": fmt(common["retained_value"]),
            "full_model_expected_sales_units": fmt(common["expected_sales_units"]),
            "units_shipped": common["units_shipped"],
            "units_retained": common["units_retained"],
            "full_exposure_eligible": common["full_eligible"],
            "partial_exposure_eligible": common["partial_eligible"],
            "no_exposure_eligible": common["none_eligible"],
        })

    if saved is not None:
        common = evaluate_policy(data, saved, "full")
        rows.append({
            "policy": "saved_baseline_reference",
            "status": "saved_feasible_policy_not_new_proof",
            "native_model_objective_eur": fmt(common["objective"]),
            "full_model_objective_eur": fmt(common["objective"]),
            "full_model_sales_revenue_eur": fmt(common["sales_revenue"]),
            "full_model_retained_value_eur": fmt(common["retained_value"]),
            "full_model_expected_sales_units": fmt(common["expected_sales_units"]),
            "units_shipped": common["units_shipped"],
            "units_retained": common["units_retained"],
            "full_exposure_eligible": common["full_eligible"],
            "partial_exposure_eligible": common["partial_eligible"],
            "no_exposure_eligible": common["none_eligible"],
        })

    # Best FEASIBLE baseline, not necessarily proven optimal.
    baseline_choices = [
        (evaluate_policy(data, runs["full"]["allocation"], "full")["objective"],
         runs["full"]["allocation"], "full")
    ] if runs["full"]["allocation"] is not None else []
    if saved is not None:
        baseline_choices.append((
            evaluate_policy(data, saved, "full")["objective"],
            saved, "saved_baseline_reference"
        ))
    baseline_score, baseline, baseline_name = max(baseline_choices, key=lambda entry: entry[0])
    for row in rows:
        if row.get("full_model_objective_eur") not in (None, ""):
            score = float(row["full_model_objective_eur"])
            row["loss_vs_best_feasible_baseline_pct"] = fmt(
                100.0 * (baseline_score - score) / baseline_score, 4
            ) if baseline_score > 0 else ""
        else:
            row["loss_vs_best_feasible_baseline_pct"] = ""

    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / "zara_ablation_comparison_rerun.csv"
    fieldnames = [
        "policy", "status", "native_model_objective_eur",
        "native_model_upper_bound_eur", "solver_relative_gap_pct",
        "full_model_objective_eur", "full_model_sales_revenue_eur",
        "full_model_retained_value_eur", "full_model_expected_sales_units",
        "units_shipped", "units_retained", "full_exposure_eligible",
        "partial_exposure_eligible", "no_exposure_eligible",
        "loss_vs_best_feasible_baseline_pct",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    # Record the shipment decisions for every variant and the common baseline.
    allocations = {
        name: result["allocation"] for name, result in runs.items()
    }
    allocations["best_feasible_baseline"] = baseline
    path2 = RESULTS / "zara_ablation_shipments_rerun.csv"
    with path2.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "store", "article", "size", "best_feasible_baseline",
            "full_rerun", "no_exposure", "linear_sales"
        ])
        for i in data["stores"]:
            for a in data["articles"]:
                for s in data["sizes"]:
                    key = (i, a, s)
                    writer.writerow([
                        i, a, s, baseline[key],
                        allocations["full"][key] if allocations["full"] is not None else "",
                        allocations["no_exposure"][key] if allocations["no_exposure"] is not None else "",
                        allocations["linear_sales"][key] if allocations["linear_sales"] is not None else "",
                    ])

    print("\n========== ABLATION RESULTS (COMMON ORIGINAL MODEL) ==========")
    print(f"Best feasible baseline: EUR {baseline_score:,.2f} ({baseline_name})")
    for row in rows:
        value = row.get("full_model_objective_eur", "")
        if value == "":
            print(f"  {row['policy']}: no feasible solution recorded ({row['status']})")
            continue
        print(
            f"  {row['policy']:28s} EUR {float(value):>11,.2f} "
            f"| full eligible={row['full_exposure_eligible']:>2} "
            f"| shipped={row['units_shipped']:>3}"
        )
    print("\nOutputs: results/zara_ablation_comparison_rerun.csv and results/zara_ablation_shipments_rerun.csv")
    print("A time limit does not establish optimality. Interpret loss values accordingly.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=180,
                        help="maximum time for each model solve (default 180)")
    parser.add_argument("--gap", type=float, default=0.0001,
                        help="relative MIP gap tolerance (default 0.0001)")
    parser.add_argument("--check-archive", action="store_true",
                        help="verify original archived ablation shipments without a solver run")
    args = parser.parse_args()
    if args.seconds <= 0 or not 0 < args.gap < 1:
        parser.error("--seconds must be positive; --gap must be between 0 and 1")

    data = load_data()
    if args.check_archive:
        archive = RESULTS / "zara_ablation_shipments.csv"
        if not archive.exists():
            raise FileNotFoundError(f"Missing archived shipment decisions: {archive}")
        policies = {name: {} for name in ("full_rerun", "no_exposure", "linear_sales")}
        with archive.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                key = (row["store"], row["article"], row["size"])
                for name in policies:
                    policies[name][key] = int(row[name])
        expected = {"full_rerun": 45657.45,
                    "no_exposure": 30920.85,
                    "linear_sales": 42975.55}
        for name, shipments in policies.items():
            value = evaluate_policy(data, shipments, "full")["objective"]
            if abs(value - expected[name]) > 0.02:
                raise AssertionError(f"Archive mismatch for {name}: {value:.2f} vs {expected[name]:.2f}")
            print(f"PASS archived {name}: EUR {value:,.2f}")
        print("PASS: Original ablation results independently re-evaluated; no files changed.")
        return
    saved = load_saved_baseline(data)
    print("Saved baseline found." if saved is not None else "No saved baseline found.")
    runs = {}
    for variant in MODELS:
        runs[variant] = solve_one(data, variant, args.seconds, args.gap)

    if runs["full"]["allocation"] is None and saved is None:
        raise RuntimeError("No feasible baseline allocation. Increase --seconds.")
    save_results(data, runs, saved)


if __name__ == "__main__":
    main()