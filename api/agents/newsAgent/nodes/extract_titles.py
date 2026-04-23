import json
import re

from json_repair import repair_json
from langchain_openai import ChatOpenAI

from api.agents.promptLoader.prompt_loader import load_prompt

from .config import load_agent_config
from .state import NewsAgentState


def _fallback_titles(text: str) -> list[str]:
    titles = []
    seen = set()

    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not 8 <= len(line) <= 160:
            continue
        if re.fullmatch(r"[\d\s./:-]+", line):
            continue
        if line.lower() in {"home", "news", "next", "previous", "more"}:
            continue
        if line not in seen:
            seen.add(line)
            titles.append(line)
        if len(titles) >= 30:
            break

    return titles


def _fallback_next_page_texts(text: str) -> list[str]:
    candidates = ["下一页", "下页", "next", ">", "›", "»"]
    lower_text = text.lower()
    return [item for item in candidates if item.lower() in lower_text] or candidates


def _clean_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _parse_extraction(content: str) -> tuple[list[str], list[str]]:
    content = content.strip()
    match = re.search(r"\{[\s\S]*\}", content) or re.search(r"\[[\s\S]*\]", content)
    if match:
        content = match.group(0)
    data = json.loads(repair_json(content))

    if isinstance(data, list):
        return _clean_string_list(data), []

    if isinstance(data, dict):
        titles = _clean_string_list(data.get("titles"))
        next_texts = _clean_string_list(data.get("next_page_texts"))
        return titles, next_texts

    return [], []


def extract_titles_node(state: NewsAgentState) -> NewsAgentState:
    if state.get("dom_features"):
        return {**state, "title_candidates": []}

    text = state.get("page_text", "")
    config = load_agent_config()
    base_url = config.get("base_url")
    model_name = config.get("model_name")
    api_key = config.get("api_key")
    errors = state.get("errors", [])

    if not (base_url and model_name and api_key):
        return {
            **state,
            "title_candidates": _fallback_titles(text),
            "next_page_texts": _fallback_next_page_texts(text),
        }

    try:
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0,
        )
        response = llm.invoke(
            [
                ("system", load_prompt("extract_news_titles")),
                ("user", text[:12000]),
            ]
        )
        content = response.content or "[]"
        titles, next_texts = _parse_extraction(content)
    except Exception as exc:
        errors.append(f"LLM title extraction failed: {exc}")
        titles = _fallback_titles(text)
        next_texts = _fallback_next_page_texts(text)

    return {
        **state,
        "title_candidates": titles[:30],
        "next_page_texts": next_texts[:20] or _fallback_next_page_texts(text),
        "errors": errors,
    }
