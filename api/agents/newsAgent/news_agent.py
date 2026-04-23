import argparse
import json
import sys
from pathlib import Path
from typing import Literal

sys.path.append(str(Path(__file__).resolve().parents[3]))

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


def crawl_team_news(start_url: str, max_pages: int = 10) -> dict:
    """Run the compiled graph from a starting organization/news URL."""
    agent = build_news_agent()
    return agent.invoke(
        {
            # `current_url` may later become a synthetic cursor such as
            # `...#page=2` when pagination changes DOM without changing URL.
            "start_url": start_url,
            "current_url": start_url,
            "max_pages": max_pages,
            "visited_urls": [],
            "items": [],
            "errors": [],
        },
        {"recursion_limit": max_pages * 5 + 10},
    )


def main() -> int:
    """Small CLI wrapper for manual crawling/debugging."""
    parser = argparse.ArgumentParser(description="Crawl team news/articles from scholar site.")
    parser.add_argument("url", help="Team scholar homepage/list URL.")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = crawl_team_news(args.url, max_pages=args.max_pages)
    data = {
        "visited_urls": result.get("visited_urls", []),
        "items": result.get("items", []),
        "errors": result.get("errors", []),
    }

    print(json.dumps(data, ensure_ascii=False, indent=2))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
