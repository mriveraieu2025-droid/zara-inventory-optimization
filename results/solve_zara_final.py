
import csv
from pathlib import Path

import pyomo.environ as pyo


# ============================================================
# ZARA FINAL PROJECT
# REVISED MILP: EXPOSURE + SATURATION
# ============================================================

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data"
RESULTS = ROOT / "results"
TOL = 1e-5


# ============================================================
# 1. LOAD DATA
# ============================================================

def read_csv(filename):
    with (BASE / filename).open(
        "r", newline="", encoding="utf-8-sig"
    ) as f:
        return list(csv.DictReader(f))


def load_data():
    store_rows = read_csv("stores.csv")
    article_rows = read_csv("articles.csv")
    warehouse_rows = read_csv("warehouse.csv")
    demand_rows = read_csv("store_article_size.csv")
    segment_rows = read_csv("saturation_segments.csv")
    setting_rows = read_csv("model_settings.csv")

    stores = [r["store"] for r in store_rows]
    articles = [r["article"] for r in article_rows]
    sizes = ["XS", "S", "M", "L"]
    major = ["S", "M", "L"]
    segments = [1, 2, 3, 4]

    capacity = {
        r["store"]: int(r["shipment_capacity_units"])
        for r in store_rows
    }

    price = {
        r["article"]: float(r["selling_price_eur"])
        for r in article_rows
    }

    warehouse = {
        (r["article"], r["size"]):
        int(r["warehouse_stock_units"])
        for r in warehouse_rows
    }

    retention = {
        (r["article"], r["size"]):
        float(r["retention_value_eur_per_unit"])
        for r in warehouse_rows
    }

    initial = {
        (r["store"], r["article"], r["size"]):
        int(r["initial_store_inventory_units"])
        for r in demand_rows
    }

    demand = {
        (r["store"], r["article"], r["size"]):
        int(r["forecast_demand_units"])
        for r in demand_rows
    }

    slope = {
        (
            r["store"], r["article"], r["size"],
            int(r["segment"])
        ): float(r["slope"])
        for r in segment_rows
    }

    intercept = {
        (
            r["store"], r["article"], r["size"],
            int(r["segment"])
        ): float(r["intercept"])
        for r in segment_rows
    }

    settings = {
        r["parameter"]: float(r["value"])
        for r in setting_rows
    }

    expected = {
        (i, a, s)
        for i in stores
        for a in articles
        for s in sizes
    }

    assert set(initial) == expected
    assert set(demand) == expected

    assert set(warehouse) == {
        (a, s)
        for a in articles
        for s in sizes
    }

    expected_segments = {
        (i, a, s, k)
        for i, a, s in expected
        for k in segments
    }

    assert set(slope) == expected_segments
    assert set(intercept) == expected_segments

    assert all(v >= 0 for v in warehouse.values())
    assert all(v >= 0 for v in initial.values())
    assert all(v >= 0 for v in demand.values())
    assert all(v >= 0 for v in capacity.values())
    assert all(v >= 0 for v in retention.values())
    assert all(v >= 0 for v in price.values())

    assert (
        0 < settings["partial_threshold"]
        < settings["full_threshold"]
    )

    assert (
        0 < settings["partial_exposure_factor"] < 1
    )

    # Check saturation slopes and big-M assumptions
    for i, a, s in expected:
        slopes = [
            slope[i, a, s, k]
            for k in segments
        ]

        assert all(v >= 0 for v in slopes)

        assert all(
            slopes[j] >= slopes[j + 1]
            for j in range(len(slopes) - 1)
        )

        assert abs(intercept[i, a, s, 1]) < TOL

        q_max = initial[i, a, s] + warehouse[a, s]

        for k in segments:
            alpha = slope[i, a, s, k]
            beta = intercept[i, a, s, k]

            # An affine function reaches its minimum
            # at an endpoint of the inventory interval.
            if min(beta, alpha * q_max + beta) < -TOL:
                raise ValueError(
                    f"Invalid big-M bound for "
                    f"{(i, a, s, k)}"
                )

    print("PASS: All six CSV files loaded.")
    print("PASS: Saturation and big-M checks.")

    return {
        "stores": stores,
        "articles": articles,
        "sizes": sizes,
        "major": major,
        "segments": segments,
        "capacity": capacity,
        "price": price,
        "warehouse": warehouse,
        "retention": retention,
        "initial": initial,
        "demand": demand,
        "slope": slope,
        "intercept": intercept,
        "settings": settings,
    }


# ============================================================
# 2. BUILD REVISED MILP
# ============================================================

def build_model(d):
    m = pyo.ConcreteModel(name="Zara Revised MILP")

    m.I = pyo.Set(initialize=d["stores"])
    m.A = pyo.Set(initialize=d["articles"])
    m.S = pyo.Set(initialize=d["sizes"])
    m.M = pyo.Set(within=m.S, initialize=d["major"])
    m.K = pyo.Set(initialize=d["segments"])

    m.H = pyo.Param(
        m.A, m.S, initialize=d["warehouse"]
    )

    m.B = pyo.Param(
        m.I, m.A, m.S, initialize=d["initial"]
    )

    m.D = pyo.Param(
        m.I, m.A, m.S, initialize=d["demand"]
    )

    m.P = pyo.Param(
        m.A, initialize=d["price"]
    )

    m.R = pyo.Param(
        m.A, m.S, initialize=d["retention"]
    )

    m.C = pyo.Param(
        m.I, initialize=d["capacity"]
    )

    m.alpha = pyo.Param(
        m.I, m.A, m.S, m.K,
        initialize=d["slope"]
    )

    m.beta = pyo.Param(
        m.I, m.A, m.S, m.K,
        initialize=d["intercept"]
    )

    tp = d["settings"]["partial_threshold"]
    tf = d["settings"]["full_threshold"]
    rho = d["settings"]["partial_exposure_factor"]

    # Decision variables
    m.x = pyo.Var(
        m.I, m.A, m.S,
        domain=pyo.NonNegativeIntegers
    )

    m.z = pyo.Var(
        m.I, m.A, m.S,
        domain=pyo.NonNegativeReals
    )

    m.r = pyo.Var(
        m.A, m.S,
        domain=pyo.NonNegativeIntegers
    )

    m.u = pyo.Var(
        m.I, m.A,
        domain=pyo.Binary
    )

    m.v = pyo.Var(
        m.I, m.A,
        domain=pyo.Binary
    )

    # Available inventory
    m.q = pyo.Expression(
        m.I, m.A, m.S,
        rule=lambda m, i, a, s:
            m.B[i, a, s] + m.x[i, a, s]
    )

    # Objective: expected revenue + retained value
    m.obj = pyo.Objective(
        expr=(
            sum(
                m.P[a] * m.z[i, a, s]
                for i in m.I
                for a in m.A
                for s in m.S
            )
            +
            sum(
                m.R[a, s] * m.r[a, s]
                for a in m.A
                for s in m.S
            )
        ),
        sense=pyo.maximize
    )

    # 1. Warehouse inventory balance
    m.balance = pyo.Constraint(
        m.A, m.S,
        rule=lambda m, a, s:
            sum(m.x[i, a, s] for i in m.I)
            + m.r[a, s] == m.H[a, s]
    )

    # 2. Physical inventory limit
    m.inventory_limit = pyo.Constraint(
        m.I, m.A, m.S,
        rule=lambda m, i, a, s:
            m.z[i, a, s] <= m.q[i, a, s]
    )

    # 3. Demand limit
    m.demand_limit = pyo.Constraint(
        m.I, m.A, m.S,
        rule=lambda m, i, a, s:
            m.z[i, a, s] <= m.D[i, a, s]
    )

    # 4. Partial exposure eligibility
    m.partial = pyo.Constraint(
        m.I, m.A, m.M,
        rule=lambda m, i, a, s:
            m.q[i, a, s] >= tp * m.u[i, a]
    )

    # 5. Full exposure eligibility
    m.full = pyo.Constraint(
        m.I, m.A, m.M,
        rule=lambda m, i, a, s:
            m.q[i, a, s] >= tf * m.v[i, a]
    )

    # 6. Exposure hierarchy
    m.hierarchy = pyo.Constraint(
        m.I, m.A,
        rule=lambda m, i, a:
            m.v[i, a] <= m.u[i, a]
    )

    # 7. No-exposure sales restriction
    m.no_exposure = pyo.Constraint(
        m.I, m.A, m.S,
        rule=lambda m, i, a, s:
            m.z[i, a, s]
            <= m.D[i, a, s] * m.u[i, a]
    )

    # 8. Partial exposure saturation
    def partial_sales_rule(m, i, a, s, k):
        line = (
            m.alpha[i, a, s, k] * m.q[i, a, s]
            + m.beta[i, a, s, k]
        )

        return (
            m.z[i, a, s]
            <= rho * line
            + m.D[i, a, s] * (
                1 - m.u[i, a] + m.v[i, a]
            )
        )

    m.partial_sales = pyo.Constraint(
        m.I, m.A, m.S, m.K,
        rule=partial_sales_rule
    )

    # 9. Full exposure saturation
    def full_sales_rule(m, i, a, s, k):
        line = (
            m.alpha[i, a, s, k] * m.q[i, a, s]
            + m.beta[i, a, s, k]
        )

        return (
            m.z[i, a, s]
            <= line
            + m.D[i, a, s] * (1 - m.v[i, a])
        )

    m.full_sales = pyo.Constraint(
        m.I, m.A, m.S, m.K,
        rule=full_sales_rule
    )

    # 10. Store shipment capacity
    m.capacity = pyo.Constraint(
        m.I,
        rule=lambda m, i:
            sum(
                m.x[i, a, s]
                for a in m.A
                for s in m.S
            ) <= m.C[i]
    )

    return m


# ============================================================
# 3. SOLVE MODEL
# ============================================================

def solve_model(m):
    solver = pyo.SolverFactory("appsi_highs")

    if not solver.available(exception_flag=False):
        solver = pyo.SolverFactory("highs")

    if not solver.available(exception_flag=False):
        raise RuntimeError(
            "HiGHS is unavailable. Install highspy."
        )

    results = solver.solve(m)

    condition = results.solver.termination_condition

    if condition != pyo.TerminationCondition.optimal:
        raise RuntimeError(
            f"Solver did not report optimality: {condition}"
        )

    print("Solver termination:", condition)


# ============================================================
# 4. VALIDATE AND SUMMARIZE SOLUTION
# ============================================================

def summarize(m, d):
    val = pyo.value

    revenue = sum(
        val(m.P[a] * m.z[i, a, s])
        for i in m.I
        for a in m.A
        for s in m.S
    )

    retained_value = sum(
        val(m.R[a, s] * m.r[a, s])
        for a in m.A
        for s in m.S
    )

    shipped = sum(
        val(m.x[i, a, s])
        for i in m.I
        for a in m.A
        for s in m.S
    )

    retained = sum(
        val(m.r[a, s])
        for a in m.A
        for s in m.S
    )

    sales = sum(
        val(m.z[i, a, s])
        for i in m.I
        for a in m.A
        for s in m.S
    )

    partial_or_full = sum(
        val(m.u[i, a])
        for i in m.I
        for a in m.A
    )

    full_count = sum(
        val(m.v[i, a])
        for i in m.I
        for a in m.A
    )

    rho = d["settings"]["partial_exposure_factor"]
    tp = d["settings"]["partial_threshold"]
    tf = d["settings"]["full_threshold"]

    # Check warehouse balance
    for a in m.A:
        for s in m.S:
            lhs = sum(
                val(m.x[i, a, s])
                for i in m.I
            ) + val(m.r[a, s])

            assert abs(lhs - val(m.H[a, s])) < TOL

    # Check store capacities
    for i in m.I:
        total = sum(
            val(m.x[i, a, s])
            for a in m.A
            for s in m.S
        )

        assert total <= val(m.C[i]) + TOL

    # Verify revised sales ceilings and exposure
    for i in m.I:
        for a in m.A:
            u = val(m.u[i, a])
            v = val(m.v[i, a])

            assert v <= u + TOL

            exposure = rho * u + (1 - rho) * v

            for s in m.M:
                q = val(m.q[i, a, s])
                assert q + TOL >= tp * u
                assert q + TOL >= tf * v

            for s in m.S:
                q = val(m.q[i, a, s])
                z = val(m.z[i, a, s])
                demand = val(m.D[i, a, s])

                saturation = min(
                    val(m.alpha[i, a, s, k]) * q
                    + val(m.beta[i, a, s, k])
                    for k in m.K
                )

                ceiling = min(
                    q, demand, exposure * saturation
                )

                assert z >= -TOL
                assert z <= ceiling + TOL

    assert abs(
        val(m.obj) - revenue - retained_value
    ) < TOL

    print("\n" + "=" * 50)
    print("ZARA REVISED MILP - OPTIMAL RESULTS")
    print("=" * 50)

    print(f"Optimal objective: EUR {val(m.obj):,.2f}")
    print(f"Predicted sales revenue: EUR {revenue:,.2f}")
    print(f"Retained inventory value: EUR {retained_value:,.2f}")
    print(f"Units shipped: {shipped:,.0f}")
    print(f"Predicted sales units: {sales:,.2f}")
    print(f"Warehouse units retained: {retained:,.0f}")
    print(f"Partial-or-full exposure: {partial_or_full:.0f}")
    print(f"Full exposure: {full_count:.0f}")

    print("\nALL SOLUTION CHECKS PASSED!")


# ============================================================
# 5. EXPORT RESULTS
# ============================================================

def export_results(m):
    val = pyo.value

    RESULTS.mkdir(parents=True, exist_ok=True)

    with (RESULTS / "revised_allocation.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f)

        writer.writerow([
            "store", "article", "size",
            "initial_inventory",
            "shipped_units",
            "available_inventory",
            "expected_sales",
            "partial_exposure",
            "full_exposure"
        ])

        for i in m.I:
            for a in m.A:
                for s in m.S:
                    writer.writerow([
                        i, a, s,
                        round(val(m.B[i, a, s])),
                        round(val(m.x[i, a, s])),
                        round(val(m.q[i, a, s])),
                        round(val(m.z[i, a, s]), 6),
                        round(val(m.u[i, a])),
                        round(val(m.v[i, a]))
                    ])

    with (RESULTS / "revised_remaining_stock.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f)

        writer.writerow([
            "article", "size", "retained_units"
        ])

        for a in m.A:
            for s in m.S:
                writer.writerow([
                    a, s, round(val(m.r[a, s]))
                ])

    print("\nSaved revised_allocation.csv")
    print("Saved revised_remaining_stock.csv")


# ============================================================
# 6. MAIN
# ============================================================

def main():
    print("Loading Zara data...")
    data = load_data()

    print("\nBuilding revised Zara MILP...")
    model = build_model(data)

    print("\nSolving the ten-store optimization...")
    solve_model(model)

    summarize(model, data)
    export_results(model)


if __name__ == "__main__":
    main()
