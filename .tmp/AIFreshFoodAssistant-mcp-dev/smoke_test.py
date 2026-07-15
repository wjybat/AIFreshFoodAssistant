from __future__ import annotations

import asyncio
import json
import sqlite3

from mcp.shared.memory import create_connected_server_and_client_session

from data_access import FreshFoodRepository
from server import DEFAULT_DB_PATH, mcp


EXPECTED_TOOLS = {
    "get_dataset_info",
    "list_stores",
    "get_inventory",
    "get_sales_history",
    "get_current_prices",
}


async def main() -> None:
    repository = FreshFoodRepository(DEFAULT_DB_PATH)
    connection = repository._connect()
    try:
        try:
            connection.execute("INSERT INTO metadata(key, value) VALUES ('write_test', 'blocked')")
        except sqlite3.OperationalError as error:
            assert "readonly" in str(error).lower() or "read-only" in str(error).lower()
        else:
            raise AssertionError("The repository connection unexpectedly allowed a write")
    finally:
        connection.close()

    async with create_connected_server_and_client_session(mcp, raise_exceptions=True) as session:
        listed = await session.list_tools()
        tool_names = {tool.name for tool in listed.tools}
        missing = EXPECTED_TOOLS - tool_names
        assert not missing, f"Missing tools: {sorted(missing)}"
        tools_by_name = {tool.name: tool for tool in listed.tools}

        inventory_schema = tools_by_name["get_inventory"].inputSchema
        assert set(inventory_schema["properties"]) == {"store_id", "as_of_date"}
        assert set(inventory_schema["required"]) == {"store_id", "as_of_date"}

        sales_schema = tools_by_name["get_sales_history"].inputSchema
        assert set(sales_schema["properties"]) == {
            "store_id",
            "start_date",
            "end_date",
            "product_ids",
        }
        assert set(sales_schema["required"]) == {"store_id", "start_date", "end_date"}

        prices_schema = tools_by_name["get_current_prices"].inputSchema
        assert set(prices_schema["properties"]) == {"store_id", "as_of_date", "product_ids"}
        assert set(prices_schema["required"]) == {"store_id", "as_of_date"}
        assert tools_by_name["get_inventory"].outputSchema["type"] == "object"
        assert tools_by_name["get_sales_history"].outputSchema["type"] == "object"
        assert tools_by_name["get_current_prices"].outputSchema["type"] == "object"

        dataset = await session.call_tool("get_dataset_info", {})
        assert not dataset.isError
        assert dataset.structuredContent["read_only"] is True
        assert dataset.structuredContent["counts"]["stores"] == 4

        inventory = await session.call_tool(
            "get_inventory",
            {"store_id": "STORE_001", "as_of_date": "2026-07-09"},
        )
        assert not inventory.isError
        assert len(inventory.structuredContent["rows"]) == 8
        assert inventory.structuredContent["rows"][0]["unit"]

        sales = await session.call_tool(
            "get_sales_history",
            {
                "store_id": "STORE_001",
                "start_date": "2026-07-02",
                "end_date": "2026-07-08",
                "product_ids": ["P001"],
            },
        )
        assert not sales.isError
        assert len(sales.structuredContent["rows"]) == 7
        assert sales.structuredContent["currency"] == "CNY"

        prices = await session.call_tool(
            "get_current_prices",
            {
                "store_id": "STORE_001",
                "as_of_date": "2026-07-09",
                "product_ids": ["P001", "P003"],
            },
        )
        assert not prices.isError
        assert len(prices.structuredContent["rows"]) == 2
        assert prices.structuredContent["currency"] == "CNY"

        print(
            json.dumps(
                {
                    "status": "ok",
                    "tools": sorted(tool_names),
                    "inventory_rows_checked": len(inventory.structuredContent["rows"]),
                    "sales_rows_checked": len(sales.structuredContent["rows"]),
                    "prices_checked": len(prices.structuredContent["rows"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
