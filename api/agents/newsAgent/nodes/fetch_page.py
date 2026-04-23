from playwright.sync_api import sync_playwright

from .state import NewsAgentState


def fetch_page_node(state: NewsAgentState) -> NewsAgentState:
    url = state.get("current_url") or state["start_url"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        text = page.locator("body").inner_text(timeout=10000)
        browser.close()

    visited = state.get("visited_urls", [])
    if url not in visited:
        visited.append(url)

    return {
        **state,
        "current_url": url,
        "visited_urls": visited,
        "page_text": text,
    }
