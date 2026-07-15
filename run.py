#!/usr/bin/env python
"""
AI 社区餐桌预测引擎 —— 启动脚本

用法:
  python run.py              # 启动服务器（默认 0.0.0.0:8000）
  python run.py --seed       # 启动前注入 Memory 种子样例
  python run.py --port 9000  # 指定端口

首次使用:
  1. 复制 .env.example 为 .env
  2. 填入 LLM_API_KEY（不填则自动进入 Mock 模式）
  3. python run.py
  4. 浏览器打开 http://localhost:8000
"""
import sys
import os
import argparse

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="AI 社区餐桌预测引擎")
    parser.add_argument("--host", default=None, help="服务器地址 (默认: .env 中的 SERVER_HOST)")
    parser.add_argument("--port", type=int, default=None, help="端口 (默认: .env 中的 SERVER_PORT)")
    parser.add_argument("--seed", action="store_true", help="启动前注入 Memory 种子样例")
    parser.add_argument("--reload", action="store_true", help="开发模式（热重载）")
    args = parser.parse_args()

    from backend.config import config
    config.ensure_dirs()

    host = args.host or config.HOST
    port = args.port or config.PORT

    # 根据实际端口更新 SERVER_URL（用于生成正确的二维码菜谱页 URL）
    if config.SERVER_URL.endswith(f":{config.PORT}"):
        config.SERVER_URL = config.SERVER_URL.replace(f":{config.PORT}", f":{port}")

    # 种子注入
    if args.seed:
        from backend.memory import MemoryStore
        store = MemoryStore(config.MEMORY_DB)
        if store.count() == 0:
            print("[启动] 注入 Memory 种子样例...")
            store.store_case(
                input_context={
                    "weather": {"condition": "rain", "description": "小雨 18°C"},
                    "community": {"type": "家庭客群为主", "peak_hour": "18:00"},
                    "festival": {"name": None},
                    "inventory": [{"name": "青椒"}, {"name": "猪肉"}, {"name": "豆腐"}],
                    "foot_traffic": {"estimated": 850},
                },
                output={
                    "scenario_tag": "雨天晚餐·家庭客群",
                    "menus": [{"dish": "青椒肉丝"}, {"dish": "麻婆豆腐"}, {"dish": "紫菜蛋花汤"}],
                    "value_estimate": {"loss_reduction": "¥2,840", "ticket_lift": "+18%"},
                },
                metrics={"loss_reduction": "¥2,840"},
                is_successful=True,
                tags=["雨天晚餐"],
            )
            store.store_case(
                input_context={
                    "weather": {"condition": "hot", "description": "36°C 高温"},
                    "community": {"type": "写字楼白领+居民混合", "peak_hour": "12:00"},
                    "festival": {"name": None},
                    "inventory": [{"name": "黄瓜"}, {"name": "冬瓜"}, {"name": "排骨"}],
                    "foot_traffic": {"estimated": 1120},
                },
                output={
                    "scenario_tag": "高温清凉·白领午间",
                    "menus": [{"dish": "凉拌黄瓜木耳"}, {"dish": "冬瓜排骨汤"}, {"dish": "绿豆汤"}],
                    "value_estimate": {"loss_reduction": "¥3,120", "ticket_lift": "+22%"},
                },
                metrics={"loss_reduction": "¥3,120"},
                is_successful=True,
                tags=["高温清凉"],
            )
            print(f"[启动] 种子样例注入完成，Memory 共 {store.count()} 条")
        else:
            print(f"[启动] Memory 已有 {store.count()} 条数据，跳过种子注入")

    # 打印启动信息
    print("=" * 60)
    print("  AI 社区餐桌预测引擎 v2.0")
    print("  LLM Agentic Workflow · 即时烹饪场景经营平台")
    print("=" * 60)
    print(f"  模式: {'Mock（未配置API Key）' if config.mock_mode else '真实LLM'}")
    print(f"  模型: {config.LLM_MODEL}")
    print(f"  LLM Provider: {config.resolved_llm_provider}")
    print(f"  多步 Agent: 已启用")
    print(
        f"  MCP 数据: {'已启用（必需）' if config.MCP_ENABLED and config.MCP_REQUIRED else '已启用（可回退）' if config.MCP_ENABLED else '未启用'}"
    )
    print(f"  地址: http://{host}:{port}")
    print(f"  数据: {config.DATA_DIR}")
    print(f"  菜谱: {config.RECIPES_DIR}")
    print(f"  Memory: {config.MEMORY_DB}")
    print("=" * 60)
    if config.mock_mode:
        print("  ⚠️  Mock 模式：请在 .env 中配置 LLM_API_KEY 以启用真实LLM调用")
        print("     Mock模式下将使用基于输入数据的模拟生成（可用于测试调试）")
    print()

    # 启动 uvicorn
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
