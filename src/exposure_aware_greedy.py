"""A deterministic, exposure-aware greedy benchmark for the Zara MILP.

Run from the repository root:
    py src/exposure_aware_greedy.py

The policy uses ONLY the synthetic inputs and a greedy rule; it never uses the
optimized MILP shipments in making its allocation. It combines:
  * atomic bundles to unlock partial/full size exposure, and
  * single-unit additions to store/article/size combinations.

Each iteration selects the feasible action with the greatest *positive*
incremental model-value gain per shipped unit. This is a heuristic, NOT a MILP.
All policies are evaluated using the same original exposure and saturation
function and warehouse-retention values. Existing output files are untouched.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "results"
SIZES = ["XS", "S", "M", "L"]
MAJOR = ["S", "M", "L"]


def read(name):
    with (DATA / name).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load():
    stores = read("stores.csv")
    articles = read("articles.csv")
    warehouse = read("warehouse.csv")
    demand = read("store_article_size.csv")
    lines = read("saturation_segments.csv")
    settings = {r["parameter"]: float(r["value"]) for r in read("model_settings.csv")}
    d = {
        "stores": [r["store"] for r in stores],
        "articles": [r["article"] for r in articles],
        "capacity": {r["store"]: int(r["shipment_capacity_units"]) for r in stores},
        "price": {r["article"]: float(r["selling_price_eur"]) for r in articles},
        "stock": {(r["article"], r["size"]): int(r["warehouse_stock_units"]) for r in warehouse},
        "retention": {(r["article"], r["size"]): float(r["retention_value_eur_per_unit"]) for r in warehouse},
        "initial": {(r["store"], r["article"], r["size"]): int(r["initial_store_inventory_units"]) for r in demand},
        "demand": {(r["store"], r["article"], r["size"]): int(r["forecast_demand_units"]) for r in demand},
        "lines": {},
        "settings": settings,
    }
    for r in lines:
        key = (r["store"], r["article"], r["size"])
        d["lines"].setdefault(key, []).append((float(r["slope"]), float(r["intercept"])))
    expected = {(i, a, s) for i in d["stores"] for a in d["articles"] for s in SIZES}
    assert len(expected) == 200
    assert set(d["initial"]) == set(d["demand"]) == set(d["lines"]) == expected
    assert all(len(d["lines"][k]) == 4 for k in expected)
    assert settings["partial_threshold"] == 1 and settings["full_threshold"] == 3
    assert abs(settings["partial_exposure_factor"] - .6) < 1e-9
    return d


def exposure(d, x, i, a):
    q_major = [d["initial"][i, a, s] + x[i, a, s] for s in MAJOR]
    if all(q >= d["settings"]["full_threshold"] for q in q_major):
        return 1.0, "full"
    if all(q >= d["settings"]["partial_threshold"] for q in q_major):
        return d["settings"]["partial_exposure_factor"], "partial"
    return 0.0, "none"


def store_article_revenue(d, x, i, a):
    e, _ = exposure(d, x, i, a)
    subtotal = 0.
    for s in SIZES:
        key = (i, a, s)
        q = d["initial"][key] + x[key]
        f = min(alpha * q + beta for alpha, beta in d["lines"][key])
        z = max(0., min(q, d["demand"][key], e * f))
        subtotal += d["price"][a] * z
    return subtotal


def score_action(d, x, left, space, i, a, additions):
    """Positive net gain and gain/unit, or None when infeasible."""
    qty = sum(additions.values())
    if qty <= 0 or qty > space[i]:
        return None
    for s, n in additions.items():
        if n < 0 or n > left[a, s]:
            return None
    before = store_article_revenue(d, x, i, a)
    for s, n in additions.items():
        x[i, a, s] += n
    after = store_article_revenue(d, x, i, a)
    for s, n in additions.items():
        x[i, a, s] -= n
    retained_opportunity = sum(d["retention"][a, s] * n for s, n in additions.items())
    net = after - before - retained_opportunity
    if net <= 1e-8:
        return None
    return net / qty, net


def greedy(d):
    x = {(i, a, s): 0 for i in d["stores"] for a in d["articles"] for s in SIZES}
    left = d["stock"].copy()
    space = d["capacity"].copy()
    actions = []
    # Deterministic iteration: choose max gain per unit, then total net gain;
    # on any numerical tie, keep the first store/article/size in input order.
    while True:
        best = None
        best_rank = (-1.0, -1.0)
        for i in d["stores"]:
            if not space[i]:
                continue
            for a in d["articles"]:
                _, current = exposure(d, x, i, a)
                for target, threshold in (("full", int(d["settings"]["full_threshold"])),
                                          ("partial", int(d["settings"]["partial_threshold"]))):
                    if current == "full" or (current == "partial" and target == "partial"):
                        continue
                    bundle = {s: max(0, threshold - d["initial"][i, a, s] - x[i, a, s])
                              for s in MAJOR}
                    bundle = {s: n for s, n in bundle.items() if n > 0}
                    sc = score_action(d, x, left, space, i, a, bundle)
                    if sc and sc > best_rank:
                        best_rank = sc
                        best = (i, a, bundle, target)
                for s in SIZES:
                    single = {s: 1}
                    sc = score_action(d, x, left, space, i, a, single)
                    if sc and sc > best_rank:
                        best_rank = sc
                        best = (i, a, single, "single")
        if best is None:
            break
        i, a, additions, kind = best
        for s, n in additions.items():
            x[i, a, s] += n
            left[a, s] -= n
            space[i] -= n
        actions.append((i, a, kind, sum(additions.values()), round(best_rank[1], 4)))
        assert all(n >= 0 for n in left.values())
        assert all(n >= 0 for n in space.values())
    return x, actions


def evaluate(d, x):
    expected = {(i, a, s) for i in d["stores"] for a in d["articles"] for s in SIZES}
    assert set(x) == expected
    assert all(isinstance(n, int) and n >= 0 for n in x.values())
    assert all(sum(x[i, a, s] for a in d["articles"] for s in SIZES) <= d["capacity"][i]
               for i in d["stores"])
    retained = {(a, s): d["stock"][a, s] - sum(x[i, a, s] for i in d["stores"])
                for a in d["articles"] for s in SIZES}
    assert all(n >= 0 for n in retained.values())
    r_value = sum(d["retention"][a, s] * n for (a, s), n in retained.items())
    revenue = sum(store_article_revenue(d, x, i, a)
                  for i in d["stores"] for a in d["articles"])
    sales = 0.
    counts = {"full": 0, "partial": 0, "none": 0}
    for i in d["stores"]:
        for a in d["articles"]:
            e, kind = exposure(d, x, i, a)
            counts[kind] += 1
            for s in SIZES:
                key = (i, a, s)
                q = d["initial"][key] + x[key]
                f = min(alpha * q + beta for alpha, beta in d["lines"][key])
                sales += max(0., min(q, d["demand"][key], e * f))
    return {"objective_eur": round(revenue+r_value, 2),
            "sales_revenue_eur": round(revenue, 2),
            "retained_value_eur": round(r_value, 2),
            "expected_sales_units": round(sales, 2),
            "units_shipped": sum(x.values()),
            "units_retained": sum(retained.values()),
            "full_exposure": counts["full"],
            "partial_exposure": counts["partial"],
            "no_exposure": counts["none"]}


def saved_milp_allocation():
    path = OUT / "revised_allocation.csv"
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {(r["store"], r["article"], r["size"]): int(round(float(r["shipped_units"])))
                for r in csv.DictReader(handle)}


def main():
    d = load()
    reference = evaluate(d, saved_milp_allocation())
    if abs(reference["objective_eur"] - 45657.45) > 0.01:
        raise RuntimeError("Saved MILP baseline must reproduce EUR 45,657.45 before comparison")
    x, actions = greedy(d)
    result = evaluate(d, x)
    if result["objective_eur"] > reference["objective_eur"] + 0.02:
        raise RuntimeError("Heuristic allocation cannot exceed the MILP optimum under the same model")
    result["policy"] = "Exposure-aware greedy"
    result["gap_vs_milp_pct"] = round(100.0*(reference["objective_eur"] - result["objective_eur"]) / reference["objective_eur"], 2)
    result["milp_improvement_vs_greedy_pct"] = round(100.0*(reference["objective_eur"] / result["objective_eur"] - 1), 2)
    result["changed_shipments_vs_milp"] = sum(x[key] != n for key, n in saved_milp_allocation().items())
    OUT.mkdir(parents=True, exist_ok=True)
    shipments_path = OUT / "zara_exposure_aware_greedy_shipments.csv"
    with shipments_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["store", "article", "size", "shipped_units"])
        for (i,a,s), n in x.items():
            writer.writerow([i,a,s,n])
    results_path = OUT / "zara_exposure_aware_greedy_summary.csv"
    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result))
        writer.writeheader()
        writer.writerow(result)
    print("PASS: Greedy shipments respect every warehouse and store-capacity limit.")
    print("PASS: Baseline MILP fixed-allocation evaluation reproduces EUR 45,657.45.")
    print("EXPOSURE-AWARE GREEDY BENCHMARK")
    for label in ("objective_eur", "sales_revenue_eur", "retained_value_eur", "expected_sales_units", "units_shipped", "units_retained", "full_exposure", "partial_exposure", "no_exposure", "gap_vs_milp_pct", "milp_improvement_vs_greedy_pct", "changed_shipments_vs_milp"):
        print("  %s: %s" % (label, result[label]))
    print("Greedy action count:", len(actions))
    print("SAVED:", results_path.relative_to(ROOT), "and", shipments_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
