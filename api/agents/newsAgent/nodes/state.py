from typing import Any, TypedDict


class NewsAgentState(TypedDict, total=False):
    start_url: str
    current_url: str
    max_pages: int
    visited_urls: list[str]
    page_text: str
    title_candidates: list[str]
    next_page_texts: list[str]
    dom_features: dict[str, Any]
    page_items: list[dict[str, Any]]
    raw_cards: list[dict[str, Any]]
    items: list[dict[str, Any]]
    next_url: str | None
    errors: list[str]
