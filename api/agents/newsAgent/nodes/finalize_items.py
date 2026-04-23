import json
import re
from pathlib import Path
from urllib.parse import urljoin

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


def _strip_html(item: dict) -> dict:
    return {key: value for key, value in item.items() if key != "html"}


def _parse_items(content: str) -> list[dict]:
    content = content.strip()
    match = re.search(r"\[[\s\S]*\]", content)
    if match:
        content = match.group(0)
    data = json.loads(repair_json(content))
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _absolute_url(source_page: str, value: str) -> str:
    if not value:
        return ""
    return urljoin(source_page, value)


def _build_cards_payload(cards: list[dict]) -> str:
    compact_cards = []
    for index, card in enumerate(cards):
        compact_cards.append(
            {
                "index": index,
                "source_page": card.get("source_page", ""),
                "detected_title": card.get("title", ""),
                "detected_published_at": card.get("published_at", ""),
                "detected_link": card.get("link", ""),
                "detected_image": card.get("image", ""),
                "html": (card.get("html") or "")[:3000],
                "text": (card.get("text") or "")[:1000],
            }
        )
    return json.dumps(compact_cards, ensure_ascii=False)


def _merge_with_fallback(items: list[dict], raw_cards: list[dict]) -> list[dict]:
    merged = []
    for fallback_index, item in enumerate(items):
        index = item.get("index", fallback_index)
        if not isinstance(index, int):
            index = fallback_index
        fallback = raw_cards[index] if index < len(raw_cards) else {}
        title = item.get("title") or fallback.get("title")
        if not title:
            continue
        source_page = item.get("source_page") or fallback.get("source_page", "")
        merged.append(
            {
                "title": title,
                "published_at": item.get("published_at") or fallback.get("published_at", ""),
                "link": _absolute_url(source_page, item.get("link") or fallback.get("link", "")),
                "image": _absolute_url(source_page, item.get("image") or fallback.get("image", "")),
                "source_page": source_page,
            }
        )
    return merged


def finalize_items_node(state: NewsAgentState) -> NewsAgentState:
    raw_cards = state.get("raw_cards", state.get("items", []))
    fallback_items = [_strip_html(item) for item in raw_cards]
    errors = state.get("errors", [])
    logger.info("newsAgent.finalize_items start raw_cards=%d", len(raw_cards))

    if not raw_cards:
        logger.warning("newsAgent.finalize_items no raw cards")
        return {**state, "items": []}

    config = load_agent_config()
    base_url = config.get("base_url")
    model_name = config.get("model_name")
    api_key = config.get("api_key")

    if not (base_url and model_name and api_key):
        logger.warning(
            "newsAgent.finalize_items using fallback; missing llm config items=%d",
            len(fallback_items),
        )
        return {**state, "items": fallback_items}

    try:
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0,
        )
        response = llm.invoke(
            [
                ("system", load_prompt("extract_news_items")),
                ("user", _build_cards_payload(raw_cards)),
            ]
        )
        items = _merge_with_fallback(_parse_items(response.content or "[]"), raw_cards)
    except Exception as exc:
        errors.append(f"LLM item extraction failed: {exc}")
        items = fallback_items
        logger.warning(
            "newsAgent.finalize_items llm failed; using fallback items=%d error=%s",
            len(items),
            exc,
        )

    logger.info(
        "newsAgent.finalize_items done items=%d fallback_items=%d",
        len(items or fallback_items),
        len(fallback_items),
    )

    return {
        **state,
        "items": items or fallback_items,
        "errors": errors,
    }
