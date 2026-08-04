import json
import re
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


def expand_from_assets(query: str, corpus: list[str]) -> list[str]:
    """Return only phrases that occur verbatim in the matching asset metadata."""
    query = query.strip()
    values = list(dict.fromkeys(str(value).strip() for value in corpus if str(value).strip()))
    if not query or not values:
        return []

    joined = "\n".join(values)
    candidates: list[str] = []

    # Tags, scenes, and short metadata values are already useful search phrases.
    for value in values:
        if query in value and 2 <= len(value) <= 24 and value != query:
            candidates.append(value)
        for phrase in re.split(r"[，。；、：！？\s（）()“”\"《》|]+", value):
            phrase = phrase.strip()
            if query not in phrase or phrase == query:
                continue
            if 2 <= len(phrase) <= 16:
                candidates.append(phrase)

    prompt = f"""从下面的素材库元数据中，为查询词“{query}”摘取最多 10 个相关短语。
要求：
1. 每个短语必须逐字出现在素材元数据原文中，不得改写、联想或补充通用近义词；
2. 优先选择标签、场景、标题和包含查询词的具体名称，例如“皇帝的嫁衣”“皇帝的新装”；
3. 每项 2 至 16 个字符，不要返回“全部、完整、齐全”等空泛词；
4. 仅返回 JSON 字符串数组，不要解释。

素材元数据：
{joined[:20000]}"""
    headers = {"Content-Type": "application/json"}
    if settings.vision_api_key:
        headers["Authorization"] = f"Bearer {settings.vision_api_key}"
    payload = {
        "model": settings.vision_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 300,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    try:
        with httpx.Client(timeout=20) as client:
            response = client.post(
                f"{settings.vision_api_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = json.loads(response.content.decode("utf-8"))
        content = data["choices"][0]["message"]["content"].strip().removeprefix("```json").removesuffix("```").strip()
        extracted = json.loads(content)
        if isinstance(extracted, list):
            candidates = [str(item).strip() for item in extracted] + candidates
    except Exception:
        pass

    blocked = {query, "全部", "整体", "完整无缺", "完备", "齐全", "充分", "彻底", "全貌"}
    grounded = [
        term for term in candidates
        if term not in blocked and 2 <= len(term) <= 24 and term in joined
    ]
    return list(dict.fromkeys(grounded))[:12]
