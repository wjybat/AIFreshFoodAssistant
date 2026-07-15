from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Literal

from typing_extensions import TypedDict


SourceName = Literal["development-fake-sqlite"]


class InventoryRow(TypedDict):
    product_id: str
    product_name: str
    category: str
    unit: str
    snapshot_at: str
    on_hand_qty: float
    reserved_qty: float
    available_qty: float
    inbound_qty: float
    expiry_days: int
    expiry_date: str
    freshness_status: str
    stock_level: str


class InventoryResponse(TypedDict):
    source: SourceName
    store_id: str
    as_of_date: str
    units: str
    rows: list[InventoryRow]


class SalesWindow(TypedDict):
    start_date: str
    end_date: str


class SalesRow(TypedDict):
    sales_date: str
    product_id: str
    product_name: str
    category: str
    unit: str
    units_sold: float
    waste_qty: float
    unit_price: float
    gross_sales: float
    discount_amount: float
    net_sales: float


class SalesHistoryResponse(TypedDict):
    source: SourceName
    store_id: str
    window: SalesWindow
    currency: str
    units: str
    rows: list[SalesRow]


class PriceRow(TypedDict):
    product_id: str
    product_name: str
    category: str
    unit: str
    regular_price: float
    current_price: float
    unit_cost: float
    discount_pct: float
    gross_margin_pct: float
    promotion_label: str | None
    updated_at: str


class CurrentPricesResponse(TypedDict):
    source: SourceName
    store_id: str
    as_of_date: str
    currency: str
    units: str
    rows: list[PriceRow]


class StoreRow(TypedDict):
    store_id: str
    store_name: str
    city: str
    timezone: str
    inventory_as_of_date: str
    sales_start_date: str
    sales_end_date: str
    product_count: int


class StoresResponse(TypedDict):
    source: SourceName
    rows: list[StoreRow]


class DatasetInfoResponse(TypedDict):
    source: SourceName
    read_only: bool
    database_path: str
    metadata: dict[str, str]
    counts: dict[str, int]
    store_dates: dict[str, str]


class FreshFoodRepository:
    """Read-only access to the deterministic development dataset."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser().resolve()

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.is_file():
            raise FileNotFoundError(
                f"Development database not found at {self.db_path}. Run `uv run python seed.py --force`."
            )
        connection = sqlite3.connect(f"{self.db_path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA trusted_schema = OFF")
        return connection

    @staticmethod
    def _dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    @staticmethod
    def _parse_date(value: str, field_name: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must use ISO format YYYY-MM-DD") from exc

    @staticmethod
    def _normalize_product_ids(product_ids: list[str] | None) -> list[str]:
        if not product_ids:
            return []
        normalized = list(
            dict.fromkeys(value.strip() for value in product_ids if value and value.strip())
        )
        if len(normalized) > 100:
            raise ValueError("At most 100 product_ids can be requested at once")
        return normalized

    @staticmethod
    def _ensure_store(connection: sqlite3.Connection, store_id: str) -> None:
        found = connection.execute(
            "SELECT 1 FROM stores WHERE store_id = ?",
            (store_id,),
        ).fetchone()
        if not found:
            raise ValueError(f"Unknown store_id: {store_id}")

    def get_dataset_info(self) -> DatasetInfoResponse:
        with closing(self._connect()) as connection:
            metadata = {
                row["key"]: row["value"]
                for row in connection.execute("SELECT key, value FROM metadata ORDER BY key")
            }
            counts = {
                "stores": connection.execute("SELECT COUNT(*) FROM stores").fetchone()[0],
                "products": connection.execute("SELECT COUNT(*) FROM products").fetchone()[0],
                "inventory_rows": connection.execute(
                    "SELECT COUNT(*) FROM inventory_snapshots"
                ).fetchone()[0],
                "price_rows": connection.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0],
                "sales_rows": connection.execute("SELECT COUNT(*) FROM sales_daily").fetchone()[0],
            }
            store_dates = {
                row["store_id"]: row["scenario_date"]
                for row in connection.execute(
                    "SELECT store_id, scenario_date FROM stores ORDER BY store_id"
                )
            }
        return {
            "source": "development-fake-sqlite",
            "read_only": True,
            "database_path": str(self.db_path),
            "metadata": metadata,
            "counts": counts,
            "store_dates": store_dates,
        }

    def list_stores(self) -> StoresResponse:
        with closing(self._connect()) as connection:
            rows = self._dicts(
                connection.execute(
                    """
                    SELECT
                        s.store_id,
                        s.store_name,
                        s.city,
                        s.timezone,
                        s.scenario_date AS inventory_as_of_date,
                        MIN(sd.sales_date) AS sales_start_date,
                        MAX(sd.sales_date) AS sales_end_date,
                        COUNT(DISTINCT p.product_id) AS product_count
                    FROM stores AS s
                    LEFT JOIN products AS p ON p.store_id = s.store_id
                    LEFT JOIN sales_daily AS sd ON sd.store_id = s.store_id
                    GROUP BY s.store_id, s.store_name, s.city, s.timezone, s.scenario_date
                    ORDER BY s.store_id
                    """
                ).fetchall()
            )
        return {"source": "development-fake-sqlite", "rows": rows}  # type: ignore[return-value]

    def get_inventory(self, store_id: str, as_of_date: str) -> InventoryResponse:
        resolved_date = self._parse_date(as_of_date, "as_of_date").isoformat()
        with closing(self._connect()) as connection:
            self._ensure_store(connection, store_id)
            rows = self._dicts(
                connection.execute(
                    """
                    SELECT
                        i.product_id,
                        p.product_name,
                        p.category,
                        p.unit,
                        i.snapshot_at,
                        ROUND(i.on_hand_qty, 2) AS on_hand_qty,
                        ROUND(i.reserved_qty, 2) AS reserved_qty,
                        ROUND(i.available_qty, 2) AS available_qty,
                        ROUND(i.inbound_qty, 2) AS inbound_qty,
                        i.expiry_days,
                        i.expiry_date,
                        i.freshness_status,
                        i.stock_level
                    FROM inventory_snapshots AS i
                    JOIN products AS p ON p.product_id = i.product_id
                    WHERE i.store_id = ? AND i.as_of_date = ?
                    ORDER BY p.category, p.product_name, i.product_id
                    """,
                    (store_id, resolved_date),
                ).fetchall()
            )
            if not rows:
                available = connection.execute(
                    "SELECT DISTINCT as_of_date FROM inventory_snapshots WHERE store_id = ? ORDER BY as_of_date",
                    (store_id,),
                ).fetchall()
                dates = [row[0] for row in available]
                raise ValueError(
                    f"No inventory snapshot for {store_id} on {resolved_date}; available dates: {dates}"
                )
        return {
            "source": "development-fake-sqlite",
            "store_id": store_id,
            "as_of_date": resolved_date,
            "units": "per-row; see rows[].unit",
            "rows": rows,
        }  # type: ignore[return-value]

    def get_sales_history(
        self,
        store_id: str,
        start_date: str,
        end_date: str,
        product_ids: list[str] | None = None,
    ) -> SalesHistoryResponse:
        resolved_start = self._parse_date(start_date, "start_date")
        resolved_end = self._parse_date(end_date, "end_date")
        if resolved_start > resolved_end:
            raise ValueError("start_date must not be later than end_date")
        normalized_ids = self._normalize_product_ids(product_ids)
        where = ["sd.store_id = ?", "sd.sales_date BETWEEN ? AND ?"]
        parameters: list[Any] = [store_id, resolved_start.isoformat(), resolved_end.isoformat()]
        if normalized_ids:
            where.append(f"sd.product_id IN ({','.join('?' for _ in normalized_ids)})")
            parameters.extend(normalized_ids)

        with closing(self._connect()) as connection:
            self._ensure_store(connection, store_id)
            rows = self._dicts(
                connection.execute(
                    f"""
                    SELECT
                        sd.sales_date,
                        sd.product_id,
                        p.product_name,
                        p.category,
                        p.unit,
                        ROUND(sd.units_sold, 2) AS units_sold,
                        ROUND(sd.waste_qty, 2) AS waste_qty,
                        ROUND(sd.unit_price, 2) AS unit_price,
                        ROUND(sd.gross_sales, 2) AS gross_sales,
                        ROUND(sd.discount_amount, 2) AS discount_amount,
                        ROUND(sd.net_sales, 2) AS net_sales
                    FROM sales_daily AS sd
                    JOIN products AS p ON p.product_id = sd.product_id
                    WHERE {' AND '.join(where)}
                    ORDER BY sd.sales_date, sd.product_id
                    """,
                    parameters,
                ).fetchall()
            )
            if not rows:
                bounds = connection.execute(
                    "SELECT MIN(sales_date), MAX(sales_date) FROM sales_daily WHERE store_id = ?",
                    (store_id,),
                ).fetchone()
                raise ValueError(
                    f"No sales rows matched the request; available window for {store_id}: "
                    f"{bounds[0]} through {bounds[1]}"
                )
        return {
            "source": "development-fake-sqlite",
            "store_id": store_id,
            "window": {
                "start_date": resolved_start.isoformat(),
                "end_date": resolved_end.isoformat(),
            },
            "currency": "CNY",
            "units": "per-row; see rows[].unit",
            "rows": rows,
        }  # type: ignore[return-value]

    def get_current_prices(
        self,
        store_id: str,
        as_of_date: str,
        product_ids: list[str] | None = None,
    ) -> CurrentPricesResponse:
        resolved_date = self._parse_date(as_of_date, "as_of_date").isoformat()
        normalized_ids = self._normalize_product_ids(product_ids)
        where = ["ps.store_id = ?", "ps.as_of_date = ?"]
        parameters: list[Any] = [store_id, resolved_date]
        if normalized_ids:
            where.append(f"ps.product_id IN ({','.join('?' for _ in normalized_ids)})")
            parameters.extend(normalized_ids)

        with closing(self._connect()) as connection:
            self._ensure_store(connection, store_id)
            rows = self._dicts(
                connection.execute(
                    f"""
                    SELECT
                        ps.product_id,
                        p.product_name,
                        p.category,
                        p.unit,
                        ROUND(ps.regular_price, 2) AS regular_price,
                        ROUND(ps.current_price, 2) AS current_price,
                        ROUND(ps.unit_cost, 2) AS unit_cost,
                        ROUND(
                            100.0 * (ps.regular_price - ps.current_price) / NULLIF(ps.regular_price, 0),
                            2
                        ) AS discount_pct,
                        ROUND(
                            100.0 * (ps.current_price - ps.unit_cost) / NULLIF(ps.current_price, 0),
                            2
                        ) AS gross_margin_pct,
                        ps.promotion_label,
                        ps.updated_at
                    FROM price_snapshots AS ps
                    JOIN products AS p ON p.product_id = ps.product_id
                    WHERE {' AND '.join(where)}
                    ORDER BY p.category, p.product_name, ps.product_id
                    """,
                    parameters,
                ).fetchall()
            )
            if not rows:
                available = connection.execute(
                    "SELECT DISTINCT as_of_date FROM price_snapshots WHERE store_id = ? ORDER BY as_of_date",
                    (store_id,),
                ).fetchall()
                dates = [row[0] for row in available]
                raise ValueError(
                    f"No price snapshot for {store_id} on {resolved_date}; available dates: {dates}"
                )
        return {
            "source": "development-fake-sqlite",
            "store_id": store_id,
            "as_of_date": resolved_date,
            "currency": "CNY",
            "units": "prices are per rows[].unit",
            "rows": rows,
        }  # type: ignore[return-value]
