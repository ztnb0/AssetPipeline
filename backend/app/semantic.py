import json
from functools import lru_cache

import httpx

from .config import settings


SYNONYMS = {
    "对谈": ["访谈", "谈话", "对话", "采访", "交流"],
    "访谈": ["对谈", "谈话", "对话", "采访", "交流"],
    "讲话": ["演讲", "发言", "致辞"],
    "人工智能": ["AI", "智能模型", "机器学习"],
    "AI": ["人工智能", "智能模型", "机器学习"],
    "经济": ["财经", "金融", "商业", "市场"],
    "财经": ["经济", "金融", "商业", "市场"],
    "民生": ["生活", "社会", "居民", "公共服务"],
}


@lru_cache(maxsize=256)
def expand_query(query: str) -> list[str]:
    query = query.strip()
    if not query:
        return []
    terms = [query, *SYNONYMS.get(query, [])]
    prompt = f"""为素材库语义检索扩展查询词。输入：{query}
仅返回 JSON 数组，给出最多8个中文近义词、相关表达或上位概念。不要解释。"""
    headers = {"Content-Type": "application/json"}
    if settings.vision_api_key:
        headers["Authorization"] = f"Bearer {settings.vision_api_key}"
    payload = {
        "model": settings.vision_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 200,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    try:
        with httpx.Client(timeout=20) as client:
            response = client.post(f"{settings.vision_api_base_url.rstrip('/')}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = json.loads(response.content.decode("utf-8"))
        content = data["choices"][0]["message"]["content"].strip().removeprefix("```json").removesuffix("```").strip()
        expanded = json.loads(content)
        if isinstance(expanded, list):
            terms.extend(str(item).strip() for item in expanded)
    except Exception:
        pass
    return list(dict.fromkeys(term for term in terms if term))[:12]
