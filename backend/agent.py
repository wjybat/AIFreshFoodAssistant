"""Bounded multi-step agent for acquiring and reconciling store data via MCP."""
from __future__ import annotations

import asyncio
import math
import re
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from time import perf_counter
from typing import Any, AsyncGenerator

from .mcp_client import MCPClientError, MCPToolClient


REQUIRED_MCP_TOOLS = frozenset(
    {"get_inventory", "get_sales_history", "get_current_prices"}
)
SAFE_SOURCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
RAW_OPERATIONAL_INPUT_KEYS = frozenset(
    {
        "sales_history",
        "sales_rows",
        "sales",
        "current_prices",
        "price_history",
        "price_snapshot",
        "prices",
    }
)


class AgentDataError(RuntimeError):
    """Raised when required operational evidence cannot be acquired."""


class OperationalDataAgent:
    """Runs a fixed, inspectable tool plan with strict scope and result guards."""

    def __init__(
        self,
        client: MCPToolClient | None,
        *,
        required: bool = True,
        sales_window_days: int = 28,
        max_products: int = 100,
    ) -> None:
        self.client = client
        self.required = required
        self.sales_window_days = max(1, min(sales_window_days, 90))
        self.max_products = max(1, min(max_products, 100))

    async def run(
        self, input_data: dict[str, Any]
    ) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
        """Yield observable agent events followed by one enriched input result."""
        enriched = deepcopy(input_data)
        trace: list[dict[str, Any]] = []

        scope_running = self._event(
            kind="step",
            event_id="scope",
            state="running",
            label="确认门店与业务日期",
            detail="锁定本次数据查询范围",
        )
        trace.append(scope_running)
        yield "event", scope_running

        try:
            store_id, business_date_text, business_date = self._validate_scope(
                enriched, require_mcp_scope=self.client is not None and self.required
            )
        except AgentDataError as exc:
            failed = self._event(
                kind="step",
                event_id="scope",
                state="failed",
                label="确认门店与业务日期",
                detail=str(exc),
            )
            trace.append(failed)
            yield "event", failed
            raise

        scope_done = self._event(
            kind="step",
            event_id="scope",
            state="completed",
            label="确认门店与业务日期",
            detail=f"{store_id} · {business_date_text}",
        )
        trace.append(scope_done)
        yield "event", scope_done

        if self.client is None:
            no_mcp = self._event(
                kind="step",
                event_id="mcp",
                state="completed",
                label="MCP 数据源未启用",
                detail="继续使用请求中提供的库存与价格数据",
            )
            trace.append(no_mcp)
            yield "event", no_mcp
            enriched["operational_data"] = {
                "transport": "request",
                "source": "request_input",
                "store_id": store_id,
                "business_date": business_date_text,
                "fetched_at": self._utc_now(),
                "agent_trace": trace,
            }
            yield "result", {"input_data": enriched, "trace": trace}
            return

        store_info = enriched.get("store_info") or {}
        has_stable_store_id = bool(str(store_info.get("store_id") or "").strip())
        if not has_stable_store_id or business_date is None:
            failure = self._event(
                kind="step",
                event_id="mcp",
                state="failed",
                label="获取门店经营数据",
                detail="缺少稳定门店 ID 或 ISO 业务日期，无法安全查询 MCP",
            )
            trace.append(failure)
            yield "event", failure
            if self.required:
                raise AgentDataError("MCP 模式需要稳定门店 ID 和 YYYY-MM-DD 日期")
            enriched["operational_data"] = self._fallback_operational_data(
                enriched,
                trace,
                store_id,
                business_date_text,
                "MCP 查询作用域不完整，已回退到请求输入",
            )
            yield "result", {"input_data": enriched, "trace": trace}
            return

        try:
            async for event_type, payload in self._run_mcp_plan(
                enriched, trace, store_id, business_date
            ):
                yield event_type, payload
        except (MCPClientError, AgentDataError) as exc:
            latest_by_id: dict[str, dict[str, Any]] = {}
            for event in trace:
                latest_by_id[str(event.get("id", ""))] = event
            for event in latest_by_id.values():
                if event.get("state") != "running":
                    continue
                unfinished = dict(event)
                unfinished["state"] = "failed"
                unfinished["detail"] = "该步骤未完成，后续生成已停止"
                trace.append(unfinished)
                yield "event", unfinished
            failure = self._event(
                kind="step",
                event_id="mcp",
                state="failed",
                label="获取门店经营数据",
                detail="MCP 数据不可用或不符合约定",
            )
            trace.append(failure)
            yield "event", failure
            if self.required:
                raise AgentDataError("无法获取必需的门店经营数据") from exc

            enriched["operational_data"] = self._fallback_operational_data(
                enriched,
                trace,
                store_id,
                business_date_text,
                "MCP 数据不可用，已回退到请求输入",
            )
            yield "result", {"input_data": enriched, "trace": trace}

    async def _run_mcp_plan(
        self,
        enriched: dict[str, Any],
        trace: list[dict[str, Any]],
        store_id: str,
        business_date: date,
    ) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
        discovery = self._event(
            kind="step",
            event_id="discover",
            state="running",
            label="发现 MCP 数据工具",
            detail="仅允许库存、销售与价格只读工具",
        )
        trace.append(discovery)
        yield "event", discovery

        assert self.client is not None
        async with self.client.connect() as session:
            tools = await session.list_tools()
            available = {tool.name for tool in tools}
            missing = REQUIRED_MCP_TOOLS - available
            if missing:
                raise AgentDataError(
                    "MCP 服务缺少必需工具: " + ", ".join(sorted(missing))
                )

            discovered = self._event(
                kind="step",
                event_id="discover",
                state="completed",
                label="发现 MCP 数据工具",
                detail="已验证 3 个只读工具",
                source="mcp",
            )
            trace.append(discovered)
            yield "event", discovered

            inventory_start = perf_counter()
            inventory_running = self._event(
                kind="tool",
                event_id="inventory",
                parent_id="mcp",
                state="running",
                label="读取库存快照",
                detail=f"{store_id} · {business_date.isoformat()}",
                tool_name="get_inventory",
            )
            trace.append(inventory_running)
            yield "event", inventory_running
            inventory_payload = await session.call_tool(
                "get_inventory",
                {
                    "store_id": store_id,
                    "as_of_date": business_date.isoformat(),
                },
            )
            self._validate_payload_scope(
                inventory_payload,
                store_id=store_id,
                as_of_date=business_date.isoformat(),
            )
            all_inventory_rows = self._extract_rows(
                inventory_payload, "items", "inventory", "rows"
            )
            if not all_inventory_rows:
                raise AgentDataError("MCP inventory result is empty")
            normalized_all_inventory = self._normalize_inventory(all_inventory_rows)
            self._validate_inventory_rows(normalized_all_inventory)
            normalized_inventory = self._select_inventory_candidates(
                normalized_all_inventory, self.max_products
            )
            product_ids = self._validate_inventory_rows(normalized_inventory)

            inventory_done = self._event(
                kind="tool",
                event_id="inventory",
                parent_id="mcp",
                state="completed",
                label="读取库存快照",
                detail=(
                    f"返回 {len(normalized_all_inventory)} 个 SKU"
                    + (
                        f"，选取优先级最高的 {len(normalized_inventory)} 个"
                        if len(normalized_all_inventory) > len(normalized_inventory)
                        else ""
                    )
                ),
                tool_name="get_inventory",
                source=str(inventory_payload.get("source", "mcp")),
                duration_ms=self._elapsed_ms(inventory_start),
            )
            trace.append(inventory_done)
            yield "event", inventory_done

            sales_end = business_date - timedelta(days=1)
            window_start = sales_end - timedelta(days=self.sales_window_days - 1)
            sales_running = self._event(
                kind="tool",
                event_id="sales",
                parent_id="mcp",
                state="running",
                label="读取历史销售",
                detail=f"最近 {self.sales_window_days} 天",
                tool_name="get_sales_history",
            )
            prices_running = self._event(
                kind="tool",
                event_id="prices",
                parent_id="mcp",
                state="running",
                label="读取当前价格",
                detail=f"核对 {len(product_ids)} 个 SKU",
                tool_name="get_current_prices",
            )
            trace.extend((sales_running, prices_running))
            yield "event", sales_running
            yield "event", prices_running

            sales_start = perf_counter()
            prices_start = perf_counter()
            sales_task = asyncio.create_task(
                session.call_tool(
                    "get_sales_history",
                    {
                        "store_id": store_id,
                        "start_date": window_start.isoformat(),
                        "end_date": sales_end.isoformat(),
                        "product_ids": product_ids,
                    },
                )
            )
            prices_task = asyncio.create_task(
                session.call_tool(
                    "get_current_prices",
                    {
                        "store_id": store_id,
                        "as_of_date": business_date.isoformat(),
                        "product_ids": product_ids,
                    },
                )
            )
            sales_result, prices_result = await asyncio.gather(
                sales_task, prices_task, return_exceptions=True
            )

            if isinstance(sales_result, BaseException):
                sales_failed = self._event(
                    kind="tool",
                    event_id="sales",
                    parent_id="mcp",
                    state="failed",
                    label="读取历史销售",
                    detail="销售数据查询失败",
                    tool_name="get_sales_history",
                )
                trace.append(sales_failed)
                yield "event", sales_failed
                raise MCPClientError("Sales tool failed") from sales_result
            if isinstance(prices_result, BaseException):
                prices_failed = self._event(
                    kind="tool",
                    event_id="prices",
                    parent_id="mcp",
                    state="failed",
                    label="读取当前价格",
                    detail="价格数据查询失败",
                    tool_name="get_current_prices",
                )
                trace.append(prices_failed)
                yield "event", prices_failed
                raise MCPClientError("Price tool failed") from prices_result

            self._validate_payload_scope(
                sales_result,
                store_id=store_id,
                start_date=window_start.isoformat(),
                end_date=sales_end.isoformat(),
            )
            self._validate_payload_scope(
                prices_result,
                store_id=store_id,
                as_of_date=business_date.isoformat(),
            )

            sales_rows = self._extract_rows(sales_result, "items", "sales", "rows")
            price_rows = self._extract_rows(prices_result, "items", "prices", "rows")
            requested_products = set(product_ids)
            sales_currency = self._validate_currency(sales_result, "sales")
            price_currency = self._validate_currency(prices_result, "price")
            if sales_currency != price_currency:
                raise AgentDataError("MCP sales and price currencies do not match")
            if sales_currency != "CNY":
                raise AgentDataError("This application currently requires CNY MCP data")

            sales_products: set[str] = set()
            for row in sales_rows:
                product_id = str(row.get("product_id", "")).strip()
                if not product_id:
                    raise AgentDataError("MCP sales rows require product_id")
                row["product_id"] = product_id
                sales_products.add(product_id)
                sales_date_text = str(row.get("sales_date", "")).strip()
                try:
                    sales_date = date.fromisoformat(sales_date_text)
                except ValueError as exc:
                    raise AgentDataError(
                        "MCP sales rows require an ISO sales_date"
                    ) from exc
                if not window_start <= sales_date <= sales_end:
                    raise AgentDataError(
                        "MCP sales row date is outside the requested window"
                    )
                row["sales_date"] = sales_date.isoformat()
                units = row.get("units_sold", row.get("quantity", row.get("units")))
                revenue = row.get(
                    "revenue", row.get("net_sales", row.get("gross_sales"))
                )
                units_value = self._required_number(units, "sales units")
                revenue_value = self._required_number(revenue, "sales revenue")
                if units_value < 0:
                    raise AgentDataError("MCP sales contains a negative units value")
                if revenue_value < 0:
                    raise AgentDataError("MCP sales contains a negative revenue value")
                row["units_sold"] = self._json_number(units_value)
                row["revenue"] = self._json_number(revenue_value)
            if not sales_products.issubset(requested_products):
                raise AgentDataError("MCP sales result contains products outside request scope")

            price_products: list[str] = []
            for row in price_rows:
                product_id = str(row.get("product_id", "")).strip()
                if not product_id:
                    raise AgentDataError("MCP price rows require product_id")
                row["product_id"] = product_id
                price_products.append(product_id)
            if (
                len(price_products) != len(set(price_products))
                or set(price_products) != requested_products
            ):
                raise AgentDataError("MCP price result does not exactly cover inventory products")
            for row in price_rows:
                current_price = row.get("current_price", row.get("price"))
                unit_cost = row.get("unit_cost", row.get("cost"))
                current_price_value = self._required_number(
                    current_price, "current price"
                )
                unit_cost_value = self._required_number(unit_cost, "unit cost")
                if current_price_value < 0:
                    raise AgentDataError("MCP price contains a negative current price")
                if unit_cost_value < 0:
                    raise AgentDataError("MCP price contains a negative unit cost")
                row["current_price"] = self._json_number(current_price_value)
                row["unit_cost"] = self._json_number(unit_cost_value)
                for field in ("regular_price", "discount_pct", "gross_margin_pct"):
                    if field not in row or row[field] in (None, ""):
                        continue
                    value = self._required_number(row[field], field.replace("_", " "))
                    if field == "regular_price" and value < 0:
                        raise AgentDataError("MCP regular price cannot be negative")
                    row[field] = self._json_number(value)
            sales_done = self._event(
                kind="tool",
                event_id="sales",
                parent_id="mcp",
                state="completed",
                label="读取历史销售",
                detail=f"返回 {len(sales_rows)} 条销售记录",
                tool_name="get_sales_history",
                source=str(sales_result.get("source", "mcp")),
                duration_ms=self._elapsed_ms(sales_start),
            )
            prices_done = self._event(
                kind="tool",
                event_id="prices",
                parent_id="mcp",
                state="completed",
                label="读取当前价格",
                detail=f"覆盖 {len(price_rows)} 个 SKU",
                tool_name="get_current_prices",
                source=str(prices_result.get("source", "mcp")),
                duration_ms=self._elapsed_ms(prices_start),
            )
            trace.extend((sales_done, prices_done))
            yield "event", sales_done
            yield "event", prices_done

        reconcile_running = self._event(
            kind="step",
            event_id="reconcile",
            state="running",
            label="校验并归一化经营证据",
            detail="合并库存、销量、售价与成本",
        )
        trace.append(reconcile_running)
        yield "event", reconcile_running

        inventory = self._merge_prices(normalized_inventory, price_rows)
        sales_summary = self._summarize_sales(sales_rows)
        operational_analysis = self._analyze_inventory(inventory, sales_summary)
        source_names = {
            str(payload.get("source", "mcp"))
            for payload in (inventory_payload, sales_result, prices_result)
        }
        if len(source_names) != 1:
            raise AgentDataError("MCP tools returned inconsistent data sources")
        source_name = source_names.pop()
        for key in RAW_OPERATIONAL_INPUT_KEYS:
            enriched.pop(key, None)
        enriched["inventory"] = inventory
        enriched["sales_summary"] = sales_summary
        enriched["operational_analysis"] = operational_analysis
        enriched["operational_data"] = {
            "transport": "mcp",
            "source": source_name,
            "store_id": store_id,
            "business_date": business_date.isoformat(),
            "inventory_as_of": inventory_payload.get(
                "as_of", inventory_payload.get("as_of_date", business_date.isoformat())
            ),
            "inventory_total_count": len(normalized_all_inventory),
            "inventory_selected_count": len(normalized_inventory),
            "sales_window": {
                "start_date": window_start.isoformat(),
                "end_date": sales_end.isoformat(),
                "days": self.sales_window_days,
            },
            "sales_record_count": len(sales_rows),
            "sales_retention": "aggregated_only",
            "price_as_of": prices_result.get(
                "as_of", prices_result.get("as_of_date", business_date.isoformat())
            ),
            "currency": price_currency,
            "fetched_at": self._utc_now(),
        }

        reconcile_done = self._event(
            kind="step",
            event_id="reconcile",
            state="completed",
            label="校验并归一化经营证据",
            detail=(
                f"识别 {operational_analysis['expiring_count']} 个临期 SKU、"
                f"{operational_analysis['high_stock_count']} 个高库存 SKU"
            ),
        )
        trace.append(reconcile_done)
        enriched["operational_data"]["agent_trace"] = trace
        yield "event", reconcile_done
        yield "result", {"input_data": enriched, "trace": trace}

    @staticmethod
    def _validate_scope(
        input_data: dict[str, Any], *, require_mcp_scope: bool
    ) -> tuple[str, str, date | None]:
        store_info = input_data.get("store_info") or {}
        store_id = str(store_info.get("store_id") or "").strip()
        if not store_id and not require_mcp_scope:
            store_id = str(store_info.get("store_name") or "default-store").strip()
        date_value = str(store_info.get("date") or "").strip()
        if not store_id:
            raise AgentDataError("MCP 模式需要稳定的 store_info.store_id")
        if not date_value:
            raise AgentDataError("缺少业务日期 store_info.date")
        if not require_mcp_scope:
            try:
                return store_id, date_value, date.fromisoformat(date_value)
            except ValueError:
                return store_id, date_value, None
        try:
            business_date = date.fromisoformat(date_value)
        except ValueError as exc:
            raise AgentDataError("MCP 模式要求 YYYY-MM-DD 业务日期") from exc
        return store_id, date_value, business_date

    @staticmethod
    def _extract_rows(payload: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                if any(not isinstance(row, dict) for row in value):
                    raise AgentDataError("MCP result contains a malformed row")
                return [dict(row) for row in value]
        return []

    @staticmethod
    def _validate_payload_scope(
        payload: dict[str, Any],
        *,
        store_id: str,
        as_of_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> None:
        if str(payload.get("store_id", "")).strip() != store_id:
            raise AgentDataError("MCP result store_id does not match request scope")
        source = str(payload.get("source", "")).strip()
        if not SAFE_SOURCE_PATTERN.fullmatch(source):
            raise AgentDataError(
                "MCP result source must be a short opaque identifier"
            )
        payload["source"] = source
        if as_of_date is not None:
            returned_date = str(
                payload.get("as_of_date", payload.get("as_of", ""))
            ).strip()
            if returned_date != as_of_date:
                raise AgentDataError("MCP result date does not match request scope")
        if start_date is not None or end_date is not None:
            window = payload.get("window")
            if not isinstance(window, dict):
                raise AgentDataError("MCP sales result is missing its date window")
            if str(window.get("start_date", "")).strip() != start_date:
                raise AgentDataError("MCP sales start date does not match request scope")
            if str(window.get("end_date", "")).strip() != end_date:
                raise AgentDataError("MCP sales end date does not match request scope")

    @staticmethod
    def _normalize_inventory(
        inventory_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for source_row in inventory_rows:
            row = {
                "product_id": source_row.get("product_id", ""),
                "name": source_row.get(
                    "name", source_row.get("product_name", "")
                ),
                "category": source_row.get("category", ""),
                "stock": source_row.get(
                    "stock",
                    source_row.get("available_qty", source_row.get("on_hand_qty", 0)),
                ),
                "unit": source_row.get("unit", ""),
                "expiry_days": source_row.get("expiry_days"),
                "status": source_row.get(
                    "status", source_row.get("freshness_status", "正常")
                ),
                "stock_level": source_row.get("stock_level", "normal"),
            }
            optional_fields = (
                "on_hand_qty",
                "reserved_qty",
                "available_qty",
                "inbound_qty",
                "expiry_date",
                "snapshot_at",
                "price",
                "cost",
            )
            for field in optional_fields:
                if field in source_row:
                    row[field] = source_row[field]
            normalized.append(row)
        return normalized

    @staticmethod
    def _validate_inventory_rows(inventory: list[dict[str, Any]]) -> list[str]:
        product_ids: list[str] = []
        for row in inventory:
            product_id = str(row.get("product_id", "")).strip()
            name = str(row.get("name", "")).strip()
            if not product_id or not name:
                raise AgentDataError("MCP inventory rows require product_id and name")
            row["product_id"] = product_id
            row["name"] = name
            stock = OperationalDataAgent._required_number(row.get("stock"), "stock")
            if stock < 0:
                raise AgentDataError("MCP inventory contains a negative stock value")
            row["stock"] = OperationalDataAgent._json_number(stock)
            expiry_days = row.get("expiry_days")
            if expiry_days in (None, ""):
                raise AgentDataError("MCP inventory rows require expiry_days")
            row["expiry_days"] = OperationalDataAgent._json_number(
                OperationalDataAgent._required_number(expiry_days, "expiry days")
            )
            for field in (
                "on_hand_qty",
                "reserved_qty",
                "available_qty",
                "inbound_qty",
                "price",
                "cost",
            ):
                if field not in row or row[field] in (None, ""):
                    continue
                value = OperationalDataAgent._required_number(
                    row[field], field.replace("_", " ")
                )
                if value < 0:
                    raise AgentDataError(f"MCP inventory {field} cannot be negative")
                row[field] = OperationalDataAgent._json_number(value)
            product_ids.append(product_id)
        if len(product_ids) != len(set(product_ids)):
            raise AgentDataError("MCP inventory contains duplicate product_id values")
        return product_ids

    @staticmethod
    def _select_inventory_candidates(
        inventory: list[dict[str, Any]], limit: int
    ) -> list[dict[str, Any]]:
        def priority(row: dict[str, Any]) -> tuple[Any, ...]:
            expiry_days = OperationalDataAgent._number(row.get("expiry_days"))
            stock = OperationalDataAgent._number(row.get("stock", 0))
            return (
                row.get("status") != "临期" and expiry_days > 2,
                row.get("stock_level") != "high",
                expiry_days,
                -stock,
                str(row.get("product_id", "")),
            )

        return sorted(inventory, key=priority)[:limit]

    @staticmethod
    def _merge_prices(
        inventory_rows: list[dict[str, Any]], price_rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        price_map = {
            str(row.get("product_id", "")): row
            for row in price_rows
            if row.get("product_id")
        }
        merged: list[dict[str, Any]] = []
        for source_row in inventory_rows:
            row = dict(source_row)
            price = price_map.get(str(row.get("product_id", "")), {})
            if "current_price" in price:
                row["price"] = price["current_price"]
            elif "price" in price:
                row["price"] = price["price"]
            if "unit_cost" in price:
                row["cost"] = price["unit_cost"]
            elif "cost" in price:
                row["cost"] = price["cost"]
            for field in (
                "regular_price",
                "discount_pct",
                "gross_margin_pct",
                "promotion_label",
                "updated_at",
            ):
                if field in price:
                    target = "price_updated_at" if field == "updated_at" else field
                    row[target] = price[field]
            merged.append(row)
        return merged

    @staticmethod
    def _summarize_sales(rows: list[dict[str, Any]]) -> dict[str, Any]:
        by_product: dict[str, dict[str, float]] = {}
        total_units = 0.0
        total_revenue = 0.0
        for row in rows:
            product_id = str(row.get("product_id", "")).strip()
            if not product_id:
                continue
            units = OperationalDataAgent._number(
                row.get("units_sold", row.get("quantity", row.get("units", 0)))
            )
            revenue = OperationalDataAgent._number(
                row.get("revenue", row.get("net_sales", row.get("gross_sales", 0)))
            )
            current = by_product.setdefault(product_id, {"units_sold": 0.0, "revenue": 0.0})
            current["units_sold"] += units
            current["revenue"] += revenue
            total_units += units
            total_revenue += revenue
        return {
            "record_count": len(rows),
            "total_units": round(total_units, 2),
            "total_revenue": round(total_revenue, 2),
            "by_product": {
                product_id: {
                    "units_sold": round(values["units_sold"], 2),
                    "revenue": round(values["revenue"], 2),
                }
                for product_id, values in by_product.items()
            },
        }

    def _analyze_inventory(
        self, inventory: list[dict[str, Any]], sales_summary: dict[str, Any]
    ) -> dict[str, Any]:
        sales_by_product = sales_summary.get("by_product", {})
        priorities: list[dict[str, Any]] = []
        expiring_count = 0
        high_stock_count = 0
        for item in inventory:
            product_id = str(item.get("product_id", ""))
            expiry_days = self._number(item.get("expiry_days"))
            stock = self._number(item.get("stock", 0))
            units_sold = self._number(
                sales_by_product.get(product_id, {}).get("units_sold", 0)
            )
            daily_sales = units_sold / self.sales_window_days
            days_of_cover = stock / daily_sales if daily_sales > 0 else None
            score = 0.0
            reasons: list[str] = []
            if item.get("status") == "临期" or expiry_days <= 2:
                expiring_count += 1
                score += 100 - min(expiry_days, 10) * 5
                reasons.append("临期")
            if item.get("stock_level") == "high":
                high_stock_count += 1
                score += 35
                reasons.append("高库存")
            if days_of_cover is None and stock > 0:
                score += 25
                reasons.append("窗口内无销量")
            elif days_of_cover is not None and days_of_cover >= 14:
                score += 20
                reasons.append("周转偏慢")
            priorities.append(
                {
                    "product_id": product_id,
                    "name": item.get("name", ""),
                    "priority_score": round(score, 2),
                    "reasons": reasons,
                    "window_units_sold": round(units_sold, 2),
                    "estimated_days_of_cover": (
                        round(days_of_cover, 1) if days_of_cover is not None else None
                    ),
                }
            )
        priorities.sort(key=lambda row: row["priority_score"], reverse=True)
        return {
            "expiring_count": expiring_count,
            "high_stock_count": high_stock_count,
            "priority_products": priorities[:20],
        }

    def _fallback_operational_data(
        self,
        enriched: dict[str, Any],
        trace: list[dict[str, Any]],
        store_id: str,
        business_date_text: str,
        warning: str,
    ) -> dict[str, Any]:
        prior = enriched.get("operational_data")
        now = self._utc_now()
        if isinstance(prior, dict) and prior.get("transport") == "mcp":
            prior_source = str(prior.get("source", "")).strip()
            if not SAFE_SOURCE_PATTERN.fullmatch(prior_source):
                prior_source = "saved_mcp_snapshot"
            preserved_keys = (
                "inventory_as_of",
                "inventory_total_count",
                "inventory_selected_count",
                "sales_window",
                "sales_record_count",
                "sales_retention",
                "price_as_of",
                "currency",
                "fetched_at",
            )
            metadata = {
                key: prior[key] for key in preserved_keys if key in prior
            }
            metadata.update(
                {
                    "transport": "saved_mcp_snapshot_fallback",
                    "source": prior_source,
                    "store_id": store_id,
                    "business_date": business_date_text,
                    "fallback_at": now,
                    "fallback_from": {
                        "transport": "mcp",
                        "source": prior_source,
                        "fetched_at": prior.get("fetched_at", ""),
                    },
                    "warning": warning + "；当前使用请求中保存的旧 MCP 快照",
                    "agent_trace": trace,
                }
            )
            return metadata
        return {
            "transport": "request_fallback",
            "source": "request_input_fallback",
            "store_id": store_id,
            "business_date": business_date_text,
            "fetched_at": now,
            "warning": warning,
            "agent_trace": trace,
        }

    @staticmethod
    def _validate_currency(payload: dict[str, Any], label: str) -> str:
        currency = str(payload.get("currency", "")).strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise AgentDataError(f"MCP {label} result requires an ISO currency code")
        payload["currency"] = currency
        return currency

    @staticmethod
    def _number(value: Any) -> float:
        try:
            number = float(value or 0)
        except (TypeError, ValueError):
            return 0.0
        return number if math.isfinite(number) else 0.0

    @staticmethod
    def _required_number(value: Any, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise AgentDataError(f"MCP {field_name} must be numeric") from exc
        if not math.isfinite(number):
            raise AgentDataError(f"MCP {field_name} must be finite")
        return number

    @staticmethod
    def _json_number(number: float) -> int | float:
        return int(number) if number.is_integer() else number

    @staticmethod
    def _event(
        *,
        kind: str,
        event_id: str,
        state: str,
        label: str,
        detail: str = "",
        parent_id: str | None = None,
        tool_name: str | None = None,
        source: str | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "kind": kind,
            "id": event_id,
            "state": state,
            "label": label,
        }
        if detail:
            event["detail"] = detail
        if parent_id:
            event["parent_id"] = parent_id
        if tool_name:
            event["tool_name"] = tool_name
        if source:
            event["source"] = source
        if duration_ms is not None:
            event["duration_ms"] = duration_ms
        return event

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        return max(0, round((perf_counter() - start) * 1000))

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
