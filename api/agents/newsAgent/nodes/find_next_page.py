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
    with CONFIG_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def _parse_json_object(content: str) -> dict:
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


def _synthetic_page_url(url: str, analysis: dict) -> str:
    current_page = analysis.get("current_page")
    target_index = analysis.get("target_index")
    page_token = current_page + 1 if isinstance(current_page, int) else target_index
    return f"{url}#page={page_token}"


def find_next_page_node(state: NewsAgentState) -> NewsAgentState:
    url = state["current_url"]
    next_texts = state.get("next_page_texts", [])
    pagination_texts = state.get("pagination_texts", [])
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
            if state.get("page_html"):
                page.set_content(state["page_html"], wait_until="domcontentloaded")
            else:
                page.goto(url, wait_until="networkidle", timeout=60000)

            before_url = page.url
            before_text = page.locator("body").inner_text(timeout=10000)
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
                logger.warning("newsAgent.find_next_page click failed target_index=%s", target_index)
                browser.close()
                return {**state, "next_url": None}

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(1000)

            after_url = page.url
            after_text = page.locator("body").inner_text(timeout=10000)
            if after_url == before_url and after_text == before_text:
                logger.warning("newsAgent.find_next_page click did not change page url=%s", url)
                browser.close()
                return {**state, "next_url": None}

            next_url = after_url if after_url != before_url else _synthetic_page_url(url, analysis)
            next_html = page.content()
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
            "pending_page_text": after_text,
            "pending_page_html": next_html,
            "errors": errors,
        }

    logger.info("newsAgent.find_next_page done; no next page url=%s", url)
    return {**state, "next_url": None, "errors": errors}
