"""Recipe poster generation through an OpenAI-compatible Images Edit API."""
from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .config import config


logger = logging.getLogger(__name__)


class RecipeImageError(RuntimeError):
    """Raised when recipe image generation is configured as required and fails."""


@dataclass(frozen=True)
class RecipeImageResult:
    index: int
    dish_name: str
    image_url: str | None = None
    error: str | None = None


class RecipeImageGenerator:
    """Generate one portrait recipe poster for every menu item."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    @property
    def enabled(self) -> bool:
        return config.IMAGE_GENERATION_ENABLED

    async def generate_all(
        self,
        menus: list[dict[str, Any]],
        *,
        store_name: str,
        scenario_tag: str,
    ) -> list[RecipeImageResult]:
        if not self.enabled or not menus:
            return []

        reference_path = config.IMAGE_REFERENCE_PATH
        reference_error = self._validate_reference(reference_path)
        if reference_error:
            if config.IMAGE_GENERATION_REQUIRED:
                raise RecipeImageError(reference_error)
            return [
                RecipeImageResult(
                    index=index,
                    dish_name=str(menu.get("dish") or f"dish_{index}"),
                    error=reference_error,
                )
                for index, menu in enumerate(menus)
            ]

        reference_bytes = reference_path.read_bytes()
        reference_mime = self._mime_for_path(reference_path)
        semaphore = asyncio.Semaphore(config.IMAGE_MAX_CONCURRENCY)

        async def run_with(client: httpx.AsyncClient) -> list[RecipeImageResult]:
            tasks = [
                self._generate_one(
                    client,
                    semaphore,
                    index=index,
                    menu=menu,
                    store_name=store_name,
                    scenario_tag=scenario_tag,
                    reference_path=reference_path,
                    reference_bytes=reference_bytes,
                    reference_mime=reference_mime,
                )
                for index, menu in enumerate(menus)
            ]
            results = list(await asyncio.gather(*tasks))
            failures = [item for item in results if item.error]
            if failures and config.IMAGE_GENERATION_REQUIRED:
                raise RecipeImageError(
                    "菜谱图片生成失败: "
                    + "; ".join(
                        f"{item.dish_name}: {item.error}" for item in failures
                    )
                )
            return results

        if self._client is not None:
            return await run_with(self._client)

        headers = {}
        if config.IMAGE_API_KEY:
            headers["Authorization"] = f"Bearer {config.IMAGE_API_KEY}"
        timeout = httpx.Timeout(config.IMAGE_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            return await run_with(client)

    async def _generate_one(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        *,
        index: int,
        menu: dict[str, Any],
        store_name: str,
        scenario_tag: str,
        reference_path: Path,
        reference_bytes: bytes,
        reference_mime: str,
    ) -> RecipeImageResult:
        dish_name = str(menu.get("dish") or f"dish_{index}")
        prompt = self._build_prompt(
            menu,
            store_name=store_name,
            scenario_tag=scenario_tag,
        )

        try:
            async with semaphore:
                image_bytes = await self._request_image(
                    client,
                    prompt=prompt,
                    reference_path=reference_path,
                    reference_bytes=reference_bytes,
                    reference_mime=reference_mime,
                )
            extension = self._detect_extension(image_bytes)
            if extension is None:
                raise RecipeImageError("接口返回的内容不是受支持的 PNG/JPEG/WebP 图片")
            if len(image_bytes) > config.IMAGE_MAX_RESPONSE_BYTES:
                raise RecipeImageError("接口返回的图片超过大小限制")

            config.ensure_dirs()
            filename = f"recipe_{index}.{extension}"
            target = config.RECIPES_DIR / filename
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(image_bytes)
            temporary.replace(target)
            image_url = f"{config.SERVER_URL.rstrip('/')}/recipes/{filename}"
            return RecipeImageResult(index, dish_name, image_url=image_url)
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            logger.warning("Recipe image generation failed for %s: %s", dish_name, message)
            return RecipeImageResult(index, dish_name, error=message)

    async def _request_image(
        self,
        client: httpx.AsyncClient,
        *,
        prompt: str,
        reference_path: Path,
        reference_bytes: bytes,
        reference_mime: str,
    ) -> bytes:
        endpoint = f"{config.IMAGE_API_BASE_URL.rstrip('/')}/images/edits"
        full_fields = {
            "model": config.IMAGE_MODEL,
            "prompt": prompt,
            "n": "1",
            "size": config.IMAGE_SIZE,
            "quality": config.IMAGE_QUALITY,
            "input_fidelity": "high",
            "background": "opaque",
            "output_format": "png",
        }
        minimal_fields = {
            "model": config.IMAGE_MODEL,
            "prompt": prompt,
            "n": "1",
            "size": config.IMAGE_SIZE,
        }

        response = await self._post_edit(
            client,
            endpoint,
            full_fields,
            reference_path,
            reference_bytes,
            reference_mime,
            model_in_query=False,
        )
        if response.status_code in {400, 422}:
            logger.info(
                "Image endpoint rejected optional fields; retrying minimal request"
            )
            response = await self._post_edit(
                client,
                endpoint,
                minimal_fields,
                reference_path,
                reference_bytes,
                reference_mime,
                model_in_query=False,
            )
        if (
            response.is_error
            and config.IMAGE_MODEL_QUERY_FALLBACK
            and self._is_model_routing_error(response)
        ):
            logger.info(
                "Image endpoint did not route multipart model field; "
                "retrying with model query parameter"
            )
            response = await self._post_edit(
                client,
                endpoint,
                minimal_fields,
                reference_path,
                reference_bytes,
                reference_mime,
                model_in_query=True,
            )
        if response.is_error:
            detail = response.text[:500].replace("\n", " ")
            raise RecipeImageError(
                f"图片接口返回 HTTP {response.status_code}: {detail}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise RecipeImageError("图片接口未返回 JSON") from exc
        return await self._extract_image_bytes(client, payload)

    @staticmethod
    async def _post_edit(
        client: httpx.AsyncClient,
        endpoint: str,
        fields: dict[str, str],
        reference_path: Path,
        reference_bytes: bytes,
        reference_mime: str,
        *,
        model_in_query: bool,
    ) -> httpx.Response:
        return await client.post(
            endpoint,
            params={"model": fields["model"]} if model_in_query else None,
            data=fields,
            files={
                "image": (
                    reference_path.name,
                    reference_bytes,
                    reference_mime,
                )
            },
        )

    @staticmethod
    def _is_model_routing_error(response: httpx.Response) -> bool:
        if response.status_code not in {400, 404, 500, 502, 503}:
            return False
        detail = response.text[:1000].lower()
        return "model" in detail or "channel" in detail

    async def _extract_image_bytes(
        self,
        client: httpx.AsyncClient,
        payload: Any,
    ) -> bytes:
        if not isinstance(payload, dict):
            raise RecipeImageError("图片接口响应结构无效")
        items = payload.get("data")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise RecipeImageError("图片接口响应缺少 data[0]")
        item = items[0]

        encoded = next(
            (
                item.get(key)
                for key in ("b64_json", "image_base64", "base64")
                if item.get(key)
            ),
            None,
        )
        if isinstance(encoded, str):
            if encoded.startswith("data:") and "," in encoded:
                encoded = encoded.split(",", 1)[1]
            encoded = "".join(encoded.split())
            try:
                image_bytes = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise RecipeImageError("图片接口返回了无效的 base64 数据") from exc
            if len(image_bytes) > config.IMAGE_MAX_RESPONSE_BYTES:
                raise RecipeImageError("接口返回的图片超过大小限制")
            return image_bytes

        image_url = item.get("url")
        if isinstance(image_url, str) and image_url.startswith(("http://", "https://")):
            response = await client.get(image_url)
            response.raise_for_status()
            if len(response.content) > config.IMAGE_MAX_RESPONSE_BYTES:
                raise RecipeImageError("下载的图片超过大小限制")
            return response.content
        raise RecipeImageError("图片接口响应缺少 base64 图片或 URL")

    @staticmethod
    def _build_prompt(
        menu: dict[str, Any],
        *,
        store_name: str,
        scenario_tag: str,
    ) -> str:
        recipe_payload = {
            "菜名": menu.get("dish", ""),
            "分量": menu.get("servings", ""),
            "时间": menu.get("cook_time", ""),
            "难度": menu.get("difficulty", ""),
            "食材": menu.get("ingredients", []),
            "做法": (menu.get("recipe") or {}).get("steps", []),
            "小贴士": (menu.get("recipe") or {}).get("tips", ""),
            "门店": store_name,
            "场景": scenario_tag,
        }
        content = json.dumps(recipe_payload, ensure_ascii=False, indent=2)
        return f"""请以输入参考图片为强风格和版式参考，生成一张全新的竖版中文菜谱海报。

视觉要求：
1. 延续参考图的米白纸张质感、暖金色装饰、清爽中式排版和专业食物摄影。
2. 顶部为醒目的中文菜名，右上角保留简洁商家标识区，可显示“{store_name}”，不要复制参考图中的原菜名或虚构品牌 LOGO。
3. 中部必须是与本菜谱一致的成品菜高清实拍图，食材外观应符合下方内容。
4. 下部清晰呈现“食材”“做法”“小贴士”，并展示分量、时间、难度。
5. 中文文字要端正、易读、信息层级清晰；不得混入参考图里的芹菜炒牛肉内容。
6. 严格使用提供的菜谱事实，不增删主要食材，不改变步骤含义，不显示价格、二维码或联系方式。
7. 输出完整竖版海报，四周保留安全边距，不裁切标题和正文。

以下 JSON 是本次必须使用的菜谱内容：
```json
{content}
```
"""

    @staticmethod
    def _validate_reference(path: Path) -> str | None:
        if not path.exists() or not path.is_file():
            return f"菜谱图片参考图不存在: {path}"
        if path.stat().st_size > 50 * 1024 * 1024:
            return "菜谱图片参考图超过 50MB"
        if RecipeImageGenerator._mime_for_path(path) == "application/octet-stream":
            return "菜谱图片参考图必须是 PNG、JPEG 或 WebP"
        return None

    @staticmethod
    def _mime_for_path(path: Path) -> str:
        suffix = path.suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "application/octet-stream")

    @staticmethod
    def _detect_extension(data: bytes) -> str | None:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if data.startswith(b"\xff\xd8\xff"):
            return "jpg"
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "webp"
        return None
