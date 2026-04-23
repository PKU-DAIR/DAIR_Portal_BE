from playwright.sync_api import sync_playwright

from api.logger import get_logger

from ..state.state import NewsAgentState


logger = get_logger()


def fetch_page_node(state: NewsAgentState) -> NewsAgentState:
    """Fetch page text/html for the current graph cursor.

    Normal URL pages are opened with Playwright. For JS pagination, the previous
    node may already have clicked the next page and stored its DOM snapshot in
    `pending_page_html`; in that case we consume the snapshot instead of opening
    the URL again, because the URL may not represent page state.
    """
    url = state.get("current_url") or state["start_url"]
    logger.info("newsAgent.fetch_page start url=%s", url)

    pending_html = state.get("pending_page_html", "")
    pending_text = state.get("pending_page_text", "")

    if pending_html:
        # SPA/script pagination often keeps the same visible URL. This branch
        # preserves the clicked DOM exactly as `find_next_page_node` saw it.
        text = pending_text
        html = pending_html
        logger.info("newsAgent.fetch_page using pending page snapshot url=%s", url)
    else:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)
            text = page.locator("body").inner_text(timeout=10000)
            html = page.content()
            browser.close()

    visited = state.get("visited_urls", [])
    if url not in visited:
        visited.append(url)

    logger.info(
        "newsAgent.fetch_page done url=%s text_chars=%d visited_count=%d",
        url,
        len(text),
        len(visited),
    )

    return {
        **state,
        "current_url": url,
        "visited_urls": visited,
        "page_text": text,
        "page_html": html,
        # Clear one-shot snapshot fields so accidental reuse cannot happen.
        "pending_page_text": "",
        "pending_page_html": "",
    }
