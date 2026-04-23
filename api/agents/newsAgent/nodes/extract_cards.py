from pathlib import Path

from playwright.sync_api import sync_playwright

from .state import NewsAgentState


JS_DIR = Path(__file__).resolve().parents[1] / "js"
CARD_EXTRACT_SCRIPT = (JS_DIR / "extract_cards.js").read_text(encoding="utf-8")


def extract_cards_node(state: NewsAgentState) -> NewsAgentState:
    url = state["current_url"]
    titles = state.get("title_candidates", [])
    features = state.get("dom_features")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        result = page.evaluate(
            CARD_EXTRACT_SCRIPT,
            {"titles": titles, "features": features},
        )
        browser.close()

    page_items = result.get("cards", [])
    dom_features = features or result.get("features")
    old_cards = state.get("raw_cards", state.get("items", []))
    seen = {(item.get("title"), item.get("link")) for item in old_cards}
    new_items = []

    for item in page_items:
        key = (item.get("title"), item.get("link"))
        if key not in seen:
            seen.add(key)
            new_items.append({**item, "source_page": url})

    return {
        **state,
        "dom_features": dom_features,
        "page_items": new_items,
        "raw_cards": old_cards + new_items,
        "items": old_cards + new_items,
    }
