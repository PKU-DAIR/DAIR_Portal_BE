import json
import re
from pathlib import Path

from api.agents.promptLoader.prompt_loader import load_prompt
from api.logger import get_logger

from ..state.state import PubAgentState

try:
    from json_repair import repair_json
except ImportError:
    def repair_json(content: str) -> str:
        """Fallback used when `json_repair` is unavailable in the environment."""
        return content

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None


logger = get_logger()
CONFIG_PATH = Path(__file__).resolve().parents[3] / "app_config.json"
MAX_LLM_OUTPUT_ITEMS_PER_BLOCK = 100
PUB_FIELDS = [
    "publisher",
    "DOI",
    "year",
    "title",
    "url",
    "booktitle",
    "language",
    "chapter",
    "volume",
    "number",
    "pages",
    "school",
    "author",
]


def finalize_items_node(state: PubAgentState) -> PubAgentState:
    """Extract structured publications from each DOM block and merge them.

    Each block is sent separately to keep prompt size bounded on very long
    pages. After that we merge by normalized title and keep the most complete
    version of each paper.
    """
    blocks = state.get("raw_blocks", [])
    errors = state.get("errors", [])
    logger.info("pubAgent.finalize_items start raw_blocks=%d", len(blocks))

    if not blocks:
        logger.warning("pubAgent.finalize_items no raw blocks")
        return {**state, "items": []}

    config = load_agent_config()
    base_url = config.get("base_url")
    model_name = config.get("model_name")
    api_key = config.get("api_key")
    if not (base_url and model_name and api_key):
        raise ValueError("Missing LLM config for publication extraction")
    if ChatOpenAI is None:
        raise ImportError("langchain_openai is required for publication extraction")

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )

    merged_by_title: dict[str, dict] = {}
    for index, block in enumerate(blocks):
        logger.info(
            "pubAgent.finalize_items extracting block=%d/%d chars=%d",
            index + 1,
            len(blocks),
            len(block.get("text", "")),
        )
        try:
            items = _extract_block_items(
                llm=llm,
                url=state["current_url"],
                page_title=state.get("page_title", ""),
                block=block,
            )
        except Exception as exc:
            errors.append(f"Block {index + 1} extraction failed: {exc}")
            logger.warning(
                "pubAgent.finalize_items block extraction failed block=%d error=%s",
                index + 1,
                exc,
            )
            continue

        for item in items:
            title_key = _normalize_title(item.get("title", ""))
            if not title_key:
                continue
            existing = merged_by_title.get(title_key)
            if existing is None or _completeness_score(item) > _completeness_score(existing):
                merged_by_title[title_key] = item

    items = list(merged_by_title.values())
    logger.info("pubAgent.finalize_items done items=%d errors=%d", len(items), len(errors))
    return {
        **state,
        "items": items,
        "errors": errors,
    }


def load_agent_config() -> dict:
    """Read shared model/API configuration from the app config file."""
    with CONFIG_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def _extract_block_items(
    *,
    llm: ChatOpenAI,
    url: str,
    page_title: str,
    block: dict,
) -> list[dict]:
    """Call the LLM for one block and normalize its response."""
    response = llm.invoke(
        [
            ("system", load_prompt("extract_publications")),
            (
                "user",
                json.dumps(
                    {
                        "source_url": url,
                        "page_title": page_title,
                        "max_output_items": MAX_LLM_OUTPUT_ITEMS_PER_BLOCK,
                        "block_tag": block.get("tag", ""),
                        "block_text": block.get("text", ""),
                        "block_html": block.get("html", ""),
                    },
                    ensure_ascii=False,
                ),
            ),
        ]
    )
    return _normalize_publication_items(_parse_items(response.content or "[]"), url=url)


def _parse_items(content: str) -> list[dict]:
    """Parse a JSON array from the model, tolerating wrapper text."""
    content = (content or "").strip()
    match = re.search(r"\[[\s\S]*\]", content)
    if match:
        content = match.group(0)
    data = json.loads(repair_json(content or "[]"))
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _normalize_publication_items(items: list[dict], *, url: str) -> list[dict]:
    """Normalize LLM output into the `PublicationDBModel` field shape."""
    normalized = []
    for item in items:
        title = _clean_text(item.get("title"))
        if not title:
            continue

        authors = _clean_text(item.get("authors")) or _clean_text(item.get("author"))
        booktitle = _clean_text(item.get("booktitle")) or _clean_text(item.get("containerTitle"))
        year = _extract_year(_clean_text(item.get("year")) or _clean_text(item.get("createDate")))
        normalized_item = {field: "" for field in PUB_FIELDS}
        normalized_item.update(
            {
                "publisher": _clean_text(item.get("publisher")),
                "DOI": _clean_text(item.get("DOI")),
                "year": year,
                "title": title,
                "url": _clean_text(item.get("url")) or url,
                "booktitle": booktitle,
                "language": _clean_text(item.get("language")),
                "chapter": _clean_text(item.get("chapter")),
                "volume": _clean_text(item.get("volume")),
                "number": _clean_text(item.get("number")),
                "pages": _clean_text(item.get("pages")),
                "school": _clean_text(item.get("school")),
                "author": authors,
            }
        )
        normalized.append(normalized_item)
    return normalized


def _completeness_score(item: dict) -> tuple[int, int]:
    """Prefer the extraction with more populated fields when deduplicating."""
    values = [_clean_text(item.get(field)) for field in PUB_FIELDS]
    return sum(1 for value in values if value), sum(len(value) for value in values)


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", "", title or "").strip().lower()


def _extract_year(value: str) -> str:
    match = re.search(r"(19|20)\d{2}", value or "")
    return match.group(0) if match else _clean_text(value)


def _clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()
