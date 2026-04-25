from playwright.sync_api import sync_playwright

from api.logger import get_logger

from ..state.state import PubAgentState


logger = get_logger()


def fetch_page_node(state: PubAgentState) -> PubAgentState:
    """Fetch one publications page with Playwright.

    Publication pages are often rendered with dynamic widgets or collapsed
    sections, so using a browser here is safer than raw HTTP requests.
    """
    url = state.get("current_url") or state["start_url"]
    logger.info("pubAgent.fetch_page start url=%s", url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page_title = page.title()
        page_text = page.locator("body").inner_text(timeout=10000)
        page_html = page.content()
        browser.close()

    logger.info(
        "pubAgent.fetch_page done url=%s title=%s text_chars=%d",
        url,
        page_title,
        len(page_text),
    )

    return {
        **state,
        "current_url": url,
        "page_title": page_title,
        "page_text": page_text,
        "page_html": page_html,
    }
