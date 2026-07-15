# AIFreshFoodAssistant 开发数据 MCP

这是一个位于主项目 `.tmp/` 目录中的共享开发辅助服务。它使用确定性假数据模拟门店库存、销售历史和价格快照，并通过 MCP 暴露只读工具。源码、种子、依赖锁和确定性 SQLite fixture 随仓库共享，本地虚拟环境与缓存保持忽略。

> 所有返回均标记为 `development-fake-sqlite`，不得当作生产数据或真实经营数据使用。

## 隔离边界

- 服务目录：`<项目根目录>\.tmp\AIFreshFoodAssistant-mcp-dev`
- SQLite：`<项目根目录>\.tmp\AIFreshFoodAssistant-mcp-dev\data\fresh_food_dev.sqlite3`
- Python 环境：本目录下由 `uv` 创建的独立 `.venv`
- 主项目作为 MCP client 自行安装 `mcp>=1.27,<2`；外置服务使用本目录独立的 `.venv` 和依赖锁，两者不共享 Python 环境
- 本服务不会读取或修改主项目的 `memory/memory.db`
- MCP 查询连接使用 SQLite `mode=ro` 和 `PRAGMA query_only=ON`
- 不提供任意 SQL、写入、删除或更新工具
- HTTP 模式固定绑定 `127.0.0.1`，命令行不能改为公网地址

## 确定性数据

种子为 `20260715`，数据对齐主项目现有四个场景的门店日期、商品 ID、名称、库存、单位、价格和成本：

| 门店 | 库存/价格日期 | 商品 |
|---|---:|---:|
| `STORE_001` 阳光社区超市·城东店 | `2026-07-09` | `P001`–`P008` |
| `STORE_002` 阳光社区超市·CBD店 | `2026-07-12` | `P101`–`P108` |
| `STORE_003` 阳光社区超市·家庭店 | `2026-07-13` | `P201`–`P208` |
| `STORE_004` 阳光社区超市·北方店 | `2026-12-22` | `P301`–`P308` |

每个门店有库存日期之前 42 天的确定性日销售与损耗数据。临期商品带有开发用促销价场景。

## 安装、生成与验证

```powershell
Set-Location .\.tmp\AIFreshFoodAssistant-mcp-dev
uv sync
uv run python seed.py --force
uv run python smoke_test.py
```

依赖使用官方 Python MCP SDK 稳定 `v1.x`：`mcp[cli]>=1.27,<2`。`uv.lock` 会记录解析到的精确版本。

`smoke_test.py` 使用官方 SDK 的内存传输建立真实 MCP client/server session，列出工具并调用库存、销售和价格工具。

## MCP 工具契约

### `get_inventory(store_id, as_of_date)`

返回指定门店、指定日期的库存快照：

```json
{
  "source": "development-fake-sqlite",
  "store_id": "STORE_001",
  "as_of_date": "2026-07-09",
  "units": "per-row; see rows[].unit",
  "rows": []
}
```

### `get_sales_history(store_id, start_date, end_date, product_ids=null)`

返回包含起止日期的逐日销售、售价、销售额和损耗：

```json
{
  "source": "development-fake-sqlite",
  "store_id": "STORE_001",
  "window": {"start_date": "2026-07-02", "end_date": "2026-07-08"},
  "currency": "CNY",
  "units": "per-row; see rows[].unit",
  "rows": []
}
```

### `get_current_prices(store_id, as_of_date, product_ids=null)`

返回原价、现价、单位成本、折扣和毛利率：

```json
{
  "source": "development-fake-sqlite",
  "store_id": "STORE_001",
  "as_of_date": "2026-07-09",
  "currency": "CNY",
  "units": "prices are per rows[].unit",
  "rows": []
}
```

另有两个发现工具：

- `get_dataset_info()`：数据类型、门店日期和行数
- `list_stores()`：门店 ID、库存日期、销售窗口和商品数

推荐的多步调用顺序：

1. `get_dataset_info` / `list_stores`
2. `get_inventory`
3. `get_sales_history`
4. `get_current_prices`
5. 基于三类证据形成推荐，并明确指出数据是开发假数据

## stdio 启动（本地 agent 推荐）

```powershell
uv run python server.py --transport stdio
```

`stdio` 没有 URL。客户端配置示例：

```json
{
  "mcpServers": {
    "fresh-food-dev-data": {
      "command": "uv",
      "args": [
        "--directory",
        "D:\\tmp\\AIFreshFoodAssistant-mcp-dev",
        "run",
        "python",
        "server.py",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

## Streamable HTTP 启动（联调）

```powershell
uv run python server.py --transport streamable-http --port 8765
```

- 协议：MCP Streamable HTTP
- 绑定：`127.0.0.1:8765`
- MCP URL：`http://127.0.0.1:8765/mcp`

## 自定义数据库路径

```powershell
uv run python server.py --db D:\tmp\another.sqlite3 --transport stdio
$env:FRESH_FOOD_MCP_DB = "D:\tmp\another.sqlite3"
uv run python server.py --transport stdio
```

## 官方依据

- MCP Python SDK `v1.x`（稳定版本）及 FastMCP/Streamable HTTP 示例：<https://github.com/modelcontextprotocol/python-sdk/tree/v1.x>
- 官方内存传输测试方式：<https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/docs/testing.md>
