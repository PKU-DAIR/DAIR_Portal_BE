from pathlib import Path

from playwright.sync_api import sync_playwright

from api.logger import get_logger

from ..state.state import PubAgentState


logger = get_logger()
JS_DIR = Path(__file__).resolve().parents[1] / "js"
CHUNK_PUBLICATIONS_SCRIPT = (JS_DIR / "chunk_publications.js").read_text(encoding="utf-8")
MAX_BLOCK_CHARS = 6000
MIN_BLOCK_CHARS = 1000
MAX_BLOCK_HTML_CHARS = 4000


def chunk_blocks_node(state: PubAgentState) -> PubAgentState:
    """Split one long publication page into manageable DOM-aligned blocks.

    We do the chunking inside a browser because DOM structure matters:
    publication lists are usually grouped by headings, wrappers, and repeated
    entry containers. Pure string slicing would often cut one paper in half.
    """
    html = state.get("page_html", "")
    if not html:
        logger.warning("pubAgent.chunk_blocks no page_html")
        return {**state, "raw_blocks": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Replaying the fetched HTML avoids a second network request while still
        # letting the browser-side script inspect the DOM tree.
        page.set_content(html, wait_until="domcontentloaded")
        raw_blocks = page.locator("body").evaluate(
            CHUNK_PUBLICATIONS_SCRIPT,
            {
                "maxChars": MAX_BLOCK_CHARS,
                "minChars": MIN_BLOCK_CHARS,
                "maxHtmlChars": MAX_BLOCK_HTML_CHARS,
            },
        )
        browser.close()

    blocks = _normalize_blocks(raw_blocks or [])
    max_blocks = state.get("max_blocks")
    if max_blocks is not None:
        blocks = blocks[:max(0, max_blocks)]
    logger.info(
        "pubAgent.chunk_blocks done blocks=%d max_blocks=%s page_text_chars=%d",
        len(blocks),
        max_blocks,
        len(state.get("page_text", "")),
    )
    return {
        **state,
        "raw_blocks": blocks,
    }


def _normalize_blocks(raw_blocks: list[dict]) -> list[dict]:
    """Drop empty/duplicate chunks before the LLM stage."""
    normalized = []
    seen = set()

    for block in raw_blocks:
        text = _clean_text((block or {}).get("text"))
        if not text:
            continue
        dedupe_key = text[:500]
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(
            {
                "tag": _clean_text(block.get("tag")),
                "text": text,
                "html": _clean_text(block.get("html")),
            }
        )

    return normalized


def _clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()
