from typing import Iterable, Literal

from langgraph.graph import END, StateGraph

from api.agents.newsAgent.nodes.extract_cards import extract_cards_node
from api.agents.newsAgent.nodes.extract_titles import extract_titles_node
from api.agents.newsAgent.nodes.fetch_page import fetch_page_node
from api.agents.newsAgent.nodes.finalize_items import finalize_items_node
from api.agents.newsAgent.nodes.find_next_page import find_next_page_node
from api.agents.newsAgent.state.state import NewsAgentState


def should_continue(state: NewsAgentState) -> Literal["fetch_page", "finalize_items"]:
    """Route the graph after one page has been processed.

    `find_next_page_node` is responsible for deciding whether another page
    exists. This function only applies the user-defined page limit so the
    crawler cannot loop forever on broken pagination.
    """
    max_pages = state.get("max_pages", 10)
    visited_count = len(state.get("visited_urls", []))
    next_url = state.get("next_url")

    if next_url and visited_count < max_pages:
        return "fetch_page"

    return "finalize_items"


def build_news_agent():
    """Build the LangGraph workflow for crawling a paginated news list.

    The graph intentionally does expensive LLM work only twice:
    - near the beginning, to identify title/pagination clues;
    - at the end, to structure all collected card HTML into final fields.
    Card extraction and pagination between those points are mostly DOM based.
    """
    graph = StateGraph(NewsAgentState)
    graph.add_node("fetch_page", fetch_page_node)
    graph.add_node("extract_titles", extract_titles_node)
    graph.add_node("extract_cards", extract_cards_node)
    graph.add_node("find_next_page", find_next_page_node)
    graph.add_node("finalize_items", finalize_items_node)

    graph.set_entry_point("fetch_page")
    # Per-page loop:
    # fetch DOM/text -> learn or reuse title/card clues -> collect card HTML
    # -> click/analyze pagination -> either loop or finalize.
    graph.add_edge("fetch_page", "extract_titles")
    graph.add_edge("extract_titles", "extract_cards")
    graph.add_edge("extract_cards", "find_next_page")
    graph.add_conditional_edges(
        "find_next_page",
        should_continue,
        {"fetch_page": "fetch_page", "finalize_items": "finalize_items"},
    )
    graph.add_edge("finalize_items", END)
    return graph.compile()


def crawl_team_news(
    start_url: str,
    max_pages: int = 10,
    *,
    existing_titles: Iterable[str] | None = None,
) -> dict:
    """Run the news crawler from FastAPI/service code.

    Args:
        start_url: Organization/news list URL.
        max_pages: Maximum number of paginated list pages to crawl.
        existing_titles: Titles already stored in the database. Matching raw
            cards are filtered before final LLM extraction to avoid spending
            tokens on known items.
    """
    agent = build_news_agent()
    return agent.invoke(
        {
            # `current_url` may later become a synthetic cursor such as
            # `...#page=2` when pagination changes DOM without changing URL.
            "start_url": start_url,
            "current_url": start_url,
            "max_pages": max_pages,
            "visited_urls": [],
            "existing_titles": list(existing_titles or []),
            "raw_cards": [],
            "errors": [],
        },
        {"recursion_limit": max_pages * 5 + 10},
    )
