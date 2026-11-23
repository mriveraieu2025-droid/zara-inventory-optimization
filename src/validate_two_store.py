"""Reproduce the two-store analytical validation from Section 8 of the report.

Run from the repository root:
    py src/validate_two_store.py

Uses the exact MILP builder and solver from src/solve_zara_final.py,
with an independent, self-contained two-store dataset.
"""

import math

import pyomo.environ as pyo

from solve_zara_final import build_model, solve_model


EXPECTED_OPTIMUM_EUR = 57.60
TOL = 1e-5


def make_validation_data():
    """Data from the report's two-store, one-article worked example."""
    stores = ["Madrid", "Barcelona"]
    articles = ["Dress"]
    sizes = ["XS", "S", "M", "L"]
    major = ["S", "M", "L"]
    segments = [1, 2, 3]

    # Inventory is indexed by (store, article, size).
    initial_major = {
        ("Madrid", "S"): 2,
        ("Madrid", "M"): 0,
        ("Madrid", "L"): 2,
        ("Barcelona", "S"): 0,
        ("Barcelona", "M"): 2,
        ("Barcelona", "L"): 0,
    }
    initial = {
        (i, "Dress", s): initial_major.get((i, s), 0)
        for i in stores for s in sizes
    }

    # Six warehouse units: two units of each major size; no XS.
    warehouse = {
        ("Dress", s): 0 if s == "XS" else 2
        for s in sizes
    }
    demand = {
        (i, "Dress", s): 4
        for i in stores for s in sizes
    }

    # f(q) = min{0.8q, 0.4q+1.2, 3.2} for each store and size.
    lines = {
        1: (0.8, 0.0),
        2: (0.4, 1.2),
        3: (0.0, 3.2),
    }
    slope = {
        (i, "Dress", s, k): lines[k][0]
        for i in stores for s in sizes for k in segments
    }
    intercept = {
        (i, "Dress", s, k): lines[k][1]
        for i in stores for s in sizes for k in segments
    }

    return {
        "stores": stores,
        "articles": articles,
        "sizes": sizes,
        "major": major,
        "segments": segments,
        "capacity": {i: 6 for i in stores},
        "price": {"Dress": 10.0},
        "warehouse": warehouse,
        "retention": {("Dress", s): 3.50 for s in sizes},
        "initial": initial,
        "demand": demand,
        "slope": slope,
        "intercept": intercept,
        "settings": {
            "partial_threshold": 1,
            "full_threshold": 3,
            "partial_exposure_factor": 0.6,
        },
    }


def main():
    data = make_validation_data()
    model = build_model(data)  # Same MILP formulation as the full project.
    solve_model(model)         # HiGHS, with optimal solver termination required.

    val = pyo.value
    objective = val(model.obj)
    revenue = sum(
        val(model.P[a] * model.z[i, a, s])
        for i in model.I for a in model.A for s in model.S
    )
    retained_value = sum(
        val(model.R[a, s] * model.r[a, s])
        for a in model.A for s in model.S
    )
    total_sales = sum(
        val(model.z[i, a, s])
        for i in model.I for a in model.A for s in model.S
    )
    shipped = sum(
        val(model.x[i, a, s])
        for i in model.I for a in model.A for s in model.S
    )
    retained = sum(val(model.r[a, s]) for a in model.A for s in model.S)

    # The reported €57.60 upper bound is valid for *every* feasible
    # allocation; a feasible allocation attaining it is globally optimal.
    # Total stock across both stores and warehouse = 12 major-size units.
    analytic_upper_bound = 57.60 - 1.30 * retained

    assert math.isclose(objective, EXPECTED_OPTIMUM_EUR, abs_tol=TOL)
    assert objective <= analytic_upper_bound + TOL
    assert math.isclose(objective, revenue + retained_value, abs_tol=TOL)
    assert math.isclose(total_sales, 5.76, abs_tol=TOL)
    assert math.isclose(shipped, 6.0, abs_tol=TOL)
    assert math.isclose(retained, 0.0, abs_tol=TOL)

    for i in model.I:
        # Size-specific stock prevents full exposure at either store.
        assert val(model.v[i, "Dress"]) < TOL
        assert val(model.u[i, "Dress"]) > 1.0 - TOL
        assert sum(val(model.x[i, "Dress", s]) for s in model.S) <= 6 + TOL

    for s in model.S:
        assert math.isclose(
            sum(val(model.x[i, "Dress", s]) for i in model.I)
            + val(model.r["Dress", s]),
            data["warehouse"]["Dress", s],
            abs_tol=TOL,
        )

    print("\nTWO-STORE VALIDATION: PASS")
    print(f"Objective (EUR):       {objective:.2f}")
    print(f"Expected sales (units): {total_sales:.2f}")
    print(f"Warehouse units sent:   {shipped:.0f}")
    print(f"Warehouse units kept:   {retained:.0f}")
    print(f"Independent upper bound: {analytic_upper_bound:.2f} EUR")
    print("The solver reaches the analytically proven global optimum of EUR 57.60.")


if __name__ == "__main__":
    main()
