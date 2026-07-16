#!/usr/bin/env python
"""
Memory 查看工具 —— 命令行直接查看 memory.db 内容

用法:
  python view_memory.py              # 列出所有样例
  python view_memory.py --reset      # 重置为初始状态（清空+注入种子）
  python view_memory.py --stats      # 仅显示统计信息
"""
import sys
import os
import json
import sqlite3
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "memory" / "memory.db"


def connect():
    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        print("   请先启动服务 (python run.py --seed) 来创建数据库")
        sys.exit(1)
    return sqlite3.connect(str(DB_PATH))


def show_stats():
    conn = connect()
    count = conn.execute("SELECT COUNT(*) FROM memory_cases").fetchone()[0]
    successful = conn.execute("SELECT COUNT(*) FROM memory_cases WHERE is_successful=1").fetchone()[0]
    print(f"📊 Memory 数据库: {DB_PATH}")
    print(f"   总样例数: {count}")
    print(f"   成功样例: {successful}")
    if count > 0:
        latest = conn.execute("SELECT timestamp FROM memory_cases ORDER BY id DESC LIMIT 1").fetchone()[0]
        print(f"   最新记录: {latest}")
    conn.close()


def show_all():
    conn = connect()
    rows = conn.execute(
        "SELECT id, timestamp, input_context, output, is_successful, tags "
        "FROM memory_cases ORDER BY id DESC"
    ).fetchall()
    conn.close()

    if not rows:
        print("📭 Memory 为空")
        return

    print(f"📋 Memory 样例列表 (共 {len(rows)} 条)\n")
    print("=" * 70)

    for row in rows:
        case_id, ts, inp_json, out_json, ok, tags = row
        inp = json.loads(inp_json)
        out = json.loads(out_json)
        tags_list = tags.split(",") if tags else []

        weather = inp.get("weather", {}).get("description", "")
        community = inp.get("community", {}).get("type", "")
        festival = inp.get("festival", {}).get("name", "")
        expiring = [item.get("name", "") for item in inp.get("inventory", []) if item.get("status") == "临期"]

        menus = out.get("menus", [])
        menu_names = "、".join(m.get("dish", "") for m in menus)
        ve = out.get("value_estimate", {})

        print(f"\n  #{case_id}  {'✅' if ok else '❌'}  {out.get('scenario_tag', '未标记')}")
        print(f"  时间: {ts}")
        print(f"  天气: {weather}")
        print(f"  社区: {community}")
        if festival:
            print(f"  节日: {festival}")
        if expiring:
            print(f"  临期商品: {', '.join(expiring)}")
        print(f"  推荐菜单: {menu_names}")
        if ve:
            loss_reduction = ve.get("loss_reduction", "")
            ticket_lift = ve.get("ticket_lift", "")
            if isinstance(loss_reduction, dict):
                loss_reduction = f"{loss_reduction.get('value', '')}{loss_reduction.get('unit', '')}"
            if isinstance(ticket_lift, dict):
                ticket_lift = f"{ticket_lift.get('value', '')}{ticket_lift.get('unit', '')}"
            print(f"  效果: 减损{loss_reduction} | 客单价{ticket_lift}")
        if tags_list:
            print(f"  标签: {', '.join(tags_list)}")
        print("-" * 70)


def reset():
    conn = connect()
    deleted = conn.execute("SELECT COUNT(*) FROM memory_cases").fetchone()[0]
    conn.execute("DELETE FROM memory_cases")
    conn.commit()
    conn.close()
    print(f"🗑️  已清空 {deleted} 条样例")

    # 重新注入种子
    from backend.memory import MemoryStore
    from backend.config import config
    config.ensure_dirs()
    store = MemoryStore(config.MEMORY_DB)

    seeds = [
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
                "value_estimate": {
                    "loss_reduction": {"value": 2840, "unit": "元", "baseline": 4100, "reason": "按临期库存成本与雨天晚餐预计消化量估算。"},
                    "ticket_lift": {"value": 18, "unit": "%", "baseline": 0, "reason": "三菜套餐叠加熟食加购，理想化估算客单价提升。"},
                    "cross_sell_rate": {"value": 3.8, "unit": "件/单", "baseline": 1.1, "reason": "主菜、配菜、汤品与熟食形成多品类联动。"},
                    "member_open_rate": {"value": 27, "unit": "%", "baseline": 16, "reason": "雨天晚餐场景在下班前定时触达家庭客群。"},
                },
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
                "value_estimate": {
                    "loss_reduction": {"value": 3120, "unit": "元", "baseline": 4500, "reason": "按高温易损库存成本与午间预计消化量估算。"},
                    "ticket_lift": {"value": 22, "unit": "%", "baseline": 0, "reason": "清凉套餐组合较单品购买形成更高客单。"},
                    "cross_sell_rate": {"value": 3.6, "unit": "件/单", "baseline": 1.2, "reason": "凉菜、汤品和饮品形成午间连带组合。"},
                    "member_open_rate": {"value": 31, "unit": "%", "baseline": 18, "reason": "高温午间主题与白领客群需求匹配度较高。"},
                },
            },
        },
    ]

    for case in seeds:
        store.store_case(
            input_context=case["input"],
            output=case["output"],
            metrics=case["output"].get("value_estimate"),
            is_successful=True,
            tags=[case["output"]["scenario_tag"]],
        )

    print(f"🌱 已注入 {len(seeds)} 条种子样例")
    print(f"✅ Memory 重置完成，当前共 {store.count()} 条")


def main():
    if "--reset" in sys.argv:
        reset()
    elif "--stats" in sys.argv:
        show_stats()
    else:
        show_stats()
        print()
        show_all()


if __name__ == "__main__":
    main()
