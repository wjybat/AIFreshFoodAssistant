"""
Memory 模块 —— 基于 SQLite 的历史成功样例存储与检索

存储结构:
  memory_cases 表:
    - id: 自增主键
    - timestamp: 记录时间
    - input_context: 输入上下文 (JSON: 天气/社区/库存/节日等)
    - output: LLM 生成结果 (JSON: 菜单/套餐/触达等)
    - metrics: 实际效果指标 (JSON: 售出率/客单价等)
    - is_successful: 是否成功样例
    - tags: 标签 (逗号分隔, 用于快速检索)

检索方式:
  基于多维度相似度评分 (天气/社区类型/节日/库存重合度)
  无需 embedding 模型, 使用规则评分, 工程上稳定可控
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional
from pathlib import Path


class MemoryStore:
    """历史成功样例存储与检索"""

    def __init__(self, db_path: Path):
        self.db_path = str(db_path)
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_cases (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                input_context TEXT  NOT NULL,
                output      TEXT    NOT NULL,
                metrics     TEXT,
                is_successful BOOLEAN DEFAULT 1,
                tags        TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_successful
            ON memory_cases(is_successful)
        """)
        conn.commit()
        conn.close()

    def store_case(
        self,
        input_context: dict,
        output: dict,
        metrics: Optional[dict] = None,
        is_successful: bool = True,
        tags: Optional[list] = None,
    ) -> int:
        """存储一个历史样例"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """INSERT INTO memory_cases
               (timestamp, input_context, output, metrics, is_successful, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().isoformat(),
                json.dumps(input_context, ensure_ascii=False),
                json.dumps(output, ensure_ascii=False),
                json.dumps(metrics, ensure_ascii=False) if metrics else None,
                is_successful,
                ",".join(tags) if tags else "",
            ),
        )
        case_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return case_id

    def retrieve_cases(self, current_context: dict, top_k: int = 5) -> list:
        """
        检索与当前上下文相似的历史成功样例

        相似度评分维度:
          - 天气类型匹配 (+3)
          - 社区客群类型匹配 (+2)
          - 节日/节气匹配 (+2)
          - 库存商品重合度 (+0.5/个)
          - 客流规模接近 (+1)
        """
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id, timestamp, input_context, output, metrics, tags "
            "FROM memory_cases WHERE is_successful = 1 ORDER BY id DESC LIMIT 100"
        ).fetchall()
        conn.close()

        scored = []
        for row in rows:
            case_input = json.loads(row[2])
            score = self._similarity_score(case_input, current_context)
            if score > 0:
                scored.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "input_context": case_input,
                    "output": json.loads(row[3]),
                    "metrics": json.loads(row[4]) if row[4] else None,
                    "tags": row[5].split(",") if row[5] else [],
                    "score": score,
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _similarity_score(self, case_ctx: dict, current_ctx: dict) -> float:
        """计算两个上下文的相似度分数"""
        score = 0.0

        # 天气类型
        case_weather = case_ctx.get("weather", {}).get("condition", "")
        cur_weather = current_ctx.get("weather", {}).get("condition", "")
        if case_weather and case_weather == cur_weather:
            score += 3

        # 社区客群类型
        case_comm = case_ctx.get("community", {}).get("type", "")
        cur_comm = current_ctx.get("community", {}).get("type", "")
        if case_comm and case_comm == cur_comm:
            score += 2

        # 节日/节气
        case_fest = case_ctx.get("festival", {}).get("name", "")
        cur_fest = current_ctx.get("festival", {}).get("name", "")
        if case_fest and case_fest == cur_fest:
            score += 2
        # 都无节日也加一点分（都是日常场景）
        if not case_fest and not cur_fest:
            score += 0.5

        # 库存商品重合度
        case_products = {item.get("name", "") for item in case_ctx.get("inventory", [])}
        cur_products = {item.get("name", "") for item in current_ctx.get("inventory", [])}
        overlap = len(case_products & cur_products)
        score += overlap * 0.5

        # 客流规模接近
        case_flow = case_ctx.get("foot_traffic", {}).get("estimated", 0)
        cur_flow = current_ctx.get("foot_traffic", {}).get("estimated", 0)
        if case_flow and cur_flow:
            ratio = min(case_flow, cur_flow) / max(case_flow, cur_flow)
            if ratio > 0.7:
                score += 1

        return score

    def list_all_cases(self, limit: int = 50) -> list:
        """列出所有历史样例（用于展示）"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id, timestamp, input_context, output, is_successful, tags "
            "FROM memory_cases ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "timestamp": row[1],
                "input_context": json.loads(row[2]),
                "output": json.loads(row[3]),
                "is_successful": row[4],
                "tags": row[5].split(",") if row[5] else [],
            }
            for row in rows
        ]

    def count(self) -> int:
        """返回样例总数"""
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM memory_cases").fetchone()[0]
        conn.close()
        return count

    def reset(self) -> int:
        """清空所有历史样例，返回删除的条数"""
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM memory_cases").fetchone()[0]
        conn.execute("DELETE FROM memory_cases")
        conn.commit()
        conn.close()
        return count
        return count
