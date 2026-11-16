"""Compare deterministic shipment policies under the SAME revised Zara MILP.
Recovered revised benchmark producer; run from repository root.
Default solver runs write NEW outputs under results/ without replacing archives.
Use --check-only to evaluate both deterministic policies without a solver or file writes.
"""
import argparse
import csv
from pathlib import Path
import pyomo.environ as pyo
from solve_zara_final import load_data, build_model, solve_model

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / 'results'
TOL = 1e-5


def request_based(d):
    """FCFS: stores in CSV order, then articles and sizes in CSV order."""
    left = dict(d['warehouse'])
    capacity_left = dict(d['capacity'])
    allocation = {}
    for i in d['stores']:
        for a in d['articles']:
            for s in d['sizes']:
                key = (i, a, s)
                unmet = max(0, d['demand'][key] - d['initial'][key])
                qty = min(unmet, left[a, s], capacity_left[i])
                allocation[key] = int(qty)
                left[a, s] -= qty
                capacity_left[i] -= qty
    return allocation

def demand_proportional(d):
    """Largest unmet-demand fulfillment deficit first, deterministic ties.

    At every step ship one unit to the store with the smallest
    fulfilled fraction of its initial unmet demand for that article/size.
    Compare within a single warehouse article-size pool, process pools
    in their declared CSV order. Store capacity is always respected.
    """
    stores, articles, sizes = d['stores'], d['articles'], d['sizes']
    allocation = {(i, a, s): 0 for i in stores for a in articles for s in sizes}
    capacity_left = dict(d['capacity'])
    unmet = {key: max(0, d['demand'][key] - d['initial'][key])
             for key in allocation}
    for a in articles:
        for s in sizes:
            remaining = int(d['warehouse'][a, s])
            while remaining:
                candidates = [i for i in stores
                              if capacity_left[i] > 0 and
                              allocation[i, a, s] < unmet[i, a, s]]
                if not candidates:
                    break
                # Minimize served fraction. Ties favor larger unmet demand,
                # then the original store order.
                chosen = min(candidates, key=lambda i: (
                    allocation[i, a, s] / unmet[i, a, s],
                    -unmet[i, a, s], stores.index(i)
                ))
                allocation[chosen, a, s] += 1
                capacity_left[chosen] -= 1
                remaining -= 1
    return allocation

def verify_allocation(d, allocation):
    for i in d['stores']:
        shipped = sum(allocation[i, a, s] for a in d['articles'] for s in d['sizes'])
        assert shipped <= d['capacity'][i], (i, shipped)
    for a in d['articles']:
        for s in d['sizes']:
            shipped = sum(allocation[i, a, s] for i in d['stores'])
            assert shipped <= d['warehouse'][a, s], (a, s, shipped)
    assert all(isinstance(x, int) and x >= 0 for x in allocation.values())


def evaluate_fixed(d, allocation, name):
    verify_allocation(d, allocation)
    model = build_model(d)
    for (i, a, s), amount in allocation.items():
        model.x[i, a, s].fix(amount)
    solve_model(model)
    val = pyo.value
    revenue = sum(val(model.P[a] * model.z[i, a, s])
                  for i in model.I for a in model.A for s in model.S)
    retention = sum(val(model.R[a, s] * model.r[a, s])
                    for a in model.A for s in model.S)
    total = val(model.obj)
    assert abs(total - revenue - retention) < 1e-4
    return {
        'policy': name,
        'objective_eur': total,
        'sales_revenue_eur': revenue,
        'retained_value_eur': retention,
        'units_shipped': sum(allocation.values()),
        'expected_sales_units': sum(val(model.z[i, a, s]) for i in model.I
                                    for a in model.A for s in model.S),
        'units_retained': sum(val(model.r[a, s]) for a in model.A for s in model.S),
        'full_exposure': sum(round(val(model.v[i, a])) for i in model.I for a in model.A),
        'partial_or_full_exposure': sum(round(val(model.u[i, a]))
                                        for i in model.I for a in model.A),
    }


def evaluate_optimal(d):
    model = build_model(d)
    solve_model(model)
    val = pyo.value
    revenue = sum(val(model.P[a] * model.z[i, a, s])
                  for i in model.I for a in model.A for s in model.S)
    retention = sum(val(model.R[a, s] * model.r[a, s])
                    for a in model.A for s in model.S)
    return {
        'policy': 'Revised MILP optimal',
        'objective_eur': val(model.obj),
        'sales_revenue_eur': revenue,
        'retained_value_eur': retention,
        'units_shipped': sum(round(val(model.x[i, a, s])) for i in model.I for a in model.A for s in model.S),
        'expected_sales_units': sum(val(model.z[i, a, s]) for i in model.I for a in model.A for s in model.S),
        'units_retained': sum(round(val(model.r[a, s])) for a in model.A for s in model.S),
        'full_exposure': sum(round(val(model.v[i, a])) for i in model.I for a in model.A),
        'partial_or_full_exposure': sum(round(val(model.u[i, a])) for i in model.I for a in model.A),
    }


def evaluate_without_solver(d, allocation):
    """Exact common-model fixed-allocation evaluation; no HiGHS required."""
    verify_allocation(d, allocation)
    revenue = 0.0
    sales = 0.0
    full = partial = none = 0
    rho = d['settings']['partial_exposure_factor']
    tp = d['settings']['partial_threshold']
    tf = d['settings']['full_threshold']
    for i in d['stores']:
        for a in d['articles']:
            q = {size: d['initial'][i, a, size] + allocation[i, a, size]
                 for size in d['sizes']}
            major_min = min(q[size] for size in d['major'])
            if major_min >= tf:
                e = 1.0
                full += 1
            elif major_min >= tp:
                e = rho
                partial += 1
            else:
                e = 0.0
                none += 1
            for size in d['sizes']:
                f = min(d['slope'][i, a, size, k] * q[size]
                        + d['intercept'][i, a, size, k]
                        for k in d['segments'])
                z = min(q[size], d['demand'][i, a, size], e * f)
                revenue += d['price'][a] * z
                sales += z
    kept = {(a, size): d['warehouse'][a, size]
            - sum(allocation[i, a, size] for i in d['stores'])
            for a in d['articles'] for size in d['sizes']}
    retained_value = sum(kept[a, size] * d['retention'][a, size]
                         for a in d['articles'] for size in d['sizes'])
    return dict(objective_eur=round(revenue + retained_value, 2),
                sales_revenue_eur=round(revenue, 2),
                retained_value_eur=round(retained_value, 2),
                units_shipped=sum(allocation.values()),
                units_retained=sum(kept.values()),
                full_exposure=full, partial_only=partial,
                no_exposure=none, expected_sales_units=round(sales, 2))


def check_policies(d):
    targets = [
        ('Request-based', request_based, 22615.67, 20602.82, 2012.85, 10),
        ('Demand-proportional', demand_proportional,
         38075.47, 35911.42, 2164.05, 28),
    ]
    for name, generate, expected_obj, expected_revenue, expected_retained, full in targets:
        allocation = generate(d)
        summary = evaluate_without_solver(d, allocation)
        for key, expected in [
            ('objective_eur', expected_obj),
            ('sales_revenue_eur', expected_revenue),
            ('retained_value_eur', expected_retained),
            ('full_exposure', full),
            ('units_shipped', 392),
            ('units_retained', 91),
        ]:
            if abs(summary[key] - expected) > 0.011:
                raise AssertionError(
                    f'{name} {key}: {summary[key]} != {expected}')
        print(f"PASS {name}: EUR {summary['objective_eur']:,.2f}; "
              f"full exposure {full}; shipped {summary['units_shipped']}")
    print("PASS: Both original revised benchmark policies independently "
          "evaluated. No files changed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true',
                        help='read-only independent verification; no solver run')
    args = parser.parse_args()
    d = load_data()
    if args.check_only:
        check_policies(d)
        return
    RESULTS.mkdir(parents=True, exist_ok=True)
    print('\nCOMPARING ALL POLICIES UNDER THE REVISED MILP\n')
    results = [evaluate_optimal(d)]
    for name, generate in [('Request-based', request_based),
                           ('Demand-proportional', demand_proportional)]:
        shipment = generate(d)
        results.append(evaluate_fixed(d, shipment, name))
        with (RESULTS / ('revised_' + name.lower().replace('-', '_') + '_shipments_rerun.csv')).open(
                'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['store', 'article', 'size', 'shipped_units'])
            for key, amount in shipment.items():
                writer.writerow([*key, amount])
    optimum = results[0]['objective_eur']
    for r in results:
        score = r['objective_eur']
        improvement = ((optimum / score - 1) * 100) if score > TOL else None
        print(f"{r['policy']}: EUR {score:,.2f} | "
              f"sales EUR {r['sales_revenue_eur']:,.2f} | "
              f"retained EUR {r['retained_value_eur']:,.2f} | "
              f"shipped {r['units_shipped']} | full exposure {r['full_exposure']}")
        if improvement is not None and r is not results[0]:
            print(f"  Improvement of MILP over this benchmark: {improvement:.2f}%")
    assert all(optimum + 1e-4 >= row['objective_eur'] for row in results)
    with (RESULTS / 'revised_benchmark_comparison_rerun.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print('\nPASS: All benchmarks feasible and no benchmark exceeds the MILP optimum.')
    print('Saved new rerun files in results/; original archived outputs untouched.')


if __name__ == '__main__':
    main()