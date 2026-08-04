import base64
import json
import re

import httpx

from .config import settings


TOPIC_CATEGORIES = "科技、财经、金融市场、宏观经济、金融理财、投资管理、保险规划、养老规划、税务规划、财富传承、私人银行、金融教育、财经新闻、民生、教育、商业、文化、娱乐、体育、医疗、自然、交通、工业、政务、其他"


IMAGE_PROMPT = f"""你是专业的视频素材编目员。分析这张素材图片，仅输出一个合法 JSON 对象，不要 Markdown。
字段要求：
description：用 2 至 3 句中文描述可直接观察到的事实，包括人物数量、动作、关键物体、环境和画面文字；不要编造身份、品牌、认证资格、金融结论或人物意图；
tags：生成 8 至 15 个中文检索标签，覆盖主体、动作、对象、场景和合理用途，禁止“素材、图片、画面、高清”等空泛词；
scene：用“地点/环境 + 活动 + 业务目的”描述具体场景，例如“办公室内理财顾问与客户讨论资产配置”，不要只写“办公室”；
categories：选择 1 至 3 个稳定题材，只能从：{TOPIC_CATEGORIES}；
不要把普通商务人士直接判断为 AFP、CFP、EFP、CERTIFIED PRIVATE BANKER 或其他专业身份。只有画面明确出现认证名称/Logo，或可信来源元数据明确标注时，才可以使用对应认证标签。"""


VIDEO_PROMPT = f"""你是专业的视频素材编目员。下面的图片按时间顺序来自同一段视频，仅输出一个合法 JSON 对象，不要 Markdown。
请先为每一帧生成独立描述，再结合全部帧生成整段视频的元数据。不要把不同时间出现的同一个人重复计算。
JSON 字段要求：
frame_analysis：数组，每项包含 timestamp（时间点）和 description（该帧可观察到的中文画面描述）；
description：用 2 至 3 句中文概括整段视频的主要内容和连续动作，不要只描述某一帧；
tags：8 至 15 个中文检索标签，包含视频中持续出现或关键出现的主体、动作和主题，禁止“素材、视频、画面、高清”等空泛词；
scene：描述视频最主要的场景，使用“地点/环境 + 活动 + 业务目的”，例如“财经演播室主持人解读市场走势”；
categories：选择 1 至 3 个稳定题材，只能从：{TOPIC_CATEGORIES}；
不要编造人物身份、品牌、认证资格、金融结论或人物意图。只有明确可见或可信来源明确标注，才可以使用 AFP、CFP、EFP、CERTIFIED PRIVATE BANKER 等认证标签。"""


def _parse_json(content: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("视觉模型未返回有效 JSON")
        return json.loads(match.group(0))


def analyze_images(
    images: list[tuple[bytes, str]],
    frame_times: list[float] | None = None,
    asset_context: str | None = None,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if settings.vision_api_key:
        headers["Authorization"] = f"Bearer {settings.vision_api_key}"

    content = []
    selected_images = images[:5]
    for index, (data, mime_type) in enumerate(selected_images):
        if frame_times and index < len(frame_times):
            content.append({"type": "text", "text": f"第 {index + 1} 帧，时间点 {frame_times[index]:.2f} 秒。"})
        encoded = base64.b64encode(data).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}})
    prompt = VIDEO_PROMPT if frame_times and len(selected_images) > 1 else IMAGE_PROMPT
    if asset_context:
        prompt += f"\n\n素材来源上下文仅供参考，不能替代画面证据：{asset_context[:1000]}"
    content.append({"type": "text", "text": prompt})
    payload = {
        "model": settings.vision_model,
        "messages": [{
            "role": "user",
            "content": content,
        }],
        "temperature": 0.1,
        "max_tokens": 1400 if frame_times else 900,
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
    cleaned_tags = []
    for tag in tags:
        value = str(tag).strip()
        if value and value not in cleaned_tags:
            cleaned_tags.append(value)
    raw_categories = result.get("categories") or [result.get("category", "其他")]
    if not isinstance(raw_categories, list):
        raw_categories = [raw_categories]
    cleaned_categories = []
    for category in raw_categories:
        value = str(category).strip()
        if value and value in TOPIC_CATEGORIES.split("、") and value not in cleaned_categories:
            cleaned_categories.append(value)
    if not cleaned_categories:
        cleaned_categories = ["其他"]
    output = {
        "description": str(result.get("description", "")).strip(),
        "tags": cleaned_tags[:20],
        "scene": str(result.get("scene", "未分类")).strip(),
        "categories": cleaned_categories[:3],
    }
    if frame_times:
        frame_analysis = result.get("frame_analysis") or []
        if not isinstance(frame_analysis, list):
            frame_analysis = []
        normalized_frames = []
        for index, frame_time in enumerate(frame_times[:len(selected_images)]):
            item = frame_analysis[index] if index < len(frame_analysis) and isinstance(frame_analysis[index], dict) else {}
            normalized_frames.append({
                "timestamp": round(frame_time, 2),
                "description": str(item.get("description", "")).strip() or "该时间点画面未生成描述",
            })
        output["frame_analysis"] = normalized_frames
    return output


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
