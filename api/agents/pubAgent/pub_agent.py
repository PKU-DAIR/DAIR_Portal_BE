from langgraph.graph import END, StateGraph

from api.agents.pubAgent.nodes.chunk_blocks import chunk_blocks_node
from api.agents.pubAgent.nodes.fetch_page import fetch_page_node
from api.agents.pubAgent.nodes.finalize_items import finalize_items_node
from api.agents.pubAgent.state.state import PubAgentState


def build_pub_agent():
    """Build a lightweight graph for one long publications page.

    Unlike `newsAgent`, this workflow has no pagination loop. The target pages
    are usually single long publication lists, so the work is strictly linear:
    fetch page -> split page into DOM-sized blocks -> extract publications.
    """
    graph = StateGraph(PubAgentState)
    graph.add_node("fetch_page", fetch_page_node)
    graph.add_node("chunk_blocks", chunk_blocks_node)
    graph.add_node("finalize_items", finalize_items_node)

    graph.set_entry_point("fetch_page")
    graph.add_edge("fetch_page", "chunk_blocks")
    graph.add_edge("chunk_blocks", "finalize_items")
    graph.add_edge("finalize_items", END)
    return graph.compile()


def crawl_publications(start_url: str, max_blocks: int | None = None) -> list[dict]:
    """Run the publications crawler and return normalized item dicts."""
    agent = build_pub_agent()
    result = agent.invoke(
        {
            "start_url": start_url,
            "current_url": start_url,
            "max_blocks": max_blocks,
            "raw_blocks": [],
            "items": [],
            "errors": [],
        }
    )
    return result.get("items", [])
