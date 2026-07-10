"""
数据加载模块 —— 支持 JSON 和 CSV 格式的输入数据

输入数据格式定义:
  JSON: 完整场景数据（门店信息+天气+社区+库存+节日+通勤等）
  CSV:  仅库存数据（可与其他外部数据组合）

JSON Schema:
{
  "store_info": {"store_id": "...", "store_name": "...", "date": "..."},
  "weather": {"condition": "rain|sunny|cloudy|snow|hot", "temperature": 18, "description": "..."},
  "community": {"type": "...", "radius": "3km", "peak_hour": "18:00", "office_buildings": 2, "school_ratio": "35%"},
  "foot_traffic": {"estimated": 850, "peak_periods": ["18:00-20:00"]},
  "festival": {"name": null|"...", "description": "..."},
  "commute": {"school_dismissal": "16:30", "office_offwork": "18:00"},
  "inventory": [
    {"product_id":"...","name":"...","category":"蔬菜|肉类|豆制品|调料|主食|熟食","stock":50,"unit":"kg","expiry_days":1,"status":"临期|正常","stock_level":"high|normal|low","price":8.5,"cost":5.0}
  ],
  "historical_hot_dishes": ["..."]
}
"""
import json
import csv
from pathlib import Path
from typing import Optional


REQUIRED_FIELDS = ["store_info", "weather", "community", "inventory"]


def load_json(file_path: str | Path) -> dict:
    """加载 JSON 格式的完整场景数据"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    validate(data)
    return data


def load_csv(file_path: str | Path, context: Optional[dict] = None) -> dict:
    """
    加载 CSV 格式的库存数据，可附加上下文信息
    CSV 列: product_id,name,category,stock,unit,expiry_days,status,stock_level,price,cost
    """
    inventory = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inventory.append({
                "product_id": row.get("product_id", ""),
                "name": row["name"],
                "category": row.get("category", ""),
                "stock": float(row.get("stock", 0)),
                "unit": row.get("unit", "kg"),
                "expiry_days": int(row.get("expiry_days", 0)) if row.get("expiry_days") else None,
                "status": row.get("status", "正常"),
                "stock_level": row.get("stock_level", "normal"),
                "price": float(row.get("price", 0)),
                "cost": float(row.get("cost", 0)),
            })

    # 如果提供了上下文（天气/社区等），合并；否则使用默认值
    base = context or {}
    data = {
        "store_info": base.get("store_info", {"store_name": "CSV导入门店", "date": "今日"}),
        "weather": base.get("weather", {"condition": "cloudy", "temperature": 25, "description": "多云 25°C"}),
        "community": base.get("community", {"type": "综合客群", "radius": "3km", "peak_hour": "18:00"}),
        "foot_traffic": base.get("foot_traffic", {"estimated": 800}),
        "festival": base.get("festival", {"name": None, "description": "无"}),
        "commute": base.get("commute", {"school_dismissal": "16:30", "office_offwork": "18:00"}),
        "inventory": inventory,
        "historical_hot_dishes": base.get("historical_hot_dishes", []),
    }
    return data


def validate(data: dict):
    """校验数据格式完整性"""
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"缺少必填字段: {field}")

    if "inventory" in data:
        if not isinstance(data["inventory"], list):
            errors.append("inventory 必须是数组")
        elif len(data["inventory"]) == 0:
            errors.append("inventory 不能为空")
        else:
            for i, item in enumerate(data["inventory"]):
                if "name" not in item:
                    errors.append(f"inventory[{i}] 缺少 name 字段")

    if errors:
        raise ValueError("数据校验失败: " + "; ".join(errors))


def format_for_display(data: dict) -> dict:
    """格式化数据供前端可视化展示"""
    inventory = data.get("inventory", [])
    expiring = [item for item in inventory if item.get("status") == "临期"]
    high_stock = [item for item in inventory if item.get("stock_level") == "high"]

    return {
        "store_info": data.get("store_info", {}),
        "weather": data.get("weather", {}),
        "community": data.get("community", {}),
        "foot_traffic": data.get("foot_traffic", {}),
        "festival": data.get("festival", {}),
        "commute": data.get("commute", {}),
        "inventory": inventory,
        "historical_hot_dishes": data.get("historical_hot_dishes", []),
        "summary": {
            "total_products": len(inventory),
            "expiring_count": len(expiring),
            "high_stock_count": len(high_stock),
            "expiring_products": [item["name"] for item in expiring],
            "high_stock_products": [item["name"] for item in high_stock],
        },
    }


def list_data_files(data_dir: Path) -> list:
    """列出数据目录下可用的数据文件"""
    files = []
    if not data_dir.exists():
        return files
    for f in sorted(data_dir.iterdir()):
        if f.suffix in (".json", ".csv"):
            files.append({
                "filename": f.name,
                "path": str(f.name),
                "type": f.suffix[1:],
                "size": f.stat().st_size,
            })
    return files
