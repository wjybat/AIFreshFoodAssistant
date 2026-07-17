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
import uuid
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_recommendations (
                plan_id        TEXT PRIMARY KEY,
                created_at     TEXT NOT NULL,
                store_id       TEXT,
                plan_date      TEXT,
                input_context  TEXT NOT NULL,
                output         TEXT NOT NULL,
                recipe_urls    TEXT NOT NULL,
                raw_thinking   TEXT NOT NULL DEFAULT '',
                raw_output     TEXT NOT NULL DEFAULT '',
                decision       TEXT,
                decided_at     TEXT,
                memory_case_id INTEGER
            )
        """)
        self._add_column_if_missing(conn, "pending_recommendations", "store_id", "TEXT")
        self._add_column_if_missing(conn, "pending_recommendations", "plan_date", "TEXT")
        self._add_column_if_missing(
            conn,
            "pending_recommendations",
            "raw_thinking",
            "TEXT NOT NULL DEFAULT ''",
        )
        self._add_column_if_missing(
            conn,
            "pending_recommendations",
            "raw_output",
            "TEXT NOT NULL DEFAULT ''",
        )
        self._backfill_pending_recommendation_keys(conn)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pending_recommendation_date
            ON pending_recommendations(store_id, plan_date)
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def _add_column_if_missing(
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ):
        columns = {
            row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")
        }
        if column_name not in columns:
            conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )

    @staticmethod
    def _backfill_pending_recommendation_keys(conn: sqlite3.Connection):
        """从旧输入快照中恢复方案的门店和业务日期键。"""
        rows = conn.execute(
            """SELECT plan_id, input_context FROM pending_recommendations
               WHERE COALESCE(store_id, '') = '' OR COALESCE(plan_date, '') = ''"""
        ).fetchall()
        for plan_id, serialized_input in rows:
            try:
                input_context = json.loads(serialized_input)
                store_info = input_context.get("store_info", {})
            except (TypeError, json.JSONDecodeError):
                continue

            if not isinstance(store_info, dict):
                continue

            store_id = str(
                store_info.get("store_id")
                or store_info.get("store_name")
                or ""
            ).strip()
            plan_date = str(store_info.get("date") or "").strip()
            if not store_id or not plan_date:
                continue

            conn.execute(
                """UPDATE pending_recommendations
                   SET store_id = CASE WHEN COALESCE(store_id, '') = '' THEN ? ELSE store_id END,
                       plan_date = CASE WHEN COALESCE(plan_date, '') = '' THEN ? ELSE plan_date END
                   WHERE plan_id = ?""",
                (store_id, plan_date, plan_id),
            )

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

    def create_pending_recommendation(
        self,
        input_context: dict,
        output: dict,
        recipe_urls: dict,
        raw_thinking: str = "",
        raw_output: str = "",
    ) -> str:
        """按门店和业务日期保存当前方案，不写入 Memory 样例。"""
        store_info = input_context.get("store_info", {})
        store_id = str(
            store_info.get("store_id")
            or store_info.get("store_name")
            or "default-store"
        ).strip()
        plan_date = str(store_info.get("date") or "").strip()
        if not plan_date:
            raise ValueError("输入数据缺少 store_info.date，无法保存日期方案")

        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            """SELECT plan_id FROM pending_recommendations
               WHERE store_id = ? AND plan_date = ?
               ORDER BY created_at DESC LIMIT 1""",
            (store_id, plan_date),
        ).fetchone()
        if existing:
            plan_id = existing[0]
            conn.execute(
                """UPDATE pending_recommendations
                   SET created_at = ?, input_context = ?, output = ?, recipe_urls = ?,
                       raw_thinking = ?, raw_output = ?, decision = NULL,
                       decided_at = NULL, memory_case_id = NULL
                   WHERE plan_id = ?""",
                (
                    now,
                    json.dumps(input_context, ensure_ascii=False),
                    json.dumps(output, ensure_ascii=False),
                    json.dumps(recipe_urls, ensure_ascii=False),
                    raw_thinking,
                    raw_output,
                    plan_id,
                ),
            )
        else:
            plan_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO pending_recommendations
                   (plan_id, created_at, store_id, plan_date, input_context, output,
                    recipe_urls, raw_thinking, raw_output)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    plan_id,
                    now,
                    store_id,
                    plan_date,
                    json.dumps(input_context, ensure_ascii=False),
                    json.dumps(output, ensure_ascii=False),
                    json.dumps(recipe_urls, ensure_ascii=False),
                    raw_thinking,
                    raw_output,
                ),
            )
        conn.commit()
        conn.close()
        return plan_id

    def get_recommendation(self, plan_id: str) -> Optional[dict]:
        """读取待确认方案及其当前决策状态。"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            """SELECT plan_id, created_at, store_id, plan_date, input_context, output,
                      recipe_urls, raw_thinking, raw_output, decision, decided_at,
                      memory_case_id
               FROM pending_recommendations WHERE plan_id = ?""",
            (plan_id,),
        ).fetchone()
        conn.close()
        return self._recommendation_from_row(row)

    def get_recommendation_for_date(
        self,
        store_id: str,
        plan_date: str,
    ) -> Optional[dict]:
        """获取某门店在指定业务日期的当前推荐方案。"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            """SELECT plan_id, created_at, store_id, plan_date, input_context, output,
                      recipe_urls, raw_thinking, raw_output, decision, decided_at,
                      memory_case_id
               FROM pending_recommendations
               WHERE store_id = ? AND plan_date = ?
               ORDER BY created_at DESC LIMIT 1""",
            (store_id, plan_date),
        ).fetchone()
        conn.close()
        return self._recommendation_from_row(row)

    def update_pending_recommendation_menu_image(
        self,
        plan_id: str,
        *,
        menu_index: int,
        expected_dish: str,
        image_url: str,
    ) -> Optional[dict]:
        """事务化合并单菜图片，不创建页面或改变决策与 Memory 样例。"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT output, recipe_urls
               FROM pending_recommendations WHERE plan_id = ?""",
            (plan_id,),
        ).fetchone()
        if row is None:
            conn.rollback()
            conn.close()
            return None

        output = json.loads(row[0])
        recipe_urls = json.loads(row[1])
        menus = output.get("menus")
        if not isinstance(menus, list) or not 0 <= menu_index < len(menus):
            conn.rollback()
            conn.close()
            raise ValueError("指定菜品不存在")
        menu = menus[menu_index]
        dish_name = str(menu.get("dish") or "") if isinstance(menu, dict) else ""
        if not dish_name or dish_name != expected_dish:
            conn.rollback()
            conn.close()
            raise ValueError("方案已更新，请重新选择要生成图片的菜品")

        menu["recipe_image_url"] = image_url
        cursor = conn.execute(
            """UPDATE pending_recommendations
               SET output = ?
               WHERE plan_id = ?""",
            (
                json.dumps(output, ensure_ascii=False),
                plan_id,
            ),
        )
        conn.commit()
        conn.close()
        if cursor.rowcount != 1:
            return None
        return {"result": output, "recipe_urls": recipe_urls}

    def list_recommendation_history(self) -> list:
        """按门店和业务日期列出当前保存的推荐方案。"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """SELECT plan_id, created_at, store_id, plan_date, input_context,
                      output, decision
               FROM pending_recommendations
               WHERE COALESCE(store_id, '') <> '' AND COALESCE(plan_date, '') <> ''
               ORDER BY plan_date DESC, created_at DESC"""
        ).fetchall()
        conn.close()

        history = []
        seen_keys = set()
        for row in rows:
            store_id, plan_date = row[2], row[3]
            key = (store_id, plan_date)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            try:
                input_context = json.loads(row[4])
                output = json.loads(row[5])
            except (TypeError, json.JSONDecodeError):
                continue

            store_info = input_context.get("store_info", {})
            menus = output.get("menus", [])
            history.append(
                {
                    "plan_id": row[0],
                    "created_at": row[1],
                    "store_id": store_id,
                    "store_name": store_info.get("store_name") or store_id,
                    "plan_date": plan_date,
                    "scenario_tag": output.get("scenario_tag", "历史推荐方案"),
                    "menu_count": len(menus) if isinstance(menus, list) else 0,
                    "decision": row[6],
                }
            )
        return history

    def clear_recommendation_history(self) -> int:
        """清空全部已保存的推荐方案，不影响 Memory 历史样例。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("DELETE FROM pending_recommendations")
        conn.commit()
        conn.close()
        return cursor.rowcount

    @staticmethod
    def _recommendation_from_row(row) -> Optional[dict]:
        if row is None:
            return None
        return {
            "plan_id": row[0],
            "created_at": row[1],
            "store_id": row[2],
            "plan_date": row[3],
            "input_context": json.loads(row[4]),
            "result": json.loads(row[5]),
            "recipe_urls": json.loads(row[6]),
            "raw_thinking": row[7],
            "raw_output": row[8],
            "decision": row[9],
            "decided_at": row[10],
            "memory_case_id": row[11],
        }

    def decide_recommendation(self, plan_id: str, accepted: bool) -> Optional[dict]:
        """确认方案并写入 Memory；同一方案只能被处理一次。"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            """SELECT input_context, output, decision, memory_case_id
               FROM pending_recommendations WHERE plan_id = ?""",
            (plan_id,),
        ).fetchone()
        if row is None:
            conn.close()
            return None

        if row[2] is not None:
            conn.close()
            return {
                "decision": row[2],
                "memory_case_id": row[3],
                "already_decided": True,
            }

        decision = "accepted" if accepted else "rejected"
        output = json.loads(row[1])
        cursor = conn.execute(
            """INSERT INTO memory_cases
               (timestamp, input_context, output, metrics, is_successful, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().isoformat(),
                row[0],
                row[1],
                json.dumps(output.get("value_estimate"), ensure_ascii=False),
                accepted,
                ",".join([output.get("scenario_tag", ""), decision]),
            ),
        )
        memory_case_id = cursor.lastrowid
        conn.execute(
            """UPDATE pending_recommendations
               SET decision = ?, decided_at = ?, memory_case_id = ?
               WHERE plan_id = ?""",
            (decision, datetime.now().isoformat(), memory_case_id, plan_id),
        )
        conn.commit()
        conn.close()
        return {
            "decision": decision,
            "memory_case_id": memory_case_id,
            "already_decided": False,
        }

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
