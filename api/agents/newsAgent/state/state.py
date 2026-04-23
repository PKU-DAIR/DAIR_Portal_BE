from typing import Any, TypedDict


class NewsAgentState(TypedDict, total=False):
    # Original entry URL and the current graph cursor. `current_url` may be a
    # real URL or an internal synthetic marker for JS/SPA pagination.
    start_url: str
    current_url: str
    max_pages: int
    visited_urls: list[str]

    # Current page snapshot. `page_html` lets later nodes evaluate DOM scripts
    # against exactly the clicked/paginated page instead of reopening page 1.
    page_text: str
    page_html: str

    # A clicked pagination page is passed to the next loop through these fields.
    # `fetch_page_node` consumes them and clears them.
    pending_page_text: str
    pending_page_html: str

    # When pagination is implemented by JS with no stable URL, we replay the
    # chosen candidate indices from `start_url` to restore the same runtime page.
    pagination_click_indices: list[int]

    # LLM-derived clues from the first page. Card extraction reuses DOM features
    # after the first page, so later loops usually skip title extraction.
    title_candidates: list[str]
    next_page_texts: list[str]
    pagination_texts: list[str]

    # Learned card selectors/XPath patterns produced by `extract_cards.js`.
    dom_features: dict[str, Any]

    # `raw_cards` stores card HTML/text across pages; final LLM extraction turns
    # these into normalized news items.
    page_items: list[dict[str, Any]]
    raw_cards: list[dict[str, Any]]
    items: list[dict[str, Any]]
    next_url: str | None
    errors: list[str]
