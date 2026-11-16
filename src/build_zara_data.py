
import csv
import random
from pathlib import Path

# ================================================
# ZARA FINAL PROJECT - DATA GENERATION
# ================================================

# Write regenerated CSV files to a separate directory instead of the
# authoritative data/ folder, which must not be overwritten.
ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "generated_data"
BASE.mkdir(parents=True, exist_ok=True)
rng = random.Random(20261031)

STORES = {
    "Madrid": 42,
    "Barcelona": 35,
    "Paris": 48,
    "Milan": 40,
    "London": 53,
    "Lisbon": 29,
    "Berlin": 43,
    "Rome": 37,
    "Amsterdam": 34,
    "Brussels": 31,
}

ARTICLES = {
    "Dress": {"price": 79, "base_demand": 14},
    "Jeans": {"price": 59, "base_demand": 13},
    "Jacket": {"price": 119, "base_demand": 10},
    "Shirt": {"price": 45, "base_demand": 12},
    "Trousers": {"price": 69, "base_demand": 11},
}

SIZES = ["XS", "S", "M", "L"]
MAJOR = ["S", "M", "L"]

SIZE_FACTORS = {
    "XS": 0.55,
    "S": 1.00,
    "M": 1.20,
    "L": 0.80,
}

# Synthetic store demand factors
STORE_FACTORS = {
    "Madrid": 1.20,
    "Barcelona": 1.05,
    "Paris": 1.30,
    "Milan": 1.15,
    "London": 1.25,
    "Lisbon": 0.75,
    "Berlin": 1.10,
    "Rome": 1.00,
    "Amsterdam": 0.90,
    "Brussels": 0.80,
}

# Hypothetical article preferences
PREFERENCES = {
    ("Madrid", "Dress"): 1.30,
    ("Paris", "Dress"): 1.25,
    ("Milan", "Dress"): 1.25,
    ("London", "Jacket"): 1.40,
    ("Berlin", "Jeans"): 1.35,
    ("Amsterdam", "Jeans"): 1.20,
    ("Rome", "Trousers"): 1.25,
    ("Barcelona", "Shirt"): 1.20,
}

# Exposure assumptions
PARTIAL_THRESHOLD = 1
FULL_THRESHOLD = 3
PARTIAL_FACTOR = 0.60

# Retained inventory value is 35% of price
RETENTION_FACTOR = 0.35


# ================================================
# HELPER: WRITE CSV
# ================================================

def save_csv(filename, rows, columns):
    with (BASE / filename).open(
        "w", newline="", encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file, fieldnames=columns
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Created: {filename}")


# ================================================
# 1. STORES
# ================================================

store_rows = [
    {
        "store": city,
        "shipment_capacity_units": capacity
    }
    for city, capacity in STORES.items()
]

save_csv(
    "stores.csv",
    store_rows,
    ["store", "shipment_capacity_units"]
)


# ================================================
# 2. ARTICLES
# ================================================

article_rows = []

for article, values in ARTICLES.items():
    article_rows.append({
        "article": article,
        "selling_price_eur": values["price"]
    })

save_csv(
    "articles.csv",
    article_rows,
    ["article", "selling_price_eur"]
)


# ================================================
# 3. WAREHOUSE INVENTORY
# ================================================

warehouse_rows = []

for article, values in ARTICLES.items():

    for size in SIZES:

        # Different stock levels by size and article
        stock = round(
            28 * SIZE_FACTORS[size]
            + rng.randint(-5, 6)
        )

        stock = max(5, stock)

        retention = round(
            values["price"] * RETENTION_FACTOR,
            2
        )

        warehouse_rows.append({
            "article": article,
            "size": size,
            "warehouse_stock_units": stock,
            "retention_value_eur_per_unit": retention
        })

save_csv(
    "warehouse.csv",
    warehouse_rows,
    [
        "article",
        "size",
        "warehouse_stock_units",
        "retention_value_eur_per_unit"
    ]
)


# ================================================
# 4. STORE DEMAND AND INITIAL INVENTORY
# ================================================

combination_rows = []
demand_lookup = {}

for city in STORES:

    for article, values in ARTICLES.items():

        preference = PREFERENCES.get(
            (city, article), 1.0
        )

        for size in SIZES:

            raw_demand = (
                values["base_demand"]
                * STORE_FACTORS[city]
                * preference
                * SIZE_FACTORS[size]
            )

            demand = max(
                2,
                round(raw_demand + rng.randint(-2, 2))
            )

            # Many store-size combinations start
            # with limited or zero inventory.
            initial_stock = rng.choices(
                [0, 1, 2, 3, 4, 5],
                weights=[35, 20, 17, 13, 9, 6]
            )[0]

            demand_lookup[
                (city, article, size)
            ] = demand

            combination_rows.append({
                "store": city,
                "article": article,
                "size": size,
                "forecast_demand_units": demand,
                "initial_store_inventory_units":
                    initial_stock
            })

save_csv(
    "store_article_size.csv",
    combination_rows,
    [
        "store",
        "article",
        "size",
        "forecast_demand_units",
        "initial_store_inventory_units"
    ]
)


# ================================================
# 5. SATURATION FUNCTION PARAMETERS
# ================================================

# Four marginal-sales segments:
# slope 0.85, then 0.50, then 0.20,
# and finally 0 (saturation).

SLOPES = [0.85, 0.50, 0.20, 0.00]

segment_rows = []

for (city, article, size), demand in demand_lookup.items():

    # Breakpoints based on local forecast demand.
    b1 = max(1, round(0.45 * demand))
    b2 = max(b1 + 1, round(0.90 * demand))
    b3 = max(b2 + 1, round(1.40 * demand))

    # Intercepts maintain continuity.
    intercepts = [
        0.0,
        (SLOPES[0] - SLOPES[1]) * b1,
        (SLOPES[0] - SLOPES[1]) * b1
        + (SLOPES[1] - SLOPES[2]) * b2,
        (SLOPES[0] - SLOPES[1]) * b1
        + (SLOPES[1] - SLOPES[2]) * b2
        + (SLOPES[2] - SLOPES[3]) * b3,
    ]

    for k in range(4):
        segment_rows.append({
            "store": city,
            "article": article,
            "size": size,
            "segment": k + 1,
            "slope": SLOPES[k],
            "intercept": round(intercepts[k], 6)
        })

save_csv(
    "saturation_segments.csv",
    segment_rows,
    [
        "store",
        "article",
        "size",
        "segment",
        "slope",
        "intercept"
    ]
)


# ================================================
# 6. EXPOSURE PARAMETERS
# ================================================

settings_rows = [
    {
        "parameter": "partial_threshold",
        "value": PARTIAL_THRESHOLD
    },
    {
        "parameter": "full_threshold",
        "value": FULL_THRESHOLD
    },
    {
        "parameter": "partial_exposure_factor",
        "value": PARTIAL_FACTOR
    },
]

save_csv(
    "model_settings.csv",
    settings_rows,
    ["parameter", "value"]
)


# ================================================
# 7. VALIDATE GENERATED DATA
# ================================================

assert len(store_rows) == 10
assert len(article_rows) == 5
assert len(warehouse_rows) == 20
assert len(combination_rows) == 200
assert len(segment_rows) == 800

assert all(
    row["forecast_demand_units"] >= 0
    for row in combination_rows
)

assert all(
    row["warehouse_stock_units"] >= 0
    for row in warehouse_rows
)

assert all(
    row["initial_store_inventory_units"] >= 0
    for row in combination_rows
)

assert (
    0 <= PARTIAL_FACTOR <= 1
    and 0 < PARTIAL_THRESHOLD < FULL_THRESHOLD
)

# ================================================
# 8. DATASET SUMMARY
# ================================================

total_demand = sum(
    row["forecast_demand_units"]
    for row in combination_rows
)

total_initial = sum(
    row["initial_store_inventory_units"]
    for row in combination_rows
)

total_warehouse = sum(
    row["warehouse_stock_units"]
    for row in warehouse_rows
)

total_capacity = sum(STORES.values())

print("\n================================")
print("ZARA DATASET GENERATION COMPLETE")
print("================================")

print("Stores:", len(STORES))
print("Articles:", len(ARTICLES))
print("Sizes:", len(SIZES))
print("Store-article-size records:", len(combination_rows))

print("Forecast demand:", total_demand)
print("Initial store inventory:", total_initial)
print("Warehouse inventory:", total_warehouse)
print("Receiving capacity:", total_capacity)

print("Saturation segment records:", len(segment_rows))
print("Random seed: 20261031")

print("\nALL DATA CHECKS PASSED!")