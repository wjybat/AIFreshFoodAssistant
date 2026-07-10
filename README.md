# AI 社区餐桌预测引擎 · 即时烹饪场景经营平台

> **一句话定位**：让超市不再被动清库存，用 LLM 把今天卖不动的商品，变成顾客今晚想买的一顿饭。

基于 LLM + Harness 框架的 Agentic Workflow（生成式推荐），部署于云端，通过 Memory 持续自学习优化。

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
│   └── index.html              # 前端交互界面（数据可视化+流式思维链+结果展示+二维码）
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
├── .env.example                # 环境变量模板
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
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 LLM API Key
# 支持 OpenAI / 智谱GLM / 任何 OpenAI 兼容接口
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

浏览器打开 `http://localhost:8080`

---

## 🎯 使用流程

1. **选择数据**：在左侧面板选择测试数据文件（JSON/CSV）
2. **查看数据**：数据可视化展示（库存/临期/天气/社区/客流）
3. **生成方案**：点击「生成今日方案」→ LLM Agentic Workflow 启动
4. **查看推理**：实时流式展示 LLM 思维链（Memory检索→Prompt组装→LLM推理）
5. **查看结果**：推荐菜单卡片 + 场景包 + 触达矩阵 + 价值预估
6. **查看菜谱**：点击菜单卡片 → 弹出完整菜谱（食材分量+步骤+贴士）
7. **扫码分享**：菜谱弹窗底部二维码 → 手机扫码打开云端菜谱页

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
输入数据 → Memory检索(相似历史样例) → Prompt组装(System+Skills+Few-Shot+User)
    → LLM流式推理(生成式推荐) → 输出解析(思维链+JSON)
    → 菜谱页面部署(云端) → 二维码生成 → Memory存储 → 多端下发
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

---

## 🔧 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 前端主页 |
| GET | `/api/health` | 健康检查（LLM状态/Memory数量） |
| GET | `/api/data/files` | 列出可用数据文件 |
| GET | `/api/data/{filename}` | 加载数据文件 |
| POST | `/api/upload` | 上传数据文件 |
| POST | `/api/generate` | SSE流式生成（LLM Agentic Workflow） |
| GET | `/api/memory/cases` | 列出Memory历史样例 |
| POST | `/api/memory/seed` | 注入种子样例 |
| GET | `/recipes/{filename}` | 已部署的菜谱页面 |

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

_路演成功的关键不是讲技术，而是讲"画面"——让观众看到"卖不动的青椒变成今晚的青椒肉丝"那一刻的"啊哈"瞬间。_
