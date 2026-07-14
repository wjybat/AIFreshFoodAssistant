# AI 社区餐桌预测引擎 · 即时烹饪场景经营平台

> **一句话定位**：让超市不再被动清库存，用 LLM 把今天卖不动的商品，变成顾客今晚想买的一顿饭。

基于 FastAPI、OpenAI 兼容 LLM 和 SQLite 的 Agentic Workflow（生成式推荐）。系统将当前方案按门店和业务日期保存，并在负责人决策后把结果作为 Memory 样例用于后续检索。

---

## 📁 项目结构

```
Idea1/
├── backend/                    # 后端（FastAPI + LLM Agentic Workflow）
│   ├── config.py               # 配置管理（LLM API / 服务器 / 路径）
│   ├── memory.py               # Memory 模块（SQLite 历史样例存储+相似检索）
│   ├── skills.py               # Skills 模块（领域知识提示词模板）
│   ├── llm_engine.py           # LLM 引擎（Memory检索→Prompt组装→LLM调用→输出解析→菜谱部署）
│   ├── data_loader.py          # 数据加载（JSON/CSV 格式）
│   └── main.py                 # FastAPI 服务（API端点 + 静态文件服务）
├── frontend/
│   ├── index.html              # 运营驾驶舱（数据、流式生成、方案恢复）
│   ├── dmall-member.html       # Dmall 会员 App 模拟推送页
│   ├── store-dashboard.html    # 门店负责人决策大屏
│   ├── recommendation-history.html # 历史推荐方案管理页
│   ├── marked.min.js
│   └── qrcode.min.js
├── data/                       # 测试数据
│   ├── test_store_s1_rainy.json    # 场景1：雨天晚餐
│   ├── test_store_s2_hot.json      # 场景2：高温清凉
│   ├── test_store_s3_weekend.json  # 场景3：周末家庭
│   ├── test_store_s4_winter.json   # 场景4：冬至节日
│   └── sample_inventory.csv        # CSV库存样例
├── recipes/                    # 自动生成：部署的菜谱页面
├── memory/                     # 自动生成：SQLite Memory数据库
├── spec/
│   └── 产品规格文档.md          # v2.0 完整产品规格
├── run.py                      # 启动脚本
├── requirements.txt            # Python依赖
├── AGENTS.md                   # 后续开发 agent 的交接说明
└── README.md                   # 本文件
```

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv .venv

# 激活（Windows）
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 LLM API

```bash
# 在项目根目录创建 .env，填入 LLM API Key
# 支持 OpenAI、智谱 GLM 及任何 OpenAI 兼容接口
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
SERVER_PORT=8000
SERVER_URL=http://localhost:8000
```

> **不配置 API Key 也能运行**：系统自动进入 Mock 模式，使用基于输入数据的模拟生成（可用于测试调试）。配置 Key 后自动切换为真实 LLM 调用。

### 3. 启动服务

```bash
# 启动（首次可加 --seed 注入 Memory 种子样例）
python run.py --seed

# 或指定端口
python run.py --port 8080
```

### 4. 访问

浏览器打开 `http://localhost:8080`。

> 二维码使用 `SERVER_URL` 生成菜谱链接。手机扫码时不能使用 `localhost`，请改为局域网可达 IP 或公网域名，例如 `http://192.168.1.20:8000`。

---

## 🎯 使用流程

1. **选择数据**：在左侧面板选择 JSON/CSV 数据文件，查看库存、临期、天气、社区和客流。
2. **自动恢复**：系统以 `store_info.store_id`（无 ID 时使用门店名）和 `store_info.date` 查询；若该门店该日期已有方案，会自动恢复。
3. **生成或重新生成**：点击「生成今日方案」或「重新生成」。页面通过 SSE 流式展示状态、推理和生成结果。
4. **查看结果**：查看推荐菜单、场景包、价值预估和菜谱二维码；新方案先保存为待负责人确认状态。
5. **查看触达**：从全渠道触达矩阵进入 Dmall 会员 App 模拟推送页或门店负责人决策大屏。
6. **确认执行**：负责人接受或拒绝后，方案才会写入成功或失败的 Memory 样例；未决策方案不会写入 Memory。
7. **管理历史**：点击顶栏「历史方案」，按门店和日期切换已保存方案。每次只显示一份所选日期内容；「清空全部」只删除保存方案，不删除 Memory 样例。
8. **查看菜谱**：点击菜单卡片，弹出完整菜谱（食材分量、步骤、贴士）和二维码。

---

## 🏗️ 技术架构

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| 后端框架 | FastAPI | 异步API，支持SSE流式输出 |
| LLM调用 | OpenAI SDK | 流式调用，支持任何OpenAI兼容接口 |
| Memory | SQLite | 历史成功样例存储，多维度相似检索 |
| 前端 | HTML/CSS/JS | 原生JS，内嵌QR码生成器 |
| 数据格式 | JSON / CSV | 标准化输入，支持门店ERP对接 |
| 部署 | 云端服务器 | 菜谱页独立URL，任意设备扫码可访问 |

### LLM Agentic Workflow 流程

```
输入数据 → 按门店/日期恢复历史方案（如存在）
    → Memory 检索（相似已决策样例）→ Prompt 组装（System + Skills + Few-Shot + User）
    → LLM 流式推理 → 输出解析（推理文本 + JSON）→ 菜谱页面部署与二维码生成
    → 保存当前方案 → 多端下发 → 负责人接受/拒绝 → 写入 Memory 样例
```

---

## 📊 测试数据

| 文件 | 场景 | 天气 | 关键库存 | 社区画像 |
|------|------|------|----------|----------|
| test_store_s1_rainy.json | 雨天晚餐 | 小雨 18°C | 青椒(1天临期)/猪肉(高库存)/豆腐(2天) | 家庭客群 |
| test_store_s2_hot.json | 高温清凉 | 36°C | 黄瓜(1天临期)/冬瓜(高库存)/排骨(2天) | 白领+居民 |
| test_store_s3_weekend.json | 周末家庭 | 晴 25°C | 五花肉(高库存)/番茄(2天临期) | 家庭聚餐 |
| test_store_s4_winter.json | 冬至节日 | 冬至 2°C | 猪肉馅(2天临期)/白菜(1天临期)/面粉(高) | 北方社区 |
| sample_inventory.csv | CSV样例 | - | 青椒/猪肉/豆腐等8种商品 | - |

JSON 至少需要 `store_info`、`weather`、`community` 和非空 `inventory`。其中 `store_info.date` 是方案保存和自动恢复的必填业务键，建议使用稳定格式，如 `2026-07-15`。

CSV 只包含库存数据，系统会补充默认场景字段，默认门店名为“CSV导入门店”、日期为“今日”。连续使用默认 CSV 生成会覆盖同一门店同一天的方案；生产数据应补充真实门店 ID 和业务日期。

---

## 💾 方案与 Memory 存储

`memory/memory.db` 中有两类互相独立的数据：

| 表 | 作用 | 写入时机 |
|------|------|----------|
| `pending_recommendations` | 当前推荐方案、菜谱 URL、原始推理/输出和决策状态 | 每次生成；同一 `(store_id, plan_date)` 原地覆盖 |
| `memory_cases` | LLM 相似检索使用的成功/失败业务样例 | 负责人接受或拒绝方案时 |

重新生成同一门店、同一日期时，系统保留原 `plan_id`，更新方案内容，并重置 `decision`、`decided_at` 与 `memory_case_id`。此前已写入 `memory_cases` 的样例不会自动删除。

启动时会尝试从旧方案的 `input_context.store_info` 回填门店与日期键。缺少日期的旧记录保留在数据库中，但不会出现在历史方案管理页，也不会被自动恢复。

---

## 🔧 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 前端主页 |
| GET | `/recommendation-history` | 已保存推荐方案管理页 |
| GET | `/api/health` | 健康检查（LLM状态/Memory数量） |
| GET | `/api/data/files` | 列出可用数据文件 |
| GET | `/api/data/{filename}` | 加载数据文件 |
| POST | `/api/upload` | 上传数据文件 |
| POST | `/api/generate` | SSE流式生成（LLM Agentic Workflow） |
| GET | `/api/recommendations?store_id={id}&date={yyyy-mm-dd}` | 获取某门店某业务日期的当前方案；未命中返回 `404` |
| GET | `/api/recommendations/history` | 列出所有已保存方案的摘要，每个门店日期一条 |
| DELETE | `/api/recommendations/history` | 清空所有保存方案，不影响 `memory_cases` |
| GET | `/dmall-member?plan_id={id}` | Dmall 会员 App 模拟推送页 |
| GET | `/store-dashboard?plan_id={id}` | 门店负责人决策大屏 |
| GET | `/api/recommendations/{plan_id}` | 读取待确认方案 |
| POST | `/api/recommendations/{plan_id}/decision` | 接受或拒绝方案并写入 Memory |
| GET | `/api/memory/cases` | 列出Memory历史样例 |
| POST | `/api/memory/seed` | 注入种子样例 |
| POST | `/api/memory/reset?reseed=true` | 重置 Memory 样例，可选重注入种子数据 |
| GET | `/recipes/{filename}` | 已部署的菜谱页面 |

`POST /api/generate` 的 SSE 事件包括 `status`、`thinking`、`token`、`done` 和 `error`。前端流式展示依赖这些事件名与载荷格式。

---

## 📝 配置说明 (.env)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| LLM_API_KEY | LLM API密钥（不填=Mock模式） | 空 |
| LLM_BASE_URL | API地址 | https://api.openai.com/v1 |
| LLM_MODEL | 模型名 | gpt-4o |
| SERVER_HOST | 监听地址 | 0.0.0.0 |
| SERVER_PORT | 监听端口 | 8000 |
| SERVER_URL | 对外可访问URL（二维码用） | http://localhost:8000 |

> 部署到云端时，将 SERVER_URL 改为实际域名（如 `https://your-domain.com`），二维码将指向云端菜谱页。

---

## ✅ 修改后验证

项目目前没有独立测试套件。修改后至少执行：

```powershell
& '你的虚拟环境/python.exe' -m compileall backend
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/recommendations/history
```

若改动涉及方案保存或 UI，浏览器中还应验证：数据切换后的自动恢复、同日重新生成覆盖、历史方案页面切换、负责人决策，以及二维码外部可达性。后续开发约束见 [AGENTS.md](AGENTS.md)。

---

_路演成功的关键不是讲技术，而是讲"画面"——让观众看到"卖不动的青椒变成今晚的青椒肉丝"那一刻的"啊哈"瞬间。_
