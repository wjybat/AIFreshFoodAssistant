"""
FastAPI 后端服务 —— API 端点与静态文件服务

API 端点:
  GET  /                    → 前端主页
    GET  /dmall-member        → Dmall 会员 App 模拟页
    GET  /store-dashboard     → 门店负责人决策大屏
  GET  /api/health          → 健康检查（含 LLM 状态）
  GET  /api/data/files      → 列出可用数据文件
  GET  /api/data/{filename} → 加载数据文件
  POST /api/generate        → SSE 流式生成（LLM Agentic Workflow）
    GET  /api/recommendations/{plan_id}          → 获取待确认方案
    POST /api/recommendations/{plan_id}/decision → 负责人接受或拒绝方案
  GET  /api/memory/cases    → 列出 Memory 中的历史样例
  GET  /recipes/{filename}  → 已部署的菜谱页面
"""
import json
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from .config import config
from .memory import MemoryStore
from .llm_engine import LLMEngine
from .data_loader import load_json, load_csv, list_data_files, format_for_display

# ==================== 初始化 ====================
config.ensure_dirs()
memory_store = MemoryStore(config.MEMORY_DB)
llm_engine = LLMEngine(memory_store)

app = FastAPI(
    title="AI 社区餐桌预测引擎",
    description="基于 LLM Agentic Workflow 的即时烹饪场景经营平台",
    version="2.1",
)

# 挂载静态目录
app.mount("/recipes", StaticFiles(directory=str(config.RECIPES_DIR)), name="recipes")
app.mount("/assets", StaticFiles(directory=str(config.FRONTEND_DIR)), name="assets")


# ==================== 数据模型 ====================
class GenerateRequest(BaseModel):
    data: dict
    enable_thinking: bool = True
    options: Optional[dict] = None


class RecommendationDecisionRequest(BaseModel):
    accepted: bool


# ==================== 路由 ====================

@app.get("/")
async def index():
    """前端主页"""
    index_path = config.FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "前端文件未找到")
    return FileResponse(str(index_path))


@app.get("/recipe.html")
async def recipe_template():
    """菜谱页模板"""
    recipe_path = config.FRONTEND_DIR / "recipe.html"
    if not recipe_path.exists():
        raise HTTPException(404, "菜谱页模板未找到")
    return FileResponse(str(recipe_path))


@app.get("/dmall-member")
async def dmall_member():
    """Dmall 会员 App 模拟页"""
    page_path = config.FRONTEND_DIR / "dmall-member.html"
    if not page_path.exists():
        raise HTTPException(404, "前端文件未找到")
    return FileResponse(str(page_path))


@app.get("/store-dashboard")
async def store_dashboard():
    """门店负责人决策大屏"""
    page_path = config.FRONTEND_DIR / "store-dashboard.html"
    if not page_path.exists():
        raise HTTPException(404, "前端文件未找到")
    return FileResponse(str(page_path))


@app.get("/recommendation-history")
async def recommendation_history():
    """历史推荐方案管理页"""
    page_path = config.FRONTEND_DIR / "recommendation-history.html"
    if not page_path.exists():
        raise HTTPException(404, "前端文件未找到")
    return FileResponse(str(page_path))


@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "llm_configured": not config.mock_mode,
        "mock_mode": config.mock_mode,
        "llm_model": config.LLM_MODEL,
        "llm_base_url": config.LLM_BASE_URL,
        "llm_provider": config.resolved_llm_provider,
        "agent_enabled": True,
        "mcp_enabled": config.MCP_ENABLED,
        "mcp_required": config.MCP_REQUIRED,
        "memory_count": memory_store.count(),
        "server_url": config.SERVER_URL,
    }


@app.get("/api/data/files")
async def get_data_files():
    """列出可用数据文件"""
    files = list_data_files(config.DATA_DIR)
    return {"files": files}


@app.get("/api/data/{filename}")
async def get_data(filename: str):
    """加载指定数据文件"""
    file_path = config.DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, f"文件不存在: {filename}")

    try:
        if file_path.suffix == ".json":
            data = load_json(file_path)
        elif file_path.suffix == ".csv":
            data = load_csv(file_path)
        else:
            raise HTTPException(400, f"不支持的文件格式: {file_path.suffix}")

        return {"data": data, "display": format_for_display(data)}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"加载失败: {str(e)}")


@app.post("/api/upload")
async def upload_data(file: UploadFile = File(...)):
    """上传数据文件"""
    content = await file.read()
    filename = file.filename

    # 保存到 data 目录
    save_path = config.DATA_DIR / filename
    save_path.write_bytes(content)

    try:
        if filename.endswith(".json"):
            data = load_json(save_path)
        elif filename.endswith(".csv"):
            data = load_csv(save_path)
        else:
            raise HTTPException(400, "仅支持 .json 和 .csv 文件")

        return {"data": data, "display": format_for_display(data)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    """
    SSE 流式生成 —— LLM Agentic Workflow

    返回 text/event-stream，前端通过 EventSource 接收
    """
    async def event_stream():
        async for event in llm_engine.generate(req.data, enable_thinking=req.enable_thinking):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/recommendations/history")
async def get_recommendation_history():
    """列出按门店和业务日期保存的推荐方案。"""
    recommendations = memory_store.list_recommendation_history()
    return {
        "recommendations": recommendations,
        "total": len(recommendations),
    }


@app.delete("/api/recommendations/history")
async def clear_recommendation_history():
    """清空全部已保存推荐方案，不影响 Memory 历史样例。"""
    deleted = memory_store.clear_recommendation_history()
    return {
        "message": f"已清空 {deleted} 条保存的推荐方案",
        "deleted": deleted,
    }


@app.get("/api/recommendations/{plan_id}")
async def get_recommendation(plan_id: str):
    """获取指定的待确认推荐方案。"""
    recommendation = memory_store.get_recommendation(plan_id)
    if recommendation is None:
        raise HTTPException(404, "推荐方案不存在或已被清理")
    return recommendation


@app.get("/api/recommendations")
async def get_recommendation_for_date(store_id: str, date: str):
    """获取指定门店业务日期对应的当前推荐方案。"""
    recommendation = memory_store.get_recommendation_for_date(store_id, date)
    if recommendation is None:
        raise HTTPException(404, "该日期尚无生成方案")
    return recommendation


@app.post("/api/recommendations/{plan_id}/decision")
async def decide_recommendation(plan_id: str, req: RecommendationDecisionRequest):
    """确认方案并将结果作为成功或失败样例写入 Memory。"""
    decision = memory_store.decide_recommendation(plan_id, req.accepted)
    if decision is None:
        raise HTTPException(404, "推荐方案不存在或已被清理")
    return {
        **decision,
        "memory_count": memory_store.count(),
    }


@app.get("/api/memory/cases")
async def get_memory_cases(limit: int = 50):
    """列出 Memory 中的历史样例"""
    cases = memory_store.list_all_cases(limit)
    return {
        "cases": cases,
        "total": memory_store.count(),
    }


@app.post("/api/memory/seed")
async def seed_memory():
    """用预置样例初始化 Memory（仅首次使用）"""
    if memory_store.count() > 0:
        return {"message": "Memory 已有数据，跳过种子注入", "count": memory_store.count()}

    _seed_memory()
    return {"message": "种子样例注入完成", "count": memory_store.count()}


@app.post("/api/memory/reset")
async def reset_memory(reseed: bool = True):
    """
    重置 Memory 到初始状态
    - 清空所有历史样例
    - reseed=true 时重新注入种子样例（默认）
    """
    deleted = memory_store.reset()
    reseeded = 0
    if reseed:
        _seed_memory()
        reseeded = memory_store.count()
    return {
        "message": f"已清空 {deleted} 条样例" + (f"，重新注入 {reseeded} 条种子样例" if reseed else ""),
        "deleted": deleted,
        "reseeded": reseeded,
        "current_count": memory_store.count(),
    }


def _seed_memory():
    """注入预置种子样例（内部函数，供 seed 和 reset 共用）"""
    seed_cases = [
        {
            "input": {
                "weather": {"condition": "rain", "description": "小雨 18°C"},
                "community": {"type": "家庭客群为主", "peak_hour": "18:00"},
                "festival": {"name": None},
                "inventory": [{"name": "青椒"}, {"name": "猪肉"}, {"name": "豆腐"}],
                "foot_traffic": {"estimated": 850},
            },
            "output": {
                "scenario_tag": "雨天晚餐·家庭客群",
                "menus": [{"dish": "青椒肉丝"}, {"dish": "麻婆豆腐"}, {"dish": "紫菜蛋花汤"}],
                "value_estimate": {"loss_reduction": "¥2,840", "ticket_lift": "+18%"},
            },
        },
        {
            "input": {
                "weather": {"condition": "hot", "description": "36°C 高温"},
                "community": {"type": "写字楼白领+居民混合", "peak_hour": "12:00"},
                "festival": {"name": None},
                "inventory": [{"name": "黄瓜"}, {"name": "冬瓜"}, {"name": "排骨"}],
                "foot_traffic": {"estimated": 1120},
            },
            "output": {
                "scenario_tag": "高温清凉·白领午间",
                "menus": [{"dish": "凉拌黄瓜木耳"}, {"dish": "冬瓜排骨汤"}, {"dish": "绿豆汤"}],
                "value_estimate": {"loss_reduction": "¥3,120", "ticket_lift": "+22%"},
            },
        },
    ]

    for case in seed_cases:
        memory_store.store_case(
            input_context=case["input"],
            output=case["output"],
            metrics=case["output"].get("value_estimate"),
            is_successful=True,
            tags=[case["output"]["scenario_tag"]],
        )


# ==================== 启动入口 ====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
    )
