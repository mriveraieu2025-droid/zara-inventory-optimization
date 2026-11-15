"""Softer-exposure robustness experiment for the Zara MILP.

Run from the repository root:
    py src/exposure_robustness.py --residual 0.20 --seconds 300

For store-article combinations without a complete major-size assortment,
allow a fraction of the piecewise saturation sales potential instead of zero.
Partial exposure (rho=0.6) and full exposure (1.0) remain unchanged.

Original input files, baseline allocation, and other results are untouched.
"""

import argparse
import csv
from pathlib import Path

import pyomo.environ as pyo
from solve_zara_final import load_data, build_model

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
ABLATION = RESULTS / "zara_ablation_shipments.csv"
OUTPUT = RESULTS / "zara_exposure_robustness.csv"
FIELDS = [
    "residual_exposure_factor", "partial_exposure_factor", "status",
    "optimized_soft_objective_eur", "optimized_soft_sales_revenue_eur",
    "optimized_soft_retained_value_eur", "optimized_full_exposure",
    "optimized_partial_only", "optimized_no_exposure",
    "optimized_shipped", "optimized_retained",
    "full_baseline_allocation_soft_eval_eur",
    "no_exposure_policy_soft_eval_eur",
    "improvement_vs_no_exposure_policy_pct", "note",
]


def ablation_shipments():
    if not ABLATION.exists():
        raise FileNotFoundError(f"Missing required saved allocation: {ABLATION}")
    shipments = {"full_rerun": {}, "no_exposure": {}}
    with ABLATION.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (row["store"], row["article"], row["size"])
            for label in shipments:
                shipments[label][key] = int(row[label])
    return shipments


def evaluate_fixed(data, shipping, residual):
    """Evaluate shipments under the same softened exposure rules."""
    expected = {(i, a, s) for i in data["stores"]
                for a in data["articles"] for s in data["sizes"]}
    if shipping.keys() != expected:
        raise ValueError("Fixed shipment file does not cover exactly 200 combinations")
    retained_value = 0.0
    retained_total = 0
    for a in data["articles"]:
        for s in data["sizes"]:
            kept = data["warehouse"][a, s] - sum(shipping[i, a, s] for i in data["stores"])
            if kept < 0:
                raise ValueError(f"Fixed shipments exceed warehouse stock for {a}, {s}")
            retained_total += kept
            retained_value += data["retention"][a, s] * kept
    for i in data["stores"]:
        if sum(shipping[i, a, s] for a in data["articles"]
               for s in data["sizes"]) > data["capacity"][i]:
            raise ValueError(f"Fixed allocation exceeds capacity at {i}")

    revenue = 0.0
    exposure_counts = {"full": 0, "partial": 0, "none": 0}
    full = data["settings"]["full_threshold"]
    partial = data["settings"]["partial_threshold"]
    rho = data["settings"]["partial_exposure_factor"]
    for i in data["stores"]:
        for a in data["articles"]:
            major_final = [data["initial"][i, a, s] + shipping[i, a, s]
                           for s in data["major"]]
            if all(q >= full for q in major_final):
                exposure = 1.0
                exposure_counts["full"] += 1
            elif all(q >= partial for q in major_final):
                exposure = rho
                exposure_counts["partial"] += 1
            else:
                exposure = residual
                exposure_counts["none"] += 1
            for s in data["sizes"]:
                q = data["initial"][i, a, s] + shipping[i, a, s]
                sat = min(data["slope"][i, a, s, k] * q
                          + data["intercept"][i, a, s, k]
                          for k in data["segments"])
                sale = min(q, data["demand"][i, a, s], exposure * sat)
                revenue += data["price"][a] * sale

    return {"objective": revenue + retained_value,
            "revenue": revenue, "retention": retained_value,
            "retained": retained_total, "exposure": exposure_counts}


def build_soft_model(data, residual):
    """Linearize z <= residual * f(q) for u=0; leave other states unchanged.

    The previously active z<=D*u family is deactivated. New inequalities:
       z <= residual * (alpha_k*q+beta_k) + D*u, all k.
    When u=1, D*u >= D makes these inequalities redundant because
    each affine saturation segment is nonnegative on the feasible domain.
    """
    model = build_model(data)
    model.no_exposure.deactivate()

    def residual_rule(m, i, a, s, k):
        line = m.alpha[i, a, s, k] * m.q[i, a, s] + m.beta[i, a, s, k]
        return m.z[i, a, s] <= residual * line + m.D[i, a, s] * m.u[i, a]

    model.residual_no_exposure = pyo.Constraint(
        model.I, model.A, model.S, model.K, rule=residual_rule
    )
    return model


def save_result(row):
    old = {}
    if OUTPUT.exists():
        with OUTPUT.open(newline="", encoding="utf-8-sig") as f:
            for previous in csv.DictReader(f):
                old[previous["residual_exposure_factor"]] = previous
    old[row["residual_exposure_factor"]] = row
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for key in sorted(old, key=float):
            writer.writerow(old[key])


def main():
    parser = argparse.ArgumentParser(description="Residual sales without exposure")
    parser.add_argument("--residual", type=float, default=0.20,
                        help="Fraction of saturation potential allowed without exposure")
    parser.add_argument("--seconds", type=int, default=300,
                        help="HiGHS time limit in seconds")
    args = parser.parse_args()
    data = load_data()
    rho = data["settings"]["partial_exposure_factor"]
    if not (0 <= args.residual < rho < 1):
        parser.error("Require 0 <= residual < partial_exposure_factor < 1")
    if args.seconds <= 0:
        parser.error("--seconds must be positive")

    shipping = ablation_shipments()
    reference = evaluate_fixed(data, shipping["full_rerun"], 0.0)
    original_no_exposure = evaluate_fixed(data, shipping["no_exposure"], 0.0)
    if abs(reference["objective"] - 45657.45) > 0.02:
        raise RuntimeError("Archived full-model allocation disagrees with original model")
    if abs(original_no_exposure["objective"] - 30920.85) > 0.02:
        raise RuntimeError("Archived no-exposure allocation disagrees with ablation report")

    full_soft = evaluate_fixed(data, shipping["full_rerun"], args.residual)
    noexp_soft = evaluate_fixed(data, shipping["no_exposure"], args.residual)
    print("\nEXPOSURE ROBUSTNESS CHECK")
    print(f"No-exposure residual = {args.residual:.2f}; partial = {rho:.2f}; full = 1")
    print("Baseline allocation under softened evaluation: EUR %.2f" % full_soft["objective"])
    print("No-exposure policy allocation under softened evaluation: EUR %.2f" % noexp_soft["objective"])
    print("Original inputs and saved baseline remain unchanged.")

    row = {key: "" for key in FIELDS}
    row.update(residual_exposure_factor=f"{args.residual:.2f}",
               partial_exposure_factor=f"{rho:.2f}",
               full_baseline_allocation_soft_eval_eur=round(full_soft["objective"], 2),
               no_exposure_policy_soft_eval_eur=round(noexp_soft["objective"], 2))

    model = build_soft_model(data, args.residual)
    solver = pyo.SolverFactory("appsi_highs")
    if not solver.available(exception_flag=False):
        solver = pyo.SolverFactory("highs")
    if not solver.available(exception_flag=False):
        raise RuntimeError("Install highspy to solve the model")
    solver.options["time_limit"] = float(args.seconds)
    try:
        result = solver.solve(model, load_solutions=False)
        condition = result.solver.termination_condition
        row["status"] = str(condition)
        row["note"] = f"HiGHS termination: {condition}; time limit {args.seconds}s"
        if condition == pyo.TerminationCondition.optimal:
            model.solutions.load_from(result)
            v = pyo.value
            revenue = sum(v(model.P[a] * model.z[i, a, s])
                          for i in model.I for a in model.A for s in model.S)
            kept_value = sum(v(model.R[a, s] * model.r[a, s])
                             for a in model.A for s in model.S)
            total = v(model.obj)
            assert abs(total - revenue - kept_value) < 1e-4
            if total + 1e-4 < full_soft["objective"]:
                raise ValueError("Optimized softened objective below known feasible baseline")
            row.update(
                optimized_soft_objective_eur=round(total, 2),
                optimized_soft_sales_revenue_eur=round(revenue, 2),
                optimized_soft_retained_value_eur=round(kept_value, 2),
                optimized_shipped=round(sum(v(model.x[i,a,s]) for i in model.I
                                            for a in model.A for s in model.S)),
                optimized_retained=round(sum(v(model.r[a,s]) for a in model.A for s in model.S)),
                optimized_full_exposure=round(sum(v(model.v[i,a]) for i in model.I for a in model.A)),
                optimized_partial_only=round(sum(v(model.u[i,a])-v(model.v[i,a])
                                                 for i in model.I for a in model.A)),
                optimized_no_exposure=round(sum(1-v(model.u[i,a]) for i in model.I for a in model.A))
            )
            loss = 100*(total-noexp_soft["objective"])/total
            row["improvement_vs_no_exposure_policy_pct"] = round(loss, 2)
            print("SOFTENED EXPOSURE MILP: EUR %.2f; status: %s" % (total, condition))
            print("NO-EXPOSURE POLICY (SOFT EVALUATION): EUR %.2f" % noexp_soft["objective"])
            print("POLICY LOSS RELATIVE TO SOFT MILP: %.2f%%" % loss)
            print("EXPOSURE COUNTS: full=%s, partial=%s, none=%s" %
                  (row["optimized_full_exposure"], row["optimized_partial_only"],
                   row["optimized_no_exposure"]))
        else:
            print("TIME LIMIT: optimality not established; no solver objective recorded")
    except Exception as exc:
        row["status"] = "error"
        row["note"] = f"{type(exc).__name__}: {exc}"[:250]
        print("Solver error:", row["note"])
    save_result(row)
    print("SAVED:", OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
