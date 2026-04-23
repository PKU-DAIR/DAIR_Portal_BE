from pathlib import Path

from playwright.sync_api import sync_playwright

from api.logger import get_logger

from ..state.state import NewsAgentState


logger = get_logger()

JS_DIR = Path(__file__).resolve().parents[1] / "js"
# The browser-side script is kept in JS so the DOM/XPath logic remains readable
# and can be debugged directly in devtools if needed.
CARD_EXTRACT_SCRIPT = (JS_DIR / "extract_cards.js").read_text(encoding="utf-8")


def extract_cards_node(state: NewsAgentState) -> NewsAgentState:
    """Collect raw card HTML from the current page.

    First page: pass LLM title candidates to JS so it can learn repeated card
    patterns. Later pages: pass learned `dom_features` so the script can collect
    cards without calling the LLM again.
    """
    url = state["current_url"]
    titles = state.get("title_candidates", [])
    features = state.get("dom_features")
    logger.info(
        "newsAgent.extract_cards start url=%s titles=%d has_features=%s",
        url,
        len(titles),
        bool(features),
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        if state.get("page_html"):
            # Use clicked-page HTML from state. This matters when the URL is only
            # an internal cursor and cannot be fetched directly.
            page.set_content(state["page_html"], wait_until="domcontentloaded")
        else:
            page.goto(url, wait_until="networkidle", timeout=60000)
        result = page.evaluate(
            CARD_EXTRACT_SCRIPT,
            {"titles": titles, "features": features},
        )
        browser.close()

    page_cards = result.get("cards", [])
    # Preserve previously learned features. The JS also returns features on
    # later pages, but the first learned set is the stable source of truth.
    dom_features = features or result.get("features")
    feature_groups = (dom_features or {}).get("card_groups", [])
    if dom_features and not features:
        logger.info(
            f"newsAgent.extract_cards learned dom_features card_groups: \n {feature_groups}",
        )
    elif not dom_features:
        logger.warning("newsAgent.extract_cards no dom_features learned url=%s", url)

    old_cards = state.get("raw_cards", [])
    # JS returns only card title/text/html. De-duplicate by a short text prefix
    # instead of URL because field extraction happens later in `finalize_items`.
    seen = {
        (item.get("title"), (item.get("text") or "")[:120])
        for item in old_cards
    }
    new_items = []

    for item in page_cards:
        key = (item.get("title"), (item.get("text") or "")[:120])
        if key not in seen:
            seen.add(key)
            new_items.append({**item, "source_page": url})

    logger.info(
        "newsAgent.extract_cards done url=%s page_cards=%d new_cards=%d total_cards=%d card_groups=%d",
        url,
        len(page_cards),
        len(new_items),
        len(old_cards) + len(new_items),
        len(feature_groups),
    )

    return {
        **state,
        "dom_features": dom_features,
        "raw_cards": old_cards + new_items,
    }
