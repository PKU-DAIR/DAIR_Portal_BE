from pathlib import Path

from playwright.sync_api import sync_playwright

from .state import NewsAgentState


JS_DIR = Path(__file__).resolve().parents[1] / "js"
NEXT_PAGE_SCRIPT = (JS_DIR / "find_next_page.js").read_text(encoding="utf-8")


def find_next_page_node(state: NewsAgentState) -> NewsAgentState:
    url = state["current_url"]
    next_texts = state.get("next_page_texts", [])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        next_url = page.evaluate(NEXT_PAGE_SCRIPT, {"nextTexts": next_texts})
        browser.close()

    if next_url in state.get("visited_urls", []):
        next_url = None

    if next_url:
        return {**state, "current_url": next_url, "next_url": next_url}

    return {**state, "next_url": None}
