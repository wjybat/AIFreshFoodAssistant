from __future__ import annotations

import argparse
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from data_access import (
    CurrentPricesResponse,
    DatasetInfoResponse,
    FreshFoodRepository,
    InventoryResponse,
    SalesHistoryResponse,
    StoresResponse,
)


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "fresh_food_dev.sqlite3"
LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def create_server(
    db_path: str | Path | None = None,
    port: int = DEFAULT_PORT,
) -> FastMCP:
    repository = FreshFoodRepository(
        db_path or os.environ.get("FRESH_FOOD_MCP_DB", DEFAULT_DB_PATH)
    )
    server = FastMCP(
        "AIFreshFoodAssistant Development Data",
        instructions=(
            "Read-only DEVELOPMENT-FAKE fresh-food data. Never represent these values as production data. "
            "For recommendation work, inspect store metadata first, then retrieve inventory, sales history, "
            "and current prices with separate tool calls so each reasoning step has explicit evidence."
        ),
        host=LOOPBACK_HOST,
        port=port,
        json_response=True,
    )

    @server.tool()
    def get_dataset_info() -> DatasetInfoResponse:
        """Describe dataset coverage, store dates, row counts, and its development-fake status."""
        return repository.get_dataset_info()

    @server.tool()
    def list_stores() -> StoresResponse:
        """List store IDs, inventory dates, sales windows, and product counts."""
        return repository.list_stores()

    @server.tool()
    def get_inventory(store_id: str, as_of_date: str) -> InventoryResponse:
        """
        Read one store's inventory snapshot on YYYY-MM-DD.

        The response includes per-product units, available quantities, inbound quantities, and freshness.
        """
        return repository.get_inventory(store_id, as_of_date)

    @server.tool()
    def get_sales_history(
        store_id: str,
        start_date: str,
        end_date: str,
        product_ids: list[str] | None = None,
    ) -> SalesHistoryResponse:
        """
        Read daily sales and waste rows for an inclusive YYYY-MM-DD window.

        product_ids is optional; omit it to retrieve all products in the store.
        """
        return repository.get_sales_history(store_id, start_date, end_date, product_ids)

    @server.tool()
    def get_current_prices(
        store_id: str,
        as_of_date: str,
        product_ids: list[str] | None = None,
    ) -> CurrentPricesResponse:
        """
        Read one store's price snapshot on YYYY-MM-DD.

        product_ids is optional; rows include CNY regular price, current price, unit cost, and margin.
        """
        return repository.get_current_prices(store_id, as_of_date, product_ids)

    return server


# MCP development tooling can import this module-level object as `server:mcp`.
mcp = create_server()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the read-only development fresh-food MCP server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport; stdio is the safest default for local agent integration.",
    )
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="HTTP bind port.")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.environ.get("FRESH_FOOD_MCP_DB", DEFAULT_DB_PATH)),
        help="Path to the SQLite development database.",
    )
    arguments = parser.parse_args()

    runtime_server = create_server(arguments.db, port=arguments.port)
    runtime_server.run(transport=arguments.transport)


if __name__ == "__main__":
    main()
