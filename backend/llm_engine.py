"""
LLM Agentic Workflow 引擎 —— 核心推理生成模块

工作流程:
  1. Memory 检索: 从 SQLite 检索相似历史成功样例
  2. Prompt 组装: System(角色+Skills) + Few-Shot(历史样例) + User(今日数据)
  3. LLM 调用: 流式调用 LLM API，实时输出推理过程
  4. 输出解析: 分离推理过程与结构化 JSON 结果
  5. 菜谱部署: 为每道菜生成独立 HTML 页面，部署到 recipes/ 目录
  6. Memory 存储: 将本次生成结果存入 Memory 供后续检索

支持两种模式:
  - 真实模式: 配置了 LLM_API_KEY 时，调用真实 LLM API
  - Mock 模式: 未配置 API Key 时，使用基于输入数据的模拟生成（用于测试调试）
"""
import json
import re
import asyncio
import logging
from html import escape
from typing import AsyncGenerator

from .agent import AgentDataError, OperationalDataAgent, REQUIRED_MCP_TOOLS
from .config import config
from .mcp_client import MCPToolClient
from .memory import MemoryStore
from .skills import build_system_prompt, build_few_shot, build_user_prompt


logger = logging.getLogger(__name__)
ZHIPU_THINKING_MODELS = frozenset({"glm-5.2", "glm-5.1", "glm-5", "glm-4.7"})
OPENCODE_REASONING_MODELS = frozenset({"glm-5.2"})
OPENCODE_REASONING_EFFORTS = frozenset({"high", "max"})


class LLMEngine:
    """LLM Agentic Workflow 引擎"""

    def __init__(self, memory_store: MemoryStore):
        self.memory = memory_store
        self.client = None
        mcp_client = None

        if config.MCP_ENABLED:
            mcp_client = MCPToolClient(
                config.MCP_SERVER_URL,
                allowed_tools=REQUIRED_MCP_TOOLS,
                timeout_seconds=config.MCP_TIMEOUT_SECONDS,
                max_response_bytes=config.MCP_MAX_RESPONSE_BYTES,
                auth_token=config.MCP_AUTH_TOKEN,
            )
        self.data_agent = OperationalDataAgent(
            mcp_client,
            required=config.MCP_REQUIRED,
            sales_window_days=config.AGENT_SALES_WINDOW_DAYS,
            max_products=config.AGENT_MAX_PRODUCTS,
        )

        if not config.mock_mode:
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(
                    api_key=config.LLM_API_KEY,
                    base_url=config.LLM_BASE_URL,
                )
            except Exception as e:
                print(f"[LLM Engine] OpenAI 客户端初始化失败: {e}")
                self.client = None

    @property
    def is_real_mode(self) -> bool:
        return self.client is not None

    async def generate(self, input_data: dict, enable_thinking: bool = True) -> AsyncGenerator[str, None]:
        """
        主生成流程 —— 异步生成器，yield SSE 格式的事件字符串

        事件类型:
          - status: 状态更新（"正在检索Memory..."等）
          - agent: 多步 Agent 的高层步骤与 MCP 工具调用轨迹
          - thinking: LLM 深度思考输出（reasoning_content）
          - token: LLM 正文输出（content）
          - done: 生成完成，携带结构化结果
          - error: 错误信息
        """
        try:
            # ===== Step 1: 多步经营数据 Agent =====
            yield self._sse("status", "正在启动多步经营数据 Agent...")
            working_input = input_data
            agent_trace = []
            async for agent_event_type, payload in self.data_agent.run(input_data):
                if agent_event_type == "event":
                    yield self._sse("agent", payload)
                elif agent_event_type == "result":
                    working_input = payload["input_data"]
                    agent_trace = payload.get("trace", [])

            # ===== Step 2: Memory 检索 =====
            yield self._sse("status", "正在检索 Memory 历史成功样例...")
            await asyncio.sleep(0.3)

            memory_cases = self.memory.retrieve_cases(
                working_input, top_k=config.MEMORY_TOP_K
            )
            yield self._sse("status", f"找到 {len(memory_cases)} 条相似历史样例")
            await asyncio.sleep(0.2)

            # ===== Step 3: Prompt 组装 =====
            yield self._sse("status", "正在组装 Prompt（注入 Skills + Few-Shot）...")
            await asyncio.sleep(0.3)

            system_prompt = build_system_prompt()
            few_shot = build_few_shot(memory_cases)
            user_prompt = build_user_prompt(working_input)

            full_user_prompt = few_shot + "\n" + user_prompt

            # ===== Step 4: LLM 调用 =====
            if self.is_real_mode:
                mode_label = "深度思考" if enable_thinking else "标准模式"
                yield self._sse("status", f"正在调用 LLM ({config.LLM_MODEL} · {mode_label}) 生成中...")
                raw_thinking = ""
                raw_output = ""
                async for evt_type, token in self._call_llm_stream(system_prompt, full_user_prompt, enable_thinking):
                    if evt_type == "thinking":
                        if enable_thinking:
                            raw_thinking += token
                            yield self._sse("thinking", token)
                    elif evt_type == "token":
                        raw_output += token
                        yield self._sse("token", token)
            else:
                yield self._sse("status", "⚠️ Mock 模式（未配置 LLM API Key）—— 使用模拟生成")
                raw_thinking = ""
                raw_output = ""
                async for evt_type, token in self._mock_generate(working_input, enable_thinking):
                    if evt_type == "thinking":
                        if enable_thinking:
                            raw_thinking += token
                            yield self._sse("thinking", token)
                    elif evt_type == "token":
                        raw_output += token
                        yield self._sse("token", token)

            # ===== Step 5: 输出解析 =====
            yield self._sse("status", "LLM 生成完成，正在解析结构化输出...")
            await asyncio.sleep(0.3)

            result = self._parse_output(raw_output)
            if result is None:
                yield self._sse("error", "无法解析 LLM 输出中的 JSON 结果")
                return
            try:
                self._validate_result_contract(result)
            except ValueError as exc:
                yield self._sse("error", f"LLM 输出不符合结果契约: {exc}")
                return

            # ===== Step 6: 菜谱页面部署 =====
            yield self._sse("status", "正在部署菜谱页面到云端...")
            await asyncio.sleep(0.3)

            recipe_urls = self._deploy_recipe_pages(result, working_input)

            # ===== Step 7: 等待门店负责人决策 =====
            yield self._sse("status", "方案已生成，等待门店负责人确认...")
            await asyncio.sleep(0.2)
            plan_id = self.memory.create_pending_recommendation(
                input_context=working_input,
                output=result,
                recipe_urls=recipe_urls,
                raw_thinking=raw_thinking,
                raw_output=raw_output,
            )

            # ===== 完成 =====
            yield self._sse("status", "✅ 生成完成，待门店负责人决策")
            yield self._sse("done", {
                "plan_id": plan_id,
                "result": result,
                "recipe_urls": recipe_urls,
                "raw_thinking": raw_thinking,
                "raw_output": raw_output,
                "memory_count": self.memory.count(),
                "mock_mode": not self.is_real_mode,
                "input_context": working_input,
                "agent_trace": agent_trace,
                "operational_data": working_input.get("operational_data", {}),
            })

        except Exception as e:
            if isinstance(e, (AgentDataError, ValueError)):
                logger.warning("Generation workflow rejected input: %s", e)
                message = str(e)
            else:
                logger.exception("Generation workflow failed")
                message = "内部服务异常，请检查后端日志"
            yield self._sse("error", f"生成过程出错: {message}")

    async def _call_llm_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        enable_thinking: bool = True,
    ) -> AsyncGenerator[tuple, None]:
        """流式调用 LLM API，逐 token 返回 (type, token) 元组
        type: "thinking" (reasoning_content) 或 "token" (content)
        """
        kwargs = self._build_chat_request(
            system_prompt,
            user_prompt,
            enable_thinking,
        )

        assert self.client is not None
        response = await self.client.chat.completions.create(**kwargs)

        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning_content = self._delta_value(delta, "reasoning_content")
            content = self._delta_value(delta, "content")
            if enable_thinking and reasoning_content:
                yield ("thinking", str(reasoning_content))
                await asyncio.sleep(0.01)
            if content:
                yield ("token", str(content))
                await asyncio.sleep(0.01)

    @staticmethod
    def _build_chat_request(
        system_prompt: str,
        user_prompt: str,
        enable_thinking: bool,
    ) -> dict:
        """Build an OpenAI-compatible request with provider-specific extensions."""
        kwargs = dict(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
        )
        provider = config.resolved_llm_provider
        model = config.LLM_MODEL.strip().lower().split("[", 1)[0]
        if provider == "zhipu" and model in ZHIPU_THINKING_MODELS:
            extra_body = {
                "thinking": {
                    "type": "enabled" if enable_thinking else "disabled"
                }
            }
            if enable_thinking and model == "glm-5.2":
                extra_body["reasoning_effort"] = config.LLM_REASONING_EFFORT
            kwargs["extra_body"] = extra_body
        elif (
            provider == "opencode"
            and model in OPENCODE_REASONING_MODELS
            and enable_thinking
        ):
            # OpenCode Go exposes GLM-5.2 reasoning through the standard
            # OpenAI-compatible reasoning_effort field, with high/max tiers.
            # extra_body keeps compatibility with the project's older allowed
            # OpenAI SDK versions while merging this into the top-level JSON.
            if config.LLM_REASONING_EFFORT not in OPENCODE_REASONING_EFFORTS:
                allowed = ", ".join(sorted(OPENCODE_REASONING_EFFORTS))
                raise ValueError(
                    "LLM_REASONING_EFFORT must be one of "
                    f"{allowed} for OpenCode GLM-5.2"
                )
            kwargs["extra_body"] = {
                "reasoning_effort": config.LLM_REASONING_EFFORT
            }
        elif provider == "legacy" and enable_thinking:
            kwargs["extra_body"] = {"enable_thinking": True}
        return kwargs

    @staticmethod
    def _delta_value(delta, name: str):
        if isinstance(delta, dict):
            return delta.get(name)
        return getattr(delta, name, None)

    async def _mock_generate(self, input_data: dict, enable_thinking: bool = True) -> AsyncGenerator[tuple, None]:
        """
        Mock 模式：基于输入数据生成模拟推理过程和结果
        返回 (type, token) 元组，与真实模式一致
        """
        inventory = input_data.get("inventory", [])
        expiring = [item for item in inventory if item.get("status") == "临期"]
        high_stock = [item for item in inventory if item.get("stock_level") == "high"]
        weather = input_data.get("weather", {})
        community = input_data.get("community", {})
        festival = input_data.get("festival", {})

        # 构建模拟推理过程
        mock_text = f"""1. 临期商品分析：
"""

        for item in expiring:
            mock_text += f"   - {item['name']}：剩余 {item.get('expiry_days','?')} 天临期，库存 {item['stock']}{item.get('unit','')}，需优先消耗\n"

        # 基于临期商品推理菜谱
        dish_suggestions = self._suggest_dishes_mock(expiring, high_stock)

        mock_text += f"""
2. 高库存商品分析：
"""
        for item in high_stock:
            mock_text += f"   - {item['name']}：库存偏高（{item['stock']}{item.get('unit','')}），需通过套餐组合加速消耗\n"

        mock_text += f"""
3. 场景适配分析：
   - 天气：{weather.get('description', weather.get('condition',''))}，"""
        if weather.get("condition") in ("rain", "snow"):
            mock_text += "热菜热汤需求上升，适合推荐炒菜、炖菜\n"
        elif weather.get("condition") == "hot":
            mock_text += "凉拌清淡需求上升，适合推荐凉菜、汤品\n"
        else:
            mock_text += "常规搭配，适合推荐家常菜\n"

        mock_text += f"   - 社区客群：{community.get('type','')}，客流高峰 {community.get('peak_hour','')}\n"
        if festival.get("name"):
            mock_text += f"   - 节日：{festival['name']}，推荐节令菜品\n"

        mock_text += f"""
4. 组合均衡判断：
   基于以上分析，推荐以下套餐组合（主菜+配菜+汤/主食），品类均衡，口味互补。

5. 触达策略：
   - 推送时机：{community.get('peak_hour','18:00')}前30分钟推送
   - 文案突出"今晚"+"省时"+"场景适配"

【生成结果】
```json
{json.dumps(self._build_mock_result(input_data, dish_suggestions), ensure_ascii=False, indent=2)}
```
"""

        # 分离思维链和正文。前端负责稳定逐字播放，后端按小块发送以避免
        # Mock 模式为每个字符创建一次异步调度。
        split_marker = "【生成结果】"
        thinking_part, _, output_part = mock_text.partition(split_marker)
        output_part = "【生成结果】" + output_part

        if enable_thinking:
            for index in range(0, len(thinking_part), 12):
                yield ("thinking", thinking_part[index:index + 12])
                await asyncio.sleep(0.01)
        for index in range(0, len(output_part), 16):
            yield ("token", output_part[index:index + 16])
            await asyncio.sleep(0.01)

    def _suggest_dishes_mock(self, expiring: list, high_stock: list) -> list:
        """基于临期/高库存商品推测菜谱（Mock 模式用）"""
        suggestions = []
        all_items = expiring + high_stock
        names = {item["name"] for item in all_items}

        # 简单的食材→菜谱映射
        mappings = {
            ("青椒", "猪肉"): {"dish": "青椒肉丝", "emoji": "🫑", "role": "主菜"},
            ("豆腐",): {"dish": "麻婆豆腐", "emoji": "🌶️", "role": "配菜"},
            ("番茄", "鸡蛋"): {"dish": "番茄炒蛋", "emoji": "🍅", "role": "配菜"},
            ("五花肉",): {"dish": "红烧肉", "emoji": "🥩", "role": "硬菜"},
            ("冬瓜", "排骨"): {"dish": "冬瓜排骨汤", "emoji": "🍲", "role": "汤品"},
            ("黄瓜",): {"dish": "凉拌黄瓜", "emoji": "🥒", "role": "主菜"},
            ("白菜", "猪肉馅"): {"dish": "白菜猪肉水饺", "emoji": "🥟", "role": "主推"},
            ("紫菜", "鸡蛋"): {"dish": "紫菜蛋花汤", "emoji": "🍵", "role": "汤品"},
        }

        for ingredients, dish_info in mappings.items():
            if set(ingredients) & names:
                suggestions.append(dish_info)
                # 移除已匹配的食材避免重复
                names -= set(ingredients)

        # 如果没有匹配到，生成通用菜谱
        if not suggestions and all_items:
            first_item = all_items[0]
            suggestions.append({
                "dish": f"{first_item['name']}快手菜",
                "emoji": "🍳",
                "role": "主菜",
            })

        return suggestions[:4]  # 最多4道菜

    def _build_mock_result(self, input_data: dict, dishes: list) -> dict:
        """构建 Mock 模式的结构化结果"""
        inventory = input_data.get("inventory", [])
        expiring = [item for item in inventory if item.get("status") == "临期"]

        menus = []
        for dish_info in dishes:
            # 从库存中找相关食材
            related = [item for item in inventory if item["name"] in dish_info.get("dish", "")]
            total_cost = sum(item.get("cost", 0) * 2 for item in related) or 15
            total_price = sum(item.get("price", 0) * 2 for item in related) or 25
            package_price = round(total_price * 0.8, 1)

            menus.append({
                "dish": dish_info["dish"],
                "emoji": dish_info["emoji"],
                "role": dish_info["role"],
                "priority_reason": f"含临期/高库存食材，优先消耗",
                "ingredients": [
                    {"name": item["name"], "amount": f"{item['stock']//5}{item.get('unit','g')}"}
                    for item in related[:4]
                ] or [{"name": "主料", "amount": "200g"}, {"name": "调料", "amount": "适量"}],
                "servings": "2人份",
                "cook_time": "15分钟",
                "difficulty": "简单",
                "recipe": {
                    "steps": [
                        "准备食材，清洗切配",
                        "热锅下油，爆香调料",
                        "下主料翻炒至熟",
                        "调味出锅装盘",
                    ],
                    "tips": "大火快炒保持食材口感，注意火候控制。",
                },
                "package_price": package_price,
                "original_price": total_price,
            })

        return {
            "scenario_tag": f"{input_data.get('weather',{}).get('description','')}·{input_data.get('community',{}).get('type','')}",
            "menus": menus,
            "cross_sell": "+¥6 得熟食米饭+例汤",
            "push_message": f"今晚做{dishes[0]['dish'] if dishes else '家常菜'}！🏠 食材已配好，回家即炒",
            "staff_instructions": [
                {"task": f"拣货：{dishes[0]['dish'] if dishes else '主菜'}食材 ×40份", "deadline": "09:00"},
                {"task": "布置场景化堆头：生鲜区入口", "deadline": "10:00"},
                {"task": "熟食区备联动套餐", "deadline": "16:00"},
            ],
            "display_plan": {
                "main": f"{dishes[0]['dish'] if dishes else '今日推荐'}堆头",
                "side": "配菜区",
                "cooked": "熟食联动",
                "entrance": "场景包入口",
            },
            "value_estimate": {
                "loss_reduction": f"¥{sum(item.get('cost',0)*item.get('stock',0)*0.1 for item in expiring):.0f}",
                "ticket_lift": "+18%",
                "cross_sell_rate": "3.8件/单",
                "member_open_rate": "+27%",
            },
        }

    def _parse_output(self, raw_output: str) -> dict | None:
        """从 LLM 原始输出中解析 JSON 结果"""
        # 尝试匹配 ```json ... ``` 格式
        json_match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试匹配裸 JSON（从第一个 { 到最后一个 }）
        brace_match = re.search(r"\{.*\}", raw_output, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _validate_result_contract(result: dict) -> None:
        required = {
            "scenario_tag": str,
            "menus": list,
            "value_estimate": dict,
            "staff_instructions": list,
            "display_plan": dict,
            "cross_sell": str,
        }
        missing = [name for name in required if name not in result]
        if missing:
            raise ValueError("缺少字段: " + ", ".join(missing))
        invalid = [
            name for name, expected_type in required.items()
            if not isinstance(result.get(name), expected_type)
        ]
        if invalid:
            raise ValueError("字段类型错误: " + ", ".join(invalid))
        if not result["scenario_tag"].strip():
            raise ValueError("scenario_tag 不能为空")
        if not result["menus"]:
            raise ValueError("menus 不能为空")
        if any(
            not isinstance(menu, dict) or not menu.get("dish")
            for menu in result["menus"]
        ):
            raise ValueError("menus 中每项都必须包含 dish")

    def _deploy_recipe_pages(self, result: dict, input_data: dict) -> dict:
        """
        为每道菜生成独立的 HTML 菜谱页面，部署到 recipes/ 目录
        返回 {dish_name: recipe_url} 映射
        """
        config.ensure_dirs()
        recipe_urls = {}
        store_name = input_data.get("store_info", {}).get("store_name", "AI社区超市")

        for i, menu in enumerate(result.get("menus", [])):
            dish_name = menu.get("dish", f"dish_{i}")
            recipe = menu.get("recipe", {})
            # 文件名只用ASCII，避免URL含中文导致二维码编码过长
            filename = f"recipe_{i}.html"
            filepath = config.RECIPES_DIR / filename

            html = self._build_recipe_html(menu, store_name, result.get("scenario_tag", ""))
            filepath.write_text(html, encoding="utf-8")

            recipe_url = f"{config.SERVER_URL}/recipes/{filename}"
            recipe_urls[dish_name] = recipe_url

        return recipe_urls

    def _build_recipe_html(self, menu: dict, store_name: str, scenario_tag: str) -> str:
        """生成单道菜的独立 HTML 菜谱页面"""
        safe = lambda value: escape(str(value or ""), quote=True)
        dish = safe(menu.get("dish", ""))
        emoji = safe(menu.get("emoji", "🍳"))
        servings = safe(menu.get("servings", ""))
        cook_time = safe(menu.get("cook_time", ""))
        difficulty = safe(menu.get("difficulty", ""))
        ingredients = menu.get("ingredients", [])
        recipe = menu.get("recipe", {})
        steps = recipe.get("steps", [])
        tips = safe(recipe.get("tips", ""))
        package_price = safe(menu.get("package_price", ""))
        original_price = safe(menu.get("original_price", ""))

        ingredients_html = "".join(
            f"<tr><td>{safe(ing.get('name',''))}</td><td>{safe(ing.get('amount',''))}</td><td>{safe(ing.get('note',''))}</td></tr>"
            for ing in ingredients if isinstance(ing, dict)
        )
        steps_html = "".join(f"<li>{safe(step)}</li>" for step in steps)
        store_name = safe(store_name)
        scenario_tag = safe(scenario_tag)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{dish} · 菜谱</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;background:#f4f6f9;color:#1a2332;line-height:1.6}}
.page{{max-width:520px;margin:0 auto;background:#fff;min-height:100vh;box-shadow:0 0 40px rgba(0,0,0,.06)}}
.hero{{padding:32px 20px 24px;text-align:center;background:linear-gradient(135deg,#e6f7f6,#f0fdfa)}}
.hero .emoji{{font-size:64px;margin-bottom:10px}}
.hero h1{{font-size:24px;font-weight:800;margin-bottom:6px}}
.badges{{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;margin-top:10px}}
.badge{{font-size:11.5px;padding:4px 12px;border-radius:8px;background:#fff;color:#5a6577;font-weight:600}}
.meta{{display:flex;border-bottom:1px solid #eef2f7}}
.meta-item{{flex:1;text-align:center;padding:14px 4px;border-right:1px solid #eef2f7}}
.meta-item:last-child{{border-right:none}}
.meta-item .v{{font-size:16px;font-weight:700;color:#0d8b8a}}
.meta-item .l{{font-size:11px;color:#8a95a8;margin-top:3px}}
.section{{padding:18px 20px;border-bottom:1px solid #eef2f7}}
.section h2{{font-size:16px;font-weight:700;margin-bottom:12px}}
.ingr-row{{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px dotted #eef2f7}}
.ingr-row:last-child{{border-bottom:none}}
.ingr-row .amt{{color:#0d8b8a;font-weight:600}}
.steps{{list-style:none;counter-reset:step}}
.steps li{{position:relative;padding:10px 0 10px 42px;border-bottom:1px dotted #eef2f7}}
.steps li:last-child{{border-bottom:none}}
.steps li::before{{counter-increment:step;content:counter(step);position:absolute;left:0;top:9px;width:30px;height:30px;border-radius:50%;background:#0ea5a4;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700}}
.tips{{background:#fff3ea;border-radius:12px;padding:14px 16px;font-size:13.5px;color:#92400e}}
.price{{padding:18px 20px;text-align:center;background:#e6f7f6}}
.price .now{{font-size:28px;font-weight:800;color:#f97316}}
.price .old{{font-size:14px;color:#8a95a8;text-decoration:line-through;margin-left:8px}}
.footer{{padding:18px 20px;text-align:center;background:#0e2a3a;color:#fff}}
.footer .logo{{font-size:20px;margin-bottom:6px}}
.footer .name{{font-size:14px;font-weight:700}}
.footer .desc{{font-size:11.5px;color:#a7d4d3;margin-top:4px}}
</style>
</head>
<body>
<div class="page">
  <div class="hero">
    <div class="emoji">{emoji}</div>
    <h1>{dish}</h1>
    <div class="badges">
      <span class="badge">{servings}</span>
      <span class="badge">⏱️ {cook_time}</span>
      <span class="badge">{difficulty}</span>
    </div>
  </div>
  <div class="meta">
    <div class="meta-item"><div class="v">{servings}</div><div class="l">分量</div></div>
    <div class="meta-item"><div class="v">{cook_time}</div><div class="l">用时</div></div>
    <div class="meta-item"><div class="v">{difficulty}</div><div class="l">难度</div></div>
  </div>
  <div class="section">
    <h2>🥬 食材清单</h2>
    {ingredients_html}
  </div>
  <div class="section">
    <h2>👩‍🍳 制作步骤</h2>
    <ol class="steps">
      {steps_html}
    </ol>
  </div>
  <div class="section">
    <h2>💡 小贴士</h2>
    <div class="tips">{tips}</div>
  </div>
  <div class="price">
    套餐价 <span class="now">¥{package_price}</span><span class="old">原价 ¥{original_price}</span>
  </div>
  <div class="footer">
    <div class="logo">🍽️</div>
    <div class="name">AI 社区餐桌预测引擎</div>
    <div class="desc">{store_name} · {scenario_tag}</div>
  </div>
</div>
</body>
</html>"""

    @staticmethod
    def _sse(event_type: str, content) -> str:
        """格式化 SSE 事件"""
        data = json.dumps({"type": event_type, "content": content}, ensure_ascii=False)
        return f"data: {data}\n\n"
