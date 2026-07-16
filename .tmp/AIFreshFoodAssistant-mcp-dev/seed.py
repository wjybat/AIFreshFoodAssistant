from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "fresh_food_dev.sqlite3"
REFERENCE_PRODUCTS_PATH = BASE_DIR / "data" / "seed-products.json"
DEFAULT_SCENARIO_DATA_DIR = BASE_DIR.parent.parent / "data"
SEED = 20260715
SALES_LOOKBACK_DAYS = 42
PRODUCTS_PER_STORE = 50
INVENTORY_STOCK_SCALE = 0.5


STORES = [
    ("STORE_001", "物美超市·学清路店", "示例城市", "Asia/Shanghai", "2026-07-09"),
    ("STORE_002", "物美超市·中关村店", "示例城市", "Asia/Shanghai", "2026-07-12"),
    ("STORE_003", "物美超市·新街口店", "示例城市", "Asia/Shanghai", "2026-07-15"),
    ("STORE_004", "物美超市·陶然亭店", "示例城市", "Asia/Shanghai", "2026-12-22"),
]


# These rows preserve the product IDs, names, dates, stock, units, prices, and costs
# in the main project's four bundled scenario files without importing from that project.
CORE_PRODUCTS = [
    ("STORE_001", "P001", "青椒", "蔬菜", 50.0, "kg", 1, "临期", "normal", 8.5, 5.0),
    ("STORE_001", "P002", "猪肉(丝)", "肉类", 80.0, "kg", 3, "正常", "high", 28.0, 20.0),
    ("STORE_001", "P003", "豆腐", "豆制品", 30.0, "kg", 2, "临期", "normal", 5.0, 3.0),
    ("STORE_001", "P004", "熟食米饭", "熟食", 120.0, "份", 1, "正常", "high", 6.0, 3.5),
    ("STORE_001", "P005", "鸡蛋", "蛋类", 200.0, "盒", 10, "正常", "normal", 12.0, 8.0),
    ("STORE_001", "P006", "紫菜", "干货", 60.0, "包", 180, "正常", "normal", 4.5, 2.5),
    ("STORE_001", "P007", "蒜", "调料", 100.0, "kg", 30, "正常", "normal", 10.0, 6.0),
    ("STORE_001", "P008", "酱油", "调料", 80.0, "瓶", 365, "正常", "normal", 8.0, 5.0),
    ("STORE_002", "P101", "黄瓜", "蔬菜", 60.0, "kg", 1, "临期", "normal", 6.0, 3.5),
    ("STORE_002", "P102", "冬瓜", "蔬菜", 45.0, "kg", 5, "正常", "high", 4.0, 2.0),
    ("STORE_002", "P103", "排骨", "肉类", 35.0, "kg", 2, "临期", "normal", 32.0, 24.0),
    ("STORE_002", "P104", "木耳(干)", "干货", 80.0, "包", 365, "正常", "normal", 8.0, 5.0),
    ("STORE_002", "P105", "绿豆", "干货", 100.0, "袋", 180, "正常", "normal", 5.0, 3.0),
    ("STORE_002", "P106", "凉皮", "熟食", 90.0, "份", 1, "正常", "high", 8.0, 4.0),
    ("STORE_002", "P107", "蒜", "调料", 50.0, "kg", 30, "正常", "normal", 10.0, 6.0),
    ("STORE_002", "P108", "陈醋", "调料", 60.0, "瓶", 365, "正常", "normal", 6.0, 3.5),
    ("STORE_003", "P201", "五花肉", "肉类", 40.0, "kg", 3, "正常", "high", 26.0, 18.0),
    ("STORE_003", "P202", "番茄", "蔬菜", 55.0, "kg", 2, "临期", "normal", 7.0, 4.0),
    ("STORE_003", "P203", "鸡蛋", "蛋类", 180.0, "盒", 10, "正常", "normal", 12.0, 8.0),
    ("STORE_003", "P204", "紫菜", "干货", 50.0, "包", 180, "正常", "normal", 4.5, 2.5),
    ("STORE_003", "P205", "大米", "主食", 300.0, "袋", 365, "正常", "high", 25.0, 18.0),
    ("STORE_003", "P206", "可乐", "饮料", 200.0, "瓶", 180, "正常", "high", 6.0, 3.5),
    ("STORE_003", "P207", "冰糖", "调料", 60.0, "袋", 365, "正常", "normal", 5.0, 3.0),
    ("STORE_003", "P208", "八角", "调料", 80.0, "袋", 365, "正常", "normal", 3.0, 1.5),
    ("STORE_004", "P301", "猪肉馅", "肉类", 60.0, "kg", 2, "临期", "normal", 22.0, 15.0),
    ("STORE_004", "P302", "白菜", "蔬菜", 70.0, "kg", 1, "临期", "normal", 3.0, 1.5),
    ("STORE_004", "P303", "面粉", "主食", 200.0, "袋", 365, "正常", "high", 8.0, 5.0),
    ("STORE_004", "P304", "韭菜", "蔬菜", 30.0, "kg", 3, "正常", "normal", 8.0, 5.0),
    ("STORE_004", "P305", "鸡蛋", "蛋类", 150.0, "盒", 10, "正常", "normal", 12.0, 8.0),
    ("STORE_004", "P306", "速冻水饺", "熟食", 400.0, "袋", 90, "正常", "high", 15.0, 9.0),
    ("STORE_004", "P307", "陈醋", "调料", 150.0, "瓶", 365, "正常", "normal", 6.0, 3.5),
    ("STORE_004", "P308", "蒜", "调料", 80.0, "kg", 30, "正常", "normal", 10.0, 6.0),
]


STORE_PRODUCT_ID_STARTS = {
    "STORE_001": 0,
    "STORE_002": 100,
    "STORE_003": 200,
    "STORE_004": 300,
}
SCENARIO_FILES = {
    "STORE_001": "test_store_s1_rainy.json",
    "STORE_002": "test_store_s2_hot.json",
    "STORE_003": "test_store_s3_weekend.json",
    "STORE_004": "test_store_s4_winter.json",
}
REFERENCE_CATEGORY_NAMES = {
    "dairy": "乳品",
    "fruit": "水果",
    "meat": "肉类",
    "seafood": "水产",
    "vegetable": "蔬菜",
}
REFERENCE_CATEGORY_UNITS = {
    "dairy": "盒",
    "fruit": "kg",
    "meat": "kg",
    "seafood": "份",
    "vegetable": "kg",
}
SUPPLEMENTAL_EXPIRY_DAYS = (3, 5, 7, 10, 15, 30, 90, 180, 365, 4, 6, 14)


def _load_reference_products() -> list[dict[str, Any]]:
    with REFERENCE_PRODUCTS_PATH.open("r", encoding="utf-8") as source_file:
        products = json.load(source_file)
    if not isinstance(products, list):
        raise ValueError("seed-products.json must contain a product array")
    return [product for product in products if isinstance(product, dict)]


def _supplemental_products() -> list[tuple[Any, ...]]:
    reference_products = _load_reference_products()
    if not reference_products:
        raise ValueError("seed-products.json must contain at least one product")

    all_products: list[tuple[Any, ...]] = list(CORE_PRODUCTS)
    for store_position, (store_id, *_store_details) in enumerate(STORES):
        core_products = [product for product in CORE_PRODUCTS if product[0] == store_id]
        existing_names = {str(product[2]) for product in core_products}
        required_count = PRODUCTS_PER_STORE - len(core_products)
        candidates: list[dict[str, Any]] = []

        for reference_offset in range(len(reference_products)):
            reference = reference_products[
                (store_position * 11 + reference_offset) % len(reference_products)
            ]
            product_name = str(reference.get("name", "")).strip()
            if not product_name or product_name in existing_names:
                continue
            candidates.append(reference)
            existing_names.add(product_name)
            if len(candidates) == required_count:
                break

        if len(candidates) != required_count:
            raise ValueError(
                f"seed-products.json does not provide enough unique products for {store_id}"
            )

        stock_multiplier = (0.95, 1.05, 1.12, 1.20)[store_position]
        product_id_start = STORE_PRODUCT_ID_STARTS[store_id]
        for supplemental_index, reference in enumerate(candidates, start=1):
            reference_category = str(reference.get("category", "其他")).strip().lower()
            category = REFERENCE_CATEGORY_NAMES.get(reference_category, reference_category)
            unit = REFERENCE_CATEGORY_UNITS.get(reference_category, "件")
            stock = round(max(1.0, float(reference.get("stock", 1)) * stock_multiplier), 1)
            current_price = round(float(reference.get("price", 0)), 2)
            unit_cost = round(float(reference.get("cost_price", 0)), 2)
            expiry_days = SUPPLEMENTAL_EXPIRY_DAYS[
                (supplemental_index + store_position * 2) % len(SUPPLEMENTAL_EXPIRY_DAYS)
            ]
            turnover_days = float(reference.get("stock_turnover_days", 0))
            stock_level = (
                "high"
                if turnover_days >= 14 or supplemental_index in {9, 21, 33}
                else "normal"
            )
            product_number = product_id_start + len(core_products) + supplemental_index
            all_products.append(
                (
                    store_id,
                    f"P{product_number:03d}",
                    str(reference["name"]).strip(),
                    category,
                    stock,
                    unit,
                    expiry_days,
                    "正常",
                    stock_level,
                    current_price,
                    unit_cost,
                )
            )

    product_counts = {
        store_id: sum(1 for product in all_products if product[0] == store_id)
        for store_id, *_store_details in STORES
    }
    if any(count != PRODUCTS_PER_STORE for count in product_counts.values()):
        raise RuntimeError(f"Unexpected per-store product counts: {product_counts}")
    return [
        (*product[:4], round(float(product[4]) * INVENTORY_STOCK_SCALE, 2), *product[5:])
        for product in all_products
    ]


PRODUCTS = _supplemental_products()


def _scenario_inventory_rows(store_id: str) -> list[dict[str, Any]]:
    return [
        {
            "product_id": product_id,
            "name": name,
            "category": category,
            "stock": stock,
            "unit": unit,
            "expiry_days": expiry_days,
            "status": freshness_status,
            "stock_level": stock_level,
            "price": current_price,
            "cost": unit_cost,
        }
        for (
            product_store_id,
            product_id,
            name,
            category,
            stock,
            unit,
            expiry_days,
            freshness_status,
            stock_level,
            current_price,
            unit_cost,
        ) in PRODUCTS
        if product_store_id == store_id
    ]


def sync_scenario_files(data_dir: Path) -> None:
    """Keep the selectable JSON scenario inventory aligned with the MCP fixture."""
    for store_id, filename in SCENARIO_FILES.items():
        scenario_path = data_dir / filename
        with scenario_path.open("r", encoding="utf-8") as scenario_file:
            scenario = json.load(scenario_file)
        if scenario.get("store_info", {}).get("store_id") != store_id:
            raise ValueError(f"Scenario file does not match {store_id}: {scenario_path}")
        scenario["inventory"] = _scenario_inventory_rows(store_id)
        scenario_path.write_text(
            json.dumps(scenario, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Synced {len(scenario['inventory'])} products to {scenario_path}")


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE stores (
    store_id TEXT PRIMARY KEY,
    store_name TEXT NOT NULL,
    city TEXT NOT NULL,
    timezone TEXT NOT NULL,
    scenario_date TEXT NOT NULL
);

CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit TEXT NOT NULL,
    unit_cost REAL NOT NULL CHECK (unit_cost >= 0)
);

CREATE TABLE inventory_snapshots (
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    product_id TEXT NOT NULL REFERENCES products(product_id),
    as_of_date TEXT NOT NULL,
    snapshot_at TEXT NOT NULL,
    on_hand_qty REAL NOT NULL CHECK (on_hand_qty >= 0),
    reserved_qty REAL NOT NULL CHECK (reserved_qty >= 0),
    available_qty REAL NOT NULL CHECK (available_qty >= 0),
    inbound_qty REAL NOT NULL CHECK (inbound_qty >= 0),
    expiry_days INTEGER NOT NULL CHECK (expiry_days >= 0),
    expiry_date TEXT NOT NULL,
    freshness_status TEXT NOT NULL,
    stock_level TEXT NOT NULL,
    PRIMARY KEY (store_id, product_id, as_of_date)
);

CREATE TABLE price_snapshots (
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    product_id TEXT NOT NULL REFERENCES products(product_id),
    as_of_date TEXT NOT NULL,
    currency TEXT NOT NULL,
    regular_price REAL NOT NULL CHECK (regular_price >= 0),
    current_price REAL NOT NULL CHECK (current_price >= 0),
    unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
    promotion_label TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (store_id, product_id, as_of_date)
);

CREATE TABLE sales_daily (
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    product_id TEXT NOT NULL REFERENCES products(product_id),
    sales_date TEXT NOT NULL,
    units_sold REAL NOT NULL CHECK (units_sold >= 0),
    waste_qty REAL NOT NULL CHECK (waste_qty >= 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    gross_sales REAL NOT NULL CHECK (gross_sales >= 0),
    discount_amount REAL NOT NULL CHECK (discount_amount >= 0),
    net_sales REAL NOT NULL CHECK (net_sales >= 0),
    PRIMARY KEY (store_id, product_id, sales_date)
);

CREATE INDEX idx_inventory_store_date ON inventory_snapshots(store_id, as_of_date);
CREATE INDEX idx_prices_store_date ON price_snapshots(store_id, as_of_date);
CREATE INDEX idx_sales_store_date ON sales_daily(store_id, sales_date);
CREATE INDEX idx_sales_product_date ON sales_daily(product_id, sales_date);
"""


def _snapshot_time(as_of_date: date) -> str:
    china_timezone = timezone(timedelta(hours=8))
    return datetime.combine(as_of_date, datetime.min.time(), china_timezone).replace(hour=8).isoformat()


def build_database(db_path: Path, force: bool = False) -> None:
    db_path = db_path.resolve()
    if db_path.exists() and not force:
        raise FileExistsError(f"Database already exists: {db_path}. Use --force to recreate it.")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = db_path.with_suffix(db_path.suffix + ".tmp")
    temporary_path.unlink(missing_ok=True)
    rng = random.Random(SEED)
    store_dates = {store_id: date.fromisoformat(scenario_date) for store_id, _, _, _, scenario_date in STORES}

    try:
        with closing(sqlite3.connect(temporary_path)) as connection:
            connection.executescript(SCHEMA)
            connection.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                [
                    ("dataset_name", "AIFreshFoodAssistant store operational dataset"),
                    ("dataset_version", "2026-07-16.v5"),
                    ("dataset_kind", "store-operational-data"),
                    ("currency", "CNY"),
                    ("timezone", "Asia/Shanghai"),
                    ("seed", str(SEED)),
                    ("sales_lookback_days", str(SALES_LOOKBACK_DAYS)),
                    ("inventory_stock_scale", str(INVENTORY_STOCK_SCALE)),
                ],
            )
            connection.executemany(
                """
                INSERT INTO stores(store_id, store_name, city, timezone, scenario_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                STORES,
            )
            connection.executemany(
                """
                INSERT INTO products(product_id, store_id, product_name, category, unit, unit_cost)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (product_id, store_id, name, category, unit, cost)
                    for store_id, product_id, name, category, _, unit, _, _, _, _, cost in PRODUCTS
                ],
            )

            inventory_rows = []
            price_rows = []
            sales_rows = []
            for product_index, (
                store_id,
                product_id,
                name,
                category,
                stock,
                unit,
                expiry_days,
                freshness_status,
                stock_level,
                current_price,
                unit_cost,
            ) in enumerate(PRODUCTS):
                as_of_date = store_dates[store_id]
                snapshot_at = _snapshot_time(as_of_date)
                expiry_date = as_of_date + timedelta(days=expiry_days)
                inbound_factor = {"low": 0.30, "normal": 0.12, "high": 0.05}.get(stock_level, 0.10)
                inbound_qty = round(stock * inbound_factor, 1)
                inventory_rows.append(
                    (
                        store_id,
                        product_id,
                        as_of_date.isoformat(),
                        snapshot_at,
                        stock,
                        0.0,
                        stock,
                        inbound_qty,
                        expiry_days,
                        expiry_date.isoformat(),
                        freshness_status,
                        stock_level,
                    )
                )

                if freshness_status == "临期":
                    regular_price = round(current_price / 0.88, 2)
                    promotion_label = "临期促销"
                else:
                    regular_price = current_price
                    promotion_label = None
                price_rows.append(
                    (
                        store_id,
                        product_id,
                        as_of_date.isoformat(),
                        "CNY",
                        regular_price,
                        current_price,
                        unit_cost,
                        promotion_label,
                        snapshot_at,
                    )
                )

                sales_start = as_of_date - timedelta(days=SALES_LOOKBACK_DAYS)
                sales_end = as_of_date - timedelta(days=1)
                sales_date = sales_start
                base_divisor = {"low": 4.0, "normal": 7.0, "high": 10.0}.get(stock_level, 7.0)
                base_demand = max(1.0, stock / INVENTORY_STOCK_SCALE / base_divisor)
                while sales_date <= sales_end:
                    day_index = (sales_date - sales_start).days
                    weekday_factor = (0.88, 0.92, 0.96, 1.00, 1.10, 1.24, 1.17)[sales_date.weekday()]
                    seasonal_factor = 1.0 + 0.08 * math.sin((day_index + product_index) / 4.5)
                    units_sold = round(
                        max(0.0, base_demand * weekday_factor * seasonal_factor * rng.uniform(0.86, 1.14)),
                        2,
                    )
                    promo_active = freshness_status == "临期" and sales_date >= sales_end - timedelta(days=6)
                    actual_unit_price = current_price if promo_active else regular_price
                    gross_sales = round(units_sold * regular_price, 2)
                    net_sales = round(units_sold * actual_unit_price, 2)
                    discount_amount = round(gross_sales - net_sales, 2)
                    perishability = 0.025 if expiry_days <= 3 else (0.01 if expiry_days <= 10 else 0.002)
                    waste_qty = round(max(0.0, units_sold * perishability + rng.uniform(0.0, 0.25)), 2)
                    sales_rows.append(
                        (
                            store_id,
                            product_id,
                            sales_date.isoformat(),
                            units_sold,
                            waste_qty,
                            actual_unit_price,
                            gross_sales,
                            discount_amount,
                            net_sales,
                        )
                    )
                    sales_date += timedelta(days=1)

            connection.executemany(
                """
                INSERT INTO inventory_snapshots(
                    store_id, product_id, as_of_date, snapshot_at, on_hand_qty,
                    reserved_qty, available_qty, inbound_qty, expiry_days,
                    expiry_date, freshness_status, stock_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                inventory_rows,
            )
            connection.executemany(
                """
                INSERT INTO price_snapshots(
                    store_id, product_id, as_of_date, currency, regular_price,
                    current_price, unit_cost, promotion_label, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                price_rows,
            )
            connection.executemany(
                """
                INSERT INTO sales_daily(
                    store_id, product_id, sales_date, units_sold, waste_qty,
                    unit_price, gross_sales, discount_amount, net_sales
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                sales_rows,
            )
            connection.commit()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"SQLite integrity check failed: {integrity}")

        db_path.unlink(missing_ok=True)
        temporary_path.replace(db_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    print(f"Created store operational database: {db_path}")
    print(f"Stores: {len(STORES)}, products: {len(PRODUCTS)}, sales rows: {len(sales_rows)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the store operational SQLite database.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Output SQLite database path.")
    parser.add_argument("--force", action="store_true", help="Replace an existing database.")
    parser.add_argument(
        "--sync-scenarios",
        action="store_true",
        help="Update the four selectable JSON scenarios with the generated 50-SKU inventory.",
    )
    parser.add_argument(
        "--scenario-dir",
        type=Path,
        default=DEFAULT_SCENARIO_DATA_DIR,
        help="Directory containing the selectable JSON scenarios.",
    )
    arguments = parser.parse_args()
    build_database(arguments.db, force=arguments.force)
    if arguments.sync_scenarios:
        sync_scenario_files(arguments.scenario_dir)


if __name__ == "__main__":
    main()
