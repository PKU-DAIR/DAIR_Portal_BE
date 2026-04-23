import json
import re
from pathlib import Path

from json_repair import repair_json
from langchain_openai import ChatOpenAI
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from api.agents.promptLoader.prompt_loader import load_prompt
from api.logger import get_logger

from ..state.state import NewsAgentState


logger = get_logger()
CONFIG_PATH = Path(__file__).resolve().parents[3] / "app_config.json"
JS_DIR = Path(__file__).resolve().parents[1] / "js"
NEXT_PAGE_SCRIPT = (JS_DIR / "find_next_page.js").read_text(encoding="utf-8")


def load_agent_config() -> dict:
    """Read model/API configuration from the app config file."""
    with CONFIG_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def _parse_json_object(content: str) -> dict:
    """Parse an LLM JSON object, tolerating extra text around it."""
    content = content.strip()
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        content = match.group(0)
    data = json.loads(repair_json(content))
    return data if isinstance(data, dict) else {}


def _analyze_pagination_with_llm(
    *,
    url: str,
    container: dict,
) -> dict:
    """Ask the LLM which pagination control should be clicked next.

    JS only locates the paginator and serializes candidate controls. The LLM is
    used for interpretation because paginators vary widely: "下一页", numbers,
    disabled states, current-page styling, "共4页", and so on.
    """
    config = load_agent_config()
    base_url = config.get("base_url")
    model_name = config.get("model_name")
    api_key = config.get("api_key")

    if not (base_url and model_name and api_key):
        logger.warning("newsAgent.find_next_page no llm config; stop pagination")
        return {"has_next": False, "target_index": None, "reason": "missing llm config"}

    payload = {
        "url": url,
        "container_text": container.get("container_text", ""),
        "container_html": container.get("container_html", ""),
        "candidates": container.get("candidates", []),
    }

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )
    response = llm.invoke(
        [
            ("system", load_prompt("analyze_pagination")),
            ("user", json.dumps(payload, ensure_ascii=False)),
        ]
    )
    return _parse_json_object(response.content or "{}")


def _synthetic_page_url(url: str, analysis: dict, click_count: int) -> str:
    """Create an internal cursor when clicking changes DOM but not URL.

    The crawler still needs a distinct `next_url` so LangGraph continues and
    `visited_urls` can distinguish pages. This value is not meant to be fetched
    directly; `pending_page_html` carries the real clicked DOM.
    """
    current_page = analysis.get("current_page")
    target_index = analysis.get("target_index")
    page_token = current_page + 1 if isinstance(current_page, int) else click_count + 1
    if page_token is None:
        page_token = target_index
    base_url = url.split("#page=", 1)[0]
    return f"{base_url}#page={page_token}"


def _wait_after_click(page) -> None:
    """Wait for both network and JavaScript-driven DOM updates after a click."""
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(1000)


def _click_candidate(
    page,
    *,
    target_index: int,
    next_texts: list[str],
    pagination_texts: list[str],
) -> bool:
    """Click a paginator candidate by the index returned from the inspect script."""
    clicked = page.evaluate(
        NEXT_PAGE_SCRIPT,
        {
            "mode": "click",
            "nextTexts": next_texts,
            "paginationTexts": pagination_texts,
            "targetIndex": target_index,
        },
    )
    if not clicked.get("clicked"):
        return False
    return True


def _wait_for_page_change(page, *, before_text: str, before_html: str) -> tuple[str, str]:
    """Return the new page text/html after a click.

    URL changes are not required. Many sites update a list with JavaScript while
    keeping the same address, so DOM/text changes are the success signal.
    """
    try:
        page.wait_for_function(
            """({ beforeText, beforeHtml }) => {
                const text = document.body ? document.body.innerText : "";
                const html = document.documentElement ? document.documentElement.outerHTML : "";
                return text !== beforeText || html !== beforeHtml;
            }""",
            arg={"beforeText": before_text, "beforeHtml": before_html},
            timeout=15000,
        )
    except PlaywrightTimeoutError:
        pass

    _wait_after_click(page)
    after_text = page.locator("body").inner_text(timeout=10000)
    after_html = page.content()
    return after_text, after_html


def find_next_page_node(state: NewsAgentState) -> NewsAgentState:
    """Find and click the next page, if one exists.

    Pagination is handled by real clicks, not by href extraction alone. For
    script-based pagination we replay prior click indices from `start_url` to
    reconstruct the browser runtime before asking which control to click next.
    """
    url = state["current_url"]
    next_texts = state.get("next_page_texts", [])
    pagination_texts = state.get("pagination_texts", [])
    click_history = state.get("pagination_click_indices", [])
    errors = state.get("errors", [])
    logger.info(
        "newsAgent.find_next_page start url=%s next_texts=%s pagination_texts=%s",
        url,
        next_texts,
        pagination_texts,
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            replay_url = state.get("start_url") or url.split("#page=", 1)[0]
            page.goto(replay_url, wait_until="networkidle", timeout=60000)

            for history_index in click_history:
                # Restore the current page in a live browser. Reusing static HTML
                # would lose site-defined functions such as `goToPage(2)`.
                ok = _click_candidate(
                    page,
                    target_index=history_index,
                    next_texts=next_texts,
                    pagination_texts=pagination_texts,
                )
                if not ok:
                    logger.warning(
                        "newsAgent.find_next_page replay click failed target_index=%s",
                        history_index,
                    )
                    browser.close()
                    return {**state, "next_url": None}

            before_url = page.url
            before_text = page.locator("body").inner_text(timeout=10000)
            before_html = page.content()
            # First browser-side pass only inspects paginator candidates and
            # returns their HTML/text/onclick metadata for LLM analysis.
            container = page.evaluate(
                NEXT_PAGE_SCRIPT,
                {
                    "mode": "inspect",
                    "nextTexts": next_texts,
                    "paginationTexts": pagination_texts,
                },
            )

            if not container.get("container_html") or not container.get("candidates"):
                logger.info("newsAgent.find_next_page no pagination container url=%s", url)
                browser.close()
                return {**state, "next_url": None}

            analysis = _analyze_pagination_with_llm(url=url, container=container)
            logger.info(
                "newsAgent.find_next_page analysis=%s",
                json.dumps(analysis, ensure_ascii=False),
            )

            target_index = analysis.get("target_index")
            if not analysis.get("has_next") or not isinstance(target_index, int):
                browser.close()
                return {**state, "next_url": None}

            # Second browser-side pass clicks the LLM-selected candidate.
            clicked = _click_candidate(
                page,
                target_index=target_index,
                next_texts=next_texts,
                pagination_texts=pagination_texts,
            )
            if not clicked:
                logger.warning("newsAgent.find_next_page click failed target_index=%s", target_index)
                browser.close()
                return {**state, "next_url": None}

            after_text, next_html = _wait_for_page_change(
                page,
                before_text=before_text,
                before_html=before_html,
            )
            after_url = page.url
            if after_url == before_url and after_text == before_text and next_html == before_html:
                logger.warning("newsAgent.find_next_page click did not change dom url=%s", url)
                browser.close()
                return {**state, "next_url": None}

            next_url = (
                after_url
                if after_url != before_url and not after_url.startswith("about:blank")
                else _synthetic_page_url(url, analysis, len(click_history) + 1)
            )
            if next_url.startswith("about:blank"):
                next_url = _synthetic_page_url(url, analysis, len(click_history) + 1)
            browser.close()
    except Exception as exc:
        errors.append(f"Find next page failed: {exc}")
        logger.warning("newsAgent.find_next_page failed url=%s error=%s", url, exc)
        return {**state, "next_url": None, "errors": errors}

    if next_url in state.get("visited_urls", []):
        logger.warning(
            "newsAgent.find_next_page ignored visited next_url=%s current_url=%s",
            next_url,
            url,
        )
        next_url = None

    if next_url:
        logger.info("newsAgent.find_next_page found next_url=%s", next_url)
        return {
            **state,
            "current_url": next_url,
            "next_url": next_url,
            # The next loop consumes this snapshot instead of fetching the
            # synthetic cursor as a real URL.
            "pending_page_text": after_text,
            "pending_page_html": next_html,
            # Store the chosen control so future pagination decisions can replay
            # page 2, page 3, etc. from the original live URL.
            "pagination_click_indices": click_history + [target_index],
            "errors": errors,
        }

    logger.info("newsAgent.find_next_page done; no next page url=%s", url)
    return {**state, "next_url": None, "errors": errors}
