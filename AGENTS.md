# AI 社区餐桌预测引擎：开发交接说明

用户使用说明见 [README.md](README.md)。本文件记录后续开发 agent 必须遵守的项目约束与验证方式。

## 运行与验证

- 当前 Windows 环境使用 `anaconda` 管理虚拟环境；不要假定裸 `python` 已安装项目依赖。
- 没有正式自动化测试套件。启动服务后检查 `/api/health` 和相关 API，并用浏览器验证涉及的真实页面流程。
- 涉及存储或删除的操作，应使用临时 SQLite 数据库或临时 `MemoryStore` 验证；不要为测试清除用户现有的 `memory/memory.db`。

## 架构边界

- `backend/main.py` 是 FastAPI 路由和页面交付层；业务存储逻辑放入 `backend/memory.py`，不要在路由中直接写 SQL。
- `backend/llm_engine.py` 编排 Memory 检索、提示词、流式 LLM、JSON 解析、菜谱 HTML 部署和当前方案保存。
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

## 路由与前端约束

- 固定路由必须置于 `/api/recommendations/{plan_id}` 之前，否则 `history` 会被当作 `plan_id`。当前 `/api/recommendations/history` 的 `GET` 和 `DELETE` 已在前。
- `GET /api/recommendations?store_id=...&date=...` 未命中时必须返回 `404`；主页以此判断是否自动恢复方案。
- 单方案响应需保留 `plan_id`、`store_id`、`plan_date`、`input_context`、`result`、`recipe_urls`、`raw_thinking`、`raw_output` 和决策字段。历史页、Dmall 页面和决策大屏依赖这些字段。
- 历史索引接口只返回摘要；完整方案通过 `plan_id` 单独读取，避免把大段生成文本放进列表请求。
- `frontend/index.html` 在数据加载完成后调用 `restoreRecommendationForDate`。更改数据加载流程时不得移除该恢复点。
- SSE 分片不保证逐 token 到达。保留 `createStreamRenderer` 的队列和 `requestAnimationFrame` 播放策略，完成后再解析 Markdown。
- 深度思考关闭时，Mock 和真实 LLM 都必须抑制 `thinking` 事件和面板。
- 页面使用内联 `onclick` 和全局函数，这是现有一致模式。动态写入模型或用户数据前必须做 HTML 转义。
- 二维码容器可能生成 canvas 和 image；现有 CSS 只显示最终 image，避免重复二维码。

## LLM 与部署注意事项

- 未设置 `LLM_API_KEY` 会进入 Mock 模式，适合流程验证，不代表真实模型输出稳定性。
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