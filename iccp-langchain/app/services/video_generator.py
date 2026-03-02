"""
剧情润色与文生视频生成服务（Seedance 专用协议适配）。
"""
import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from openai import AsyncOpenAI

from app.config import settings


ALLOWED_GENRES = {"sci-fi", "suspense", "healing", "business", "fantasy", "documentary"}
ALLOWED_MOODS = {"epic", "warm", "dark", "hopeful", "tense"}
ALLOWED_ASPECT_RATIOS = {"21:9", "16:9", "9:16", "4:3", "3:4", "1:1", "adaptive"}
ALLOWED_RESOLUTIONS = {"480p", "720p", "1080p"}
DEFAULT_SEEDANCE_BASE_URL = "https://operator.las.cn-beijing.volces.com"

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "expired"}
SEEDANCE_PROGRESS_MAP = {
    "queued": 15,
    "running": 65,
    "succeeded": 100,
    "failed": 100,
    "cancelled": 100,
    "expired": 100,
}

_LOCAL_VIDEO_CACHE: Dict[str, str] = {}


class VideoGenerationError(Exception):
    """视频生成业务异常"""


def _normalize_param(value: str, allowed: set[str], default: str) -> str:
    if not value:
        return default
    value = value.strip().lower()
    return value if value in allowed else default


def _extract_json_block(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    snippet = text[start:end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return {}


def _seedance_api_key() -> str:
    api_key = (settings.SEEDANCE_API_KEY or settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        raise VideoGenerationError("未配置 SEEDANCE_API_KEY（或 OPENAI_API_KEY）")
    return api_key


def _seedance_base_url() -> str:
    return (settings.SEEDANCE_BASE_URL or DEFAULT_SEEDANCE_BASE_URL).rstrip("/")


async def _polish_story(
    input_text: str,
    genre: str,
    mood: str,
    duration_seconds: int,
    extra_requirements: str,
    memory_context_text: str = "",
) -> Dict[str, Any]:
    if not settings.OPENAI_API_KEY:
        raise VideoGenerationError("未配置 OPENAI_API_KEY，无法进行剧情润色")

    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.LLM_BASE_URL if settings.LLM_BASE_URL != "https://api.openai.com/v1" else None,
        timeout=settings.LLM_TIMEOUT,
    )

    system_prompt = (
        "你是影视分镜编剧。请将用户输入润色为可用于文生视频的剧情。"
        "输出必须是 JSON，字段包括：title, storyline, visual_style, shots。"
        "其中 shots 是数组，每个元素需包含 scene, camera, action, lighting。"
    )
    user_prompt = (
        f"原始输入：{input_text}\n"
        f"剧情类型：{genre}\n"
        f"情绪基调：{mood}\n"
        f"目标时长：{duration_seconds} 秒\n"
        f"额外要求：{extra_requirements or '无'}\n"
        f"可参考的历史记忆：{memory_context_text or '无'}\n"
        "请输出紧凑但具体、可视化强的剧情与镜头。"
    )

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=min(max(settings.LLM_TEMPERATURE, 0.2), 1.0),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        raise VideoGenerationError(f"剧情润色调用失败: {exc}") from exc

    content = (response.choices[0].message.content or "").strip() if response.choices else ""
    parsed = _extract_json_block(content)
    storyline = (parsed.get("storyline") or content).strip()
    title = (parsed.get("title") or input_text[:30]).strip()
    visual_style = (parsed.get("visual_style") or f"{genre}, {mood}").strip()
    shots = parsed.get("shots") if isinstance(parsed.get("shots"), list) else []

    return {
        "title": title,
        "storyline": storyline,
        "visual_style": visual_style,
        "shots": shots,
    }


def _build_video_prompt(
    story_data: Dict[str, Any], aspect_ratio: str, duration_seconds: int, extra_requirements: str
) -> str:
    shots = story_data.get("shots", [])
    shot_lines = []
    for shot in shots[:4]:
        if not isinstance(shot, dict):
            continue
        scene = (shot.get("scene") or "").strip()
        camera = (shot.get("camera") or "").strip()
        action = (shot.get("action") or "").strip()
        lighting = (shot.get("lighting") or "").strip()
        combined = ", ".join([x for x in [scene, camera, action, lighting] if x])
        if combined:
            shot_lines.append(combined)
    shot_text = " | ".join(shot_lines)

    return (
        f"Create a high-quality cinematic short video. "
        f"Title: {story_data.get('title', '')}. "
        f"Storyline: {story_data.get('storyline', '')}. "
        f"Visual style: {story_data.get('visual_style', '')}. "
        f"Key shots: {shot_text}. "
        f"Duration: {duration_seconds}s. Aspect ratio: {aspect_ratio}. "
        f"Additional requirements: {extra_requirements or 'none'}. "
        "No text overlay, no watermark, no subtitles, no distortion."
    ).strip()


def _save_video_bytes(video_bytes: bytes) -> str:
    static_dir = Path(settings.BASE_DIR) / "static" / "generated-videos"
    static_dir.mkdir(parents=True, exist_ok=True)

    filename = f"video_{uuid.uuid4().hex}.mp4"
    output_path = static_dir / filename
    output_path.write_bytes(video_bytes)
    return f"/static/generated-videos/{filename}"


async def _download_video_if_needed(task_id: str, video_url: str) -> str:
    if not video_url:
        return video_url
    if not settings.VIDEO_SAVE_LOCAL:
        return video_url
    if task_id in _LOCAL_VIDEO_CACHE:
        return _LOCAL_VIDEO_CACHE[task_id]

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(video_url)
    resp.raise_for_status()
    local_url = _save_video_bytes(resp.content)
    _LOCAL_VIDEO_CACHE[task_id] = local_url
    return local_url


def _map_progress(status: str) -> int:
    return SEEDANCE_PROGRESS_MAP.get(status, 30)


def _extract_error_message(data: Dict[str, Any]) -> Optional[str]:
    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    if isinstance(error, str) and error.strip():
        return error.strip()
    return None


async def create_story_video_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    input_text = (payload.get("input_text") or "").strip()
    if not input_text:
        raise VideoGenerationError("输入文本不能为空")

    genre = _normalize_param(payload.get("genre", "sci-fi"), ALLOWED_GENRES, "sci-fi")
    mood = _normalize_param(payload.get("mood", "epic"), ALLOWED_MOODS, "epic")
    aspect_ratio = _normalize_param(payload.get("aspect_ratio", "16:9"), ALLOWED_ASPECT_RATIOS, "16:9")
    resolution = _normalize_param(payload.get("resolution", "720p"), ALLOWED_RESOLUTIONS, "720p")

    duration_seconds = int(payload.get("duration_seconds") or 8)
    if duration_seconds < 2 or duration_seconds > 12:
        raise VideoGenerationError("duration_seconds 必须在 2~12 之间（Seedance 限制）")

    model = (payload.get("model") or settings.VIDEO_MODEL or "doubao-seedance-1-0-pro-fast-251015").strip()
    provider = (payload.get("provider") or settings.VIDEO_PROVIDER or "mock").strip().lower()
    extra_requirements = (payload.get("extra_requirements") or "").strip()
    start = time.perf_counter()

    try:
        story_data = await asyncio.wait_for(
            _polish_story(
                input_text=input_text,
                genre=genre,
                mood=mood,
                duration_seconds=duration_seconds,
                extra_requirements=extra_requirements,
                memory_context_text=(payload.get("memory_context_text") or "").strip(),
            ),
            timeout=max(3, settings.VIDEO_POLISH_TIMEOUT_SECONDS),
        )
    except asyncio.TimeoutError as exc:
        raise VideoGenerationError(
            f"剧情润色超时（>{max(3, settings.VIDEO_POLISH_TIMEOUT_SECONDS)}秒），请缩短输入或稍后重试"
        ) from exc
    prompt = _build_video_prompt(story_data, aspect_ratio, duration_seconds, extra_requirements)

    if provider == "mock":
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "success": True,
            "storyline": story_data.get("storyline", ""),
            "video_prompt": prompt,
            "task_id": None,
            "status": "mocked",
            "progress_percent": 100,
            "video_url": None,
            "provider": provider,
            "model": model,
            "latency_ms": latency_ms,
        }

    if provider != "seedance":
        raise VideoGenerationError("当前仅支持 seedance（或 mock）provider")

    api_key = _seedance_api_key()
    base_url = _seedance_base_url()
    url = f"{base_url}/api/v1/contents/generations/tasks"

    body: Dict[str, Any] = {
        "model": model,
        "content": [{"type": "text", "text": prompt}],
        "ratio": aspect_ratio,
        "duration": duration_seconds,
        "resolution": resolution,
        "watermark": bool(payload.get("watermark", False)),
        "camera_fixed": bool(payload.get("camera_fixed", False)),
    }

    if payload.get("seed") is not None and str(payload.get("seed")).strip() != "":
        body["seed"] = int(payload.get("seed"))
    if payload.get("generate_audio") is not None:
        body["generate_audio"] = bool(payload.get("generate_audio"))
    if payload.get("return_last_frame") is not None:
        body["return_last_frame"] = bool(payload.get("return_last_frame"))
    if payload.get("execution_expires_after") is not None:
        body["execution_expires_after"] = int(payload.get("execution_expires_after"))
    if payload.get("draft") is not None:
        body["draft"] = bool(payload.get("draft"))
    if payload.get("callback_url"):
        body["callback_url"] = str(payload.get("callback_url")).strip()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.VIDEO_TIMEOUT) as client:
        resp = await client.post(url, headers=headers, json=body)

    if resp.status_code >= 400:
        raise VideoGenerationError(f"Seedance 任务创建失败 ({resp.status_code}): {resp.text}")
    data = resp.json()
    task_id = data.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise VideoGenerationError(f"Seedance 返回中缺少任务 id，原始响应: {data}")

    latency_ms = int((time.perf_counter() - start) * 1000)
    return {
        "success": True,
        "storyline": story_data.get("storyline", ""),
        "video_prompt": prompt,
        "task_id": task_id,
        "status": "queued",
        "progress_percent": 10,
        "video_url": None,
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
    }


async def query_story_video_task(task_id: str, provider: str = "seedance") -> Dict[str, Any]:
    if not task_id.strip():
        raise VideoGenerationError("task_id 不能为空")

    provider = (provider or "seedance").strip().lower()
    if provider == "mock":
        return {
            "success": True,
            "task_id": task_id,
            "status": "mocked",
            "progress_percent": 100,
            "video_url": None,
            "error": None,
        }
    if provider != "seedance":
        raise VideoGenerationError("当前仅支持 seedance（或 mock）provider")

    api_key = _seedance_api_key()
    base_url = _seedance_base_url()
    url = f"{base_url}/api/v1/contents/generations/tasks/{task_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, headers=headers)

    if resp.status_code >= 400:
        raise VideoGenerationError(f"Seedance 任务查询失败 ({resp.status_code}): {resp.text}")

    data = resp.json()
    status = str(data.get("status", "queued")).lower()
    error_message = _extract_error_message(data)
    content = data.get("content") if isinstance(data.get("content"), dict) else {}
    remote_video_url = content.get("video_url") if isinstance(content.get("video_url"), str) else None
    video_url = await _download_video_if_needed(task_id, remote_video_url) if remote_video_url else None

    result = {
        "success": status not in {"failed", "cancelled", "expired"},
        "task_id": data.get("id", task_id),
        "status": status,
        "progress_percent": _map_progress(status),
        "video_url": video_url,
        "last_frame_url": content.get("last_frame_url"),
        "error": error_message,
        "raw_status": data.get("status"),
        "updated_at": data.get("updated_at"),
        "created_at": data.get("created_at"),
    }

    if status in {"failed", "cancelled", "expired"} and not result["error"]:
        result["error"] = f"任务状态为 {status}"
    return result


async def generate_story_video(payload: Dict[str, Any]) -> Dict[str, Any]:
    start_result = await create_story_video_task(payload)
    task_id = start_result.get("task_id")
    status = (start_result.get("status") or "").lower()

    if not task_id or status == "mocked":
        return start_result

    begin = time.perf_counter()
    while (time.perf_counter() - begin) < settings.VIDEO_TIMEOUT:
        task_result = await query_story_video_task(task_id, provider=start_result.get("provider", "seedance"))
        task_status = (task_result.get("status") or "").lower()
        if task_status in TERMINAL_STATUSES:
            return {
                **start_result,
                "success": task_result.get("success", False),
                "video_url": task_result.get("video_url"),
                "status": task_status,
                "progress_percent": task_result.get("progress_percent", 100),
                "error": task_result.get("error"),
            }
        await asyncio.sleep(max(1, settings.VIDEO_POLL_INTERVAL))

    raise VideoGenerationError("等待视频生成超时")
