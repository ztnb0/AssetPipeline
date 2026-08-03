import base64
import json
import re

import httpx

from .config import settings


PROMPT = """分析这张素材图片，仅输出一个 JSON 对象，不要 Markdown。字段要求：
description：准确简洁的中文画面描述；
tags：5至12个适合素材检索的中文标签数组；
scene：一个具体中文场景，例如“演播室访谈”“城市街道”；
categories：1至3个稳定的题材大类数组，只能从以下选项选择：科技、财经、民生、教育、商业、文化、娱乐、体育、医疗、自然、交通、工业、政务、其他。
不要猜测人物身份，不要添加画面中不存在的信息。"""


def _parse_json(content: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("视觉模型未返回有效 JSON")
        return json.loads(match.group(0))


def analyze_images(images: list[tuple[bytes, str]]) -> dict:
    headers = {"Content-Type": "application/json"}
    if settings.vision_api_key:
        headers["Authorization"] = f"Bearer {settings.vision_api_key}"

    content = []
    for data, mime_type in images[:5]:
        encoded = base64.b64encode(data).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}})
    content.append({"type": "text", "text": PROMPT})
    payload = {
        "model": settings.vision_model,
        "messages": [{
            "role": "user",
            "content": content,
        }],
        "temperature": 0.1,
        "max_tokens": 800,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    with httpx.Client(timeout=120) as http:
        response = http.post(
            f"{settings.vision_api_base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        # The current vLLM endpoint omits a UTF-8 charset in its Content-Type.
        # Decode bytes explicitly so Chinese analysis is not stored as mojibake.
        response_data = json.loads(response.content.decode("utf-8"))
        content = response_data["choices"][0]["message"]["content"]

    result = _parse_json(content)
    tags = result.get("tags", [])
    if not isinstance(tags, list):
        tags = [str(tags)]
    return {
        "description": str(result.get("description", "")).strip(),
        "tags": [str(tag).strip() for tag in tags if str(tag).strip()][:20],
        "scene": str(result.get("scene", "未分类")).strip(),
        "categories": [str(item).strip() for item in (result.get("categories") or [result.get("category", "其他")]) if str(item).strip()][:3],
    }


def analyze_image(data: bytes, mime_type: str) -> dict:
    return analyze_images([(data, mime_type)])


def analyze_text(transcript: str) -> dict:
    prompt = f"""根据下面的音频转写文本生成素材元数据。仅返回合法 JSON，不要 Markdown。
字段：description（中文内容摘要）、tags（8至15个内容检索标签）、scene（具体内容场景）、categories（1至3个题材大类数组）。
题材只能选：科技、财经、民生、教育、商业、文化、娱乐、体育、医疗、自然、交通、工业、政务、其他。
不要编造转写中没有的信息。

转写文本：
{transcript[:30000]}"""
    headers = {"Content-Type": "application/json"}
    if settings.vision_api_key:
        headers["Authorization"] = f"Bearer {settings.vision_api_key}"
    payload = {
        "model": settings.vision_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    with httpx.Client(timeout=120) as http:
        response = http.post(f"{settings.vision_api_base_url.rstrip('/')}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        response_data = json.loads(response.content.decode("utf-8"))
    result = _parse_json(response_data["choices"][0]["message"]["content"])
    tags = result.get("tags") or []
    categories = result.get("categories") or ["其他"]
    return {
        "description": str(result.get("description", "")).strip(),
        "tags": [str(tag).strip() for tag in tags if str(tag).strip()][:20],
        "scene": str(result.get("scene", "音频内容")).strip(),
        "categories": [str(item).strip() for item in categories if str(item).strip()][:3] or ["其他"],
    }
