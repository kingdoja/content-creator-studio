"""
标题封面图生成服务
支持 OpenAI Images API 与阿里云 DashScope（通义千问 / Qwen-Image）文生图。
"""
import asyncio
import base64
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

import httpx
from openai import AsyncOpenAI

from app.config import settings


ALLOWED_STYLES = {"cinematic", "minimal", "illustration", "3d", "photography", "cyberpunk"}
ALLOWED_TONES = {"warm", "cool", "dark", "bright", "pastel"}
ALLOWED_SIZES = {"1536x1024", "1024x1024", "1024x1536"}
ALLOWED_QUALITY = {"high", "medium", "low"}

# 通义千问文生图模型（DashScope 原生 API）
DASHSCOPE_IMAGE_MODELS = {"qwen-image", "qwen-image-plus", "qwen-image-max"}
DASHSCOPE_IMAGE_API = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
DASHSCOPE_TASKS_API = "https://dashscope.aliyuncs.com/api/v1/tasks"


class CoverGenerationError(Exception):
    """封面图生成业务异常"""


def _normalize_param(value: str, allowed: set[str], default: str) -> str:
    if not value:
        return default
    value = value.strip().lower()
    return value if value in allowed else default


def build_cover_prompt(
    title: str,
    category: str = "",
    style: str = "cinematic",
    tone: str = "bright",
    avoid_text: bool = True,
) -> str:
    safe_title = title.strip()
    safe_category = (category or "").strip()
    safe_style = _normalize_param(style, ALLOWED_STYLES, "cinematic")
    safe_tone = _normalize_param(tone, ALLOWED_TONES, "bright")

    text_rule = "Do not include any text, letters, numbers, logos, or watermarks in the image." if avoid_text else ""
    category_hint = f"Topic category: {safe_category}." if safe_category else ""

    return (
        "Create a premium editorial cover image for an online article. "
        f"Article title: {safe_title}. "
        f"{category_hint} "
        f"Visual style: {safe_style}. "
        f"Color tone: {safe_tone}. "
        "Composition should be clean, modern, high-contrast, and visually striking, "
        "with a strong focal point and cinematic lighting. "
        "No low quality artifacts, no cluttered layout, no distorted anatomy. "
        f"{text_rule}"
    ).strip()


def _save_image_bytes(image_bytes: bytes) -> str:
    static_dir = Path(settings.BASE_DIR) / "static" / "generated-covers"
    static_dir.mkdir(parents=True, exist_ok=True)

    filename = f"cover_{uuid.uuid4().hex}.png"
    output_path = static_dir / filename
    output_path.write_bytes(image_bytes)
    return f"/static/generated-covers/{filename}"


def _is_dashscope_image() -> bool:
    """是否使用阿里云 DashScope 文生图（通义千问 / Qwen-Image）"""
    base = (settings.LLM_BASE_URL or "").strip().lower()
    model = (settings.IMAGE_MODEL or "").strip().lower()
    return "dashscope" in base and model in DASHSCOPE_IMAGE_MODELS


def _dashscope_size(size: str) -> str:
    """将 1536x1024 转为 DashScope 要求的 1536*1024"""
    return size.replace("x", "*")


def _extract_image_url_from_output(output: dict) -> Optional[str]:
    """从 DashScope output 中解析出图片 URL。兼容 choices / results / image_urls / data 等结构。"""
    # 1) output.choices[0].message.content（Qwen-Image 常见返回格式）
    choices = output.get("choices") or []
    if choices:
        msg = (choices[0] or {}).get("message") or {}
        content = msg.get("content")
        if isinstance(content, str) and content.strip().startswith("http"):
            return content.strip()
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    u = part.get("image") or part.get("url") or part.get("image_url")
                    if u and isinstance(u, str):
                        return u
                if isinstance(part, str) and part.strip().startswith("http"):
                    return part.strip()
        if isinstance(content, dict):
            u = content.get("image") or content.get("url") or content.get("image_url")
            if u:
                return u

    # 2) output.results / image_urls / data（异步任务或其它接口）
    for key in ("results", "image_urls", "data"):
        items = output.get(key) or []
        if not items:
            continue
        first = items[0]
        if isinstance(first, str) and first.startswith("http"):
            return first
        if isinstance(first, dict):
            u = first.get("url") or first.get("image_url") or first.get("image")
            if u:
                return u
    return None


async def _dashscope_poll_task(api_key: str, task_id: str, timeout_sec: int = 120) -> str:
    """轮询 DashScope 异步任务，返回图片 URL。"""
    url = f"{DASHSCOPE_TASKS_API}/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    start = time.perf_counter()
    while (time.perf_counter() - start) < timeout_sec:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            raise CoverGenerationError(f"查询任务失败 ({resp.status_code}): {resp.text}")
        data = resp.json()
        if data.get("code"):
            raise CoverGenerationError(data.get("message", "查询任务返回错误"))
        output = data.get("output") or {}
        status = (output.get("task_status") or "").upper()
        if status == "SUCCEEDED":
            image_url = _extract_image_url_from_output(output)
            if image_url:
                return image_url
            raise CoverGenerationError("任务成功但未包含图片地址")
        if status in ("FAILED", "CANCELED"):
            raise CoverGenerationError(output.get("message") or f"任务失败: {status}")
        await asyncio.sleep(2)
    raise CoverGenerationError("等待任务结果超时")


async def _generate_cover_dashscope(prompt: str, size: str) -> tuple[str, int]:
    """调用 DashScope 原生文生图 API，返回 (本地图片 URL, 耗时 ms)。支持同步返回与 task_id 异步轮询。"""
    api_key = settings.OPENAI_API_KEY
    model = settings.IMAGE_MODEL or "qwen-image-max"
    dash_size = _dashscope_size(size)

    body = {
        "model": model,
        "input": {
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ]
        },
        "parameters": {"size": dash_size},
    }

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
        resp = await client.post(
            DASHSCOPE_IMAGE_API,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
    first_ms = int((time.perf_counter() - start) * 1000)

    if resp.status_code != 200:
        msg = resp.text or resp.reason_phrase
        raise CoverGenerationError(f"DashScope 文生图请求失败 ({resp.status_code}): {msg}")

    data = resp.json()
    if data.get("code"):
        raise CoverGenerationError(data.get("message", "DashScope 返回错误"))

    output = data.get("output") or {}
    task_id = output.get("task_id")

    if task_id:
        # 异步任务：轮询直到完成
        image_url = await _dashscope_poll_task(api_key, task_id)
    else:
        image_url = _extract_image_url_from_output(output)

    if not image_url:
        keys = list(output.keys()) if output else list(data.keys())
        raise CoverGenerationError(f"DashScope 返回数据为空（output 键: {keys}）")

    # 阿里云返回的 URL 有时效，下载到本地再返回本地路径
    async with httpx.AsyncClient(timeout=30) as client:
        img_resp = await client.get(image_url)
        img_resp.raise_for_status()
        image_bytes = img_resp.content

    local_url = _save_image_bytes(image_bytes)
    latency_ms = int((time.perf_counter() - start) * 1000)
    return local_url, latency_ms


async def generate_cover_image(payload: Dict) -> Dict:
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise CoverGenerationError("未配置 OPENAI_API_KEY，无法生成封面图")

    title = (payload.get("title") or "").strip()
    if not title:
        raise CoverGenerationError("标题不能为空")

    size = _normalize_param(payload.get("size", "1536x1024"), ALLOWED_SIZES, "1536x1024")
    quality = _normalize_param(payload.get("quality", "high"), ALLOWED_QUALITY, "high")
    style = payload.get("style", "cinematic")
    tone = payload.get("tone", "bright")
    category = payload.get("category", "")
    avoid_text = bool(payload.get("avoid_text", True))

    prompt = build_cover_prompt(
        title=title,
        category=category,
        style=style,
        tone=tone,
        avoid_text=avoid_text,
    )

    # 通义千问 / 阿里云 DashScope：使用原生文生图 API（Qwen-Image）
    if _is_dashscope_image():
        try:
            image_url, latency_ms = await _generate_cover_dashscope(prompt, size)
        except CoverGenerationError:
            raise
        except Exception as exc:
            raise CoverGenerationError(f"图像模型调用失败: {exc}") from exc
        return {
            "success": True,
            "image_url": image_url,
            "prompt_used": prompt,
            "model": settings.IMAGE_MODEL,
            "latency_ms": latency_ms,
        }

    # OpenAI 或其它兼容 OpenAI Images API 的厂商
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=settings.LLM_BASE_URL if settings.LLM_BASE_URL != "https://api.openai.com/v1" else None,
        timeout=settings.LLM_TIMEOUT,
    )

    start = time.perf_counter()
    try:
        response = await client.images.generate(
            model=settings.IMAGE_MODEL,
            prompt=prompt,
            size=size,
            quality=quality,
        )
    except Exception as exc:
        raise CoverGenerationError(f"图像模型调用失败: {exc}") from exc

    latency_ms = int((time.perf_counter() - start) * 1000)
    if not response.data:
        raise CoverGenerationError("图像生成失败：返回数据为空")

    image_data = response.data[0]
    image_url = getattr(image_data, "url", None)
    b64_json = getattr(image_data, "b64_json", None)

    if b64_json:
        try:
            image_bytes = base64.b64decode(b64_json)
            image_url = _save_image_bytes(image_bytes)
        except Exception as exc:
            raise CoverGenerationError(f"图片保存失败: {exc}") from exc

    if not image_url:
        raise CoverGenerationError("图像生成失败：未返回可用图片地址")

    return {
        "success": True,
        "image_url": image_url,
        "prompt_used": prompt,
        "model": settings.IMAGE_MODEL,
        "latency_ms": latency_ms,
    }
