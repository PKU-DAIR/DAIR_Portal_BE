import json
import re
from pathlib import Path

from json_repair import repair_json
from langchain_openai import ChatOpenAI

from api.agents.promptLoader.prompt_loader import load_prompt
from api.logger import get_logger

from ..state.state import NewsAgentState


logger = get_logger()
CONFIG_PATH = Path(__file__).resolve().parents[3] / "app_config.json"


def load_agent_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as file:
        return json.load(file)


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


def _fallback_pagination_texts(text: str) -> list[str]:
    candidates = ["首页", "上一页", "下一页", "尾页", "上页", "下页", "prev", "previous", "next"]
    found = []
    lower_text = text.lower()
    for item in candidates:
        if item.lower() in lower_text:
            found.append(item)
    for item in re.findall(r"(?:共\s*\d+\s*页|\b\d+\b)", text):
        if item not in found:
            found.append(item)
        if len(found) >= 30:
            break
    return found or candidates


def _clean_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _parse_extraction(content: str) -> tuple[list[str], list[str], list[str]]:
    content = content.strip()
    match = re.search(r"\{[\s\S]*\}", content) or re.search(r"\[[\s\S]*\]", content)
    if match:
        content = match.group(0)
    data = json.loads(repair_json(content))

    if isinstance(data, list):
        return _clean_string_list(data), [], []

    if isinstance(data, dict):
        titles = _clean_string_list(data.get("titles"))
        next_texts = _clean_string_list(data.get("next_page_texts"))
        pagination_texts = _clean_string_list(data.get("pagination_texts"))
        return titles, next_texts, pagination_texts

    return [], [], []


def extract_titles_node(state: NewsAgentState) -> NewsAgentState:
    if state.get("dom_features"):
        logger.info("newsAgent.extract_titles skip; dom_features already learned")
        return {**state, "title_candidates": []}

    text = state.get("page_text", "")
    logger.info("newsAgent.extract_titles start text_chars=%d", len(text))
    config = load_agent_config()
    base_url = config.get("base_url")
    model_name = config.get("model_name")
    api_key = config.get("api_key")
    errors = state.get("errors", [])

    if not (base_url and model_name and api_key):
        titles = _fallback_titles(text)
        next_texts = _fallback_next_page_texts(text)
        pagination_texts = _fallback_pagination_texts(text)
        logger.warning(
            "newsAgent.extract_titles using fallback; missing llm config titles=%d next_texts=%d pagination_texts=%d",
            len(titles),
            len(next_texts),
            len(pagination_texts),
        )
        return {
            **state,
            "title_candidates": titles,
            "next_page_texts": next_texts,
            "pagination_texts": pagination_texts,
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
        titles, next_texts, pagination_texts = _parse_extraction(content)
    except Exception as exc:
        errors.append(f"LLM title extraction failed: {exc}")
        titles = _fallback_titles(text)
        next_texts = _fallback_next_page_texts(text)
        pagination_texts = _fallback_pagination_texts(text)
        logger.warning(
            "newsAgent.extract_titles llm failed; using fallback titles=%d next_texts=%d pagination_texts=%d error=%s",
            len(titles),
            len(next_texts),
            len(pagination_texts),
            exc,
        )

    pagination_texts = pagination_texts[:30] or _fallback_pagination_texts(text)
    logger.info(
        f"newsAgent.extract_titles done titles: \n {json.dumps(titles[:30], ensure_ascii=False, indent=2)} \n next_texts: \n {json.dumps(next_texts[:20], ensure_ascii=False, indent=2)} \n pagination_texts: \n {json.dumps(pagination_texts, ensure_ascii=False, indent=2)}",
    )

    return {
        **state,
        "title_candidates": titles[:30],
        "next_page_texts": next_texts[:20] or _fallback_next_page_texts(text),
        "pagination_texts": pagination_texts,
        "errors": errors,
    }
