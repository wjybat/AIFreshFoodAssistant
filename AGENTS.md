# AI 社区餐桌预测引擎：开发交接说明

用户使用说明见 [README.md](README.md)。本文件记录后续开发 agent 必须遵守的项目约束与验证方式。

## 运行与验证

- 当前 Windows 环境使用 `anaconda` 管理虚拟环境；不要假定裸 `python` 已安装项目依赖。
- 没有正式自动化测试套件。启动服务后检查 `/api/health` 和相关 API，并用浏览器验证涉及的真实页面流程。
- 涉及存储或删除的操作，应使用临时 SQLite 数据库或临时 `MemoryStore` 验证；不要为测试清除用户现有的 `memory/memory.db`。

## 架构边界

- `backend/main.py` 是 FastAPI 路由和页面交付层；业务存储逻辑放入 `backend/memory.py`，不要在路由中直接写 SQL。
- `backend/llm_engine.py` 编排 Memory 检索、提示词、流式 LLM、JSON 解析、菜谱 HTML 部署和当前方案保存。
- `backend/agent.py` 负责有界多步经营数据流程；`backend/mcp_client.py` 只实现受限 MCP 客户端。共享开发数据库、种子数据和 MCP 服务端代码固定放在 `.tmp/AIFreshFoodAssistant-mcp-dev/`，不得混入应用运行包；该目录中的源码、锁文件和确定性 SQLite fixture 需要纳入版本控制，本地 `.venv` 与缓存除外。
- `backend/skills.py` 定义模型输出契约。变更输出字段时，同步修改提示词、Mock 结果、解析逻辑和前端渲染。
- `frontend/` 是独立的原生 HTML/CSS/JavaScript 页面，不是 React 项目。页面通过 `fetch` 调用 API，Dmall 与决策大屏从 `plan_id` 查询参数读取方案。

## 数据不变量

`memory/memory.db` 有两张语义不同的表：

| 表 | 约束 |
|------|------|
| `pending_recommendations` | 面向 UI 的当前方案；一个 `(store_id, plan_date)` 只能有一个当前方案 |
| `memory_cases` | 面向 LLM Few-Shot/相似检索的已决策成功或失败案例 |

- 生成只写 `pending_recommendations`；负责人在 `POST /api/recommendations/{plan_id}/decision` 接受或拒绝后，才写入 `memory_cases`。
- 生成同一门店、同一日期时，`create_pending_recommendation` 必须复用既有 `plan_id`、覆盖内容，并重置 `decision`、`decided_at`、`memory_case_id`。不要改为追加当前记录。
- 已经写入的 `memory_cases` 不会因重新生成而自动删除，即使方案的 `memory_case_id` 已重置。
- `store_info.date` 是方案归档和自动恢复的必填业务键。缺失日期时生成会抛出 `ValueError`。
- CSV 默认使用“CSV导入门店”和“今日”，未经上下文增强的连续 CSV 生成会覆盖同一份方案。
- 启动迁移只从旧 `input_context.store_info` 无损回填门店和日期；不要对缺失日期的记录做猜测性迁移。
- `DELETE /api/recommendations/history` 只允许清空 `pending_recommendations`，不得删除 `memory_cases` 或 `recipes/`。
- MCP 模式生成时，归一化后的库存、销售摘要、价格和 `operational_data` 必须写入方案的 `input_context`，保证方案可复现；`transport=mcp` 与服务端 `source` 标签都要保留，不得只保存上传文件中的旧库存或把开发假数据表述为生产数据。
- `MCP_REQUIRED=true` 时，工具发现、库存、销售或价格任一步失败都必须在保存方案前终止，禁止静默回退。
- MCP 严格模式必须规范化商品 ID 和数值，逐行校验 `sales_date`，要求销售/价格同为 `CNY`，并将 `source` 限制为短不透明标识；畸形行、跨作用域商品、缺失价格或混合币种均不得落库。
- MCP 成功后不得保留请求中旧的逐日销售、价格快照等原始经营字段；可回退模式若使用旧 MCP 快照，必须保留原来源/获取时间并明确标记快照回退。

## 路由与前端约束

- 固定路由必须置于 `/api/recommendations/{plan_id}` 之前，否则 `history` 会被当作 `plan_id`。当前 `/api/recommendations/history` 的 `GET` 和 `DELETE` 已在前。
- `GET /api/recommendations?store_id=...&date=...` 未命中时必须返回 `404`；主页以此判断是否自动恢复方案。
- 单方案响应需保留 `plan_id`、`store_id`、`plan_date`、`input_context`、`result`、`recipe_urls`、`raw_thinking`、`raw_output` 和决策字段。历史页、Dmall 页面和决策大屏依赖这些字段。
- 历史索引接口只返回摘要；完整方案通过 `plan_id` 单独读取，避免把大段生成文本放进列表请求。
- `frontend/index.html` 在数据加载完成后调用 `restoreRecommendationForDate`。更改数据加载流程时不得移除该恢复点。
- 恢复历史方案只影响当前展示，不得覆盖用于重新生成的已加载请求数据；否则会把旧 MCP 快照误当作新输入。
- SSE 分片不保证逐 token 到达。保留 `createStreamRenderer` 的队列和 `requestAnimationFrame` 播放策略，完成后再解析 Markdown。
- SSE 流必须以 `done` 或 `error` 结束；无终态直接 EOF 时前端要完成渲染队列并显示错误。
- 深度思考关闭时，Mock 和真实 LLM 都必须抑制 `thinking` 事件和面板。
- `agent` SSE 事件只承载高层步骤和工具调用摘要，不是思维链；它必须独立于 `thinking` 开关，且不得混入 `thinkingText` 或 `outputText`。
- Agent 事件的稳定字段为 `kind`、`id`、`state`、`label`，可选 `parent_id`、`detail`、`tool_name`、`source`、`duration_ms`；不要向浏览器发送 SQL、连接串、凭据或整批工具结果。
- 页面使用内联 `onclick` 和全局函数，这是现有一致模式。动态写入模型或用户数据前必须做 HTML 转义。
- 二维码容器可能生成 canvas 和 image；现有 CSS 只显示最终 image，避免重复二维码。

## LLM 与部署注意事项

- 未设置 `LLM_API_KEY` 会进入 Mock 模式，适合流程验证，不代表真实模型输出稳定性。
- GLM-5.2 的 Chat Completions 思考开关是 `extra_body.thinking.type=enabled|disabled`，不是 `enable_thinking`；关闭深度思考时必须对智谱端点显式发送 `disabled`，因为该模型默认开启 Thinking。
- `LLM_PROVIDER=auto` 只按官方域名识别供应商，不得仅凭 `glm-*` 模型名向第三方网关发送智谱扩展字段；OpenCode 使用 `opencode` 协议，GLM-5.2 开启思考时只发送顶层 `reasoning_effort=high|max`，不得发送智谱 `thinking` 或旧 `enable_thinking` 扩展。其他第三方兼容网关默认使用 `generic`。
- MCP Python SDK 使用稳定 `v1.x`，依赖范围保持 `mcp>=1.27,<2`；新服务优先使用 Streamable HTTP，不要改回旧 SSE transport。
- 项目只允许调用 `get_inventory`、`get_sales_history`、`get_current_prices` 三个只读工具。门店 ID 必须来自请求作用域，销售窗口和商品数量必须有上限。
- 开发假数据库与 MCP 服务位于根目录下的 `.tmp\AIFreshFoodAssistant-mcp-dev`；它使用独立环境，不得访问本项目的 `memory/memory.db`。必要 fixture 文件需要提交供其他开发者使用，但不得打入主应用发布包。
- OpenAI 兼容推理内容使用 `delta.reasoning_content`，正文使用 `delta.content`；SSE 事件名不可随意改变。
- 模型结果至少要能提供 `scenario_tag`、`menus`、`value_estimate`、`staff_instructions`、`display_plan` 和 `cross_sell`，否则下游页面会出现缺失内容。
- 菜谱链接以 `SERVER_URL` 为根。移动设备无法访问 `localhost`，演示或部署时设置局域网 IP 或公网域名。

## 变更前检查

1. 判断改动属于数据加载、持久化、生成、API 或对应前端页面，避免跨层重复实现。
2. 方案保存改动必须验证同店同日覆盖、不同日期隔离、历史索引和主页面自动恢复。
3. 决策改动必须验证同一方案重复提交不会重复写入 `memory_cases`。
4. 路由改动必须验证固定路径未被动态 `{plan_id}` 路由吞掉。
5. UI 改动需要检查桌面和窄视图，确认文本、列表和操作按钮没有重叠。
6. 保留用户已有数据库、生成菜谱和未提交代码，除非用户明确要求清除或重置。
7. Agent/MCP 改动还需验证工具白名单、严格失败不落库、关闭深度思考无 `thinking` 事件，以及 Agent 轨迹在桌面和窄视图均可读。
