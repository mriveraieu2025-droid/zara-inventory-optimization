"""Reproduce the no-shipment baseline and incremental benchmark comparison.

Usage: place this file in the root OR src/ directory of the Zara GitHub repo,
then run: python zara_no_shipment_incremental.py
(or: python src/zara_no_shipment_incremental.py)

Reads the original synthetic CSVs and saved benchmark summaries.
Does not modify the model or original results. Writes a NEW CSV under results/.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE if (HERE / 'data').is_dir() else HERE.parent
DATA = ROOT / 'data'
RESULTS = ROOT / 'results'
D = Decimal
SIZES = ('XS', 'S', 'M', 'L')
MAJOR = ('S', 'M', 'L')


def records(path: Path):
    with path.open(newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def main():
    prices = {r['article']: D(r['selling_price_eur']) for r in records(DATA / 'articles.csv')}
    stocks = records(DATA / 'warehouse.csv')
    cells = records(DATA / 'store_article_size.csv')
    seg_rows = records(DATA / 'saturation_segments.csv')
    settings = {r['parameter']: D(r['value']) for r in records(DATA / 'model_settings.csv')}

    initial = {(r['store'],r['article'],r['size']): D(r['initial_store_inventory_units']) for r in cells}
    segments = defaultdict(list)
    for r in seg_rows:
        segments[(r['store'], r['article'], r['size'])].append((D(r['slope']), D(r['intercept'])))

    assert len(cells) == len(initial) == 200
    assert len(seg_rows) == 800
    assert sum(int(r['warehouse_stock_units']) for r in stocks) == 483

    rho = settings['partial_exposure_factor']
    partial_threshold = settings['partial_threshold']
    full_threshold = settings['full_threshold']

    pairs = sorted({(r['store'], r['article']) for r in cells})
    exposure = {}
    exposure_counts = {'none':0,'partial':0,'full':0}
    for i, a in pairs:
        major = [initial[(i,a,s)] for s in MAJOR]
        if all(q >= full_threshold for q in major):
            e, label = D(1), 'full'
        elif all(q >= partial_threshold for q in major):
            e, label = rho, 'partial'
        else:
            e, label = D(0), 'none'
        exposure[(i,a)] = e
        exposure_counts[label] += 1

    initial_sales_revenue = D(0)
    expected_sales = D(0)
    for r in cells:
        i, a, s = r['store'], r['article'], r['size']
        q = initial[(i,a,s)]  # no shipments: x_ias = 0
        forecast = D(r['forecast_demand_units'])
        f = min(slope*q + intercept for slope, intercept in segments[(i,a,s)])
        e = exposure[(i,a)]  # applies to all sizes, including XS
        z = min(q, forecast, e*f)
        assert z >= 0
        expected_sales += z
        initial_sales_revenue += prices[a]*z

    warehouse_retained_value = sum(
        D(r['warehouse_stock_units'])*D(r['retention_value_eur_per_unit'])
        for r in stocks
    )
    no_ship_total = initial_sales_revenue + warehouse_retained_value

    official_rows = records(RESULTS / 'revised_benchmark_comparison_rerun.csv')
    by_name = {}
    for r in official_rows:
        n = r['policy'].lower()
        name = ('MILP' if 'milp' in n else
                'Request-based' if 'request' in n else
                'Demand-proportional' if 'proportional' in n else None)
        if name:
            by_name[name] = D(r['objective_eur'])
    greedy = records(RESULTS / 'zara_exposure_aware_greedy_summary.csv')
    assert len(greedy) == 1
    by_name['Exposure-aware greedy'] = D(greedy[0]['objective_eur'])
    assert set(by_name) == {'MILP','Exposure-aware greedy','Demand-proportional','Request-based'}

    order = ['MILP','Exposure-aware greedy','Demand-proportional','Request-based']
    increments = {name: by_name[name]-no_ship_total for name in order}
    print('NO-SHIPMENT BASELINE')
    print('Expected sales from initial inventory (units):', expected_sales)
    print('Sales revenue from initial inventory (EUR): ', initial_sales_revenue)
    print('Value of warehouse stock retained (EUR): ', warehouse_retained_value)
    print('Total no-shipment objective (EUR):      ', no_ship_total)
    print('Exposure states:', exposure_counts)
    print('\nINCREMENTAL BENCHMARK VALUES')
    out = []
    for name in order:
        row = {
            'policy': name,
            'objective_eur': f'{by_name[name]:.2f}',
            'no_shipment_baseline_eur': f'{no_ship_total:.2f}',
            'incremental_value_eur': f'{increments[name]:.2f}',
        }
        out.append(row)
        print(f'{name:24} objective={row["objective_eur"]:>10} incremental={row["incremental_value_eur"]:>10}')
    for name in order[1:]:
        assert increments[name] > 0
        gain = 100*(increments['MILP']-increments[name])/increments[name]
        print(f'MILP improvement vs {name}: {gain:.2f}%')

    RESULTS.mkdir(parents=True, exist_ok=True)
    output = RESULTS / 'no_shipment_incremental_comparison.csv'
    with output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)
    print('\nWrote', output)

if __name__ == '__main__':
    main()
