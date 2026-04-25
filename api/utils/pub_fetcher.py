import asyncio
import datetime
import json
import logging
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Optional

from api.agents.pubAgent.pub_agent import crawl_publications
from api.logger import get_logger, logging_context, remove_handler
from api.models.db_models import PublicationDBModel


CONFIG_PATH = Path(__file__).resolve().parents[1] / "app_config.json"
PUB_FETCH_LOG_LIMIT = 5000
PUB_FETCH_LOG_CONTEXT = "pub_fetch"
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

logger = get_logger()
PUB_FETCH_STATE: dict[str, Any] = {
    "status": "idle",
    "message": "No publication fetch task has been started",
    "params": {},
    "created_at": None,
    "updated_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
    "logs": deque(maxlen=PUB_FETCH_LOG_LIMIT),
}


class InMemoryTaskLogHandler(logging.Handler):
    """Collect logs for the singleton publication fetch task state."""

    def __init__(self):
        super().__init__()
        self.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "log_context", "") != PUB_FETCH_LOG_CONTEXT:
            return
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()
        PUB_FETCH_STATE["logs"].append(message)
        PUB_FETCH_STATE["updated_at"] = datetime.datetime.now().isoformat()


def start_publication_sync_task(
    start_url: Optional[str] = None,
    max_blocks: Optional[int] = None,
) -> dict[str, Any]:
    now = datetime.datetime.now().isoformat()
    if PUB_FETCH_STATE["status"] == "running":
        return get_publication_sync_task()

    PUB_FETCH_STATE.update(
        {
            "status": "running",
            "message": "Publication fetch task started",
            "params": {
                "start_url": start_url,
                "max_blocks": max_blocks,
            },
            "created_at": now,
            "updated_at": now,
            "finished_at": None,
            "result": None,
            "error": None,
            "logs": deque(maxlen=PUB_FETCH_LOG_LIMIT),
        }
    )
    asyncio.create_task(
        _run_publication_sync_task(
            start_url=start_url,
            max_blocks=max_blocks,
        )
    )
    return get_publication_sync_task()


def get_publication_sync_task() -> dict[str, Any]:
    return {
        "status": PUB_FETCH_STATE["status"],
        "message": PUB_FETCH_STATE["message"],
        "params": PUB_FETCH_STATE["params"],
        "created_at": PUB_FETCH_STATE["created_at"],
        "updated_at": PUB_FETCH_STATE["updated_at"],
        "finished_at": PUB_FETCH_STATE["finished_at"],
        "result": PUB_FETCH_STATE["result"],
        "error": PUB_FETCH_STATE["error"],
        "logs": list(PUB_FETCH_STATE["logs"]),
    }


async def _run_publication_sync_task(
    start_url: Optional[str] = None,
    max_blocks: Optional[int] = None,
) -> None:
    handler = InMemoryTaskLogHandler()
    logger.addHandler(handler)
    try:
        with logging_context(PUB_FETCH_LOG_CONTEXT):
            logger.info("publication fetch task started")
            result = await sync_publications_from_agent(
                start_url=start_url,
                max_blocks=max_blocks,
            )
            PUB_FETCH_STATE["status"] = "success"
            PUB_FETCH_STATE["message"] = "Publication fetch task finished successfully"
            PUB_FETCH_STATE["result"] = result
            PUB_FETCH_STATE["updated_at"] = datetime.datetime.now().isoformat()
            logger.info(
                "publication fetch task finished created_count=%s skipped_existing_count=%s agent_item_count=%s",
                result.get("created_count", 0),
                result.get("skipped_existing_count", 0),
                result.get("agent_item_count", 0),
            )
    except ValueError as exc:
        PUB_FETCH_STATE["status"] = "failed"
        PUB_FETCH_STATE["message"] = str(exc)
        PUB_FETCH_STATE["error"] = str(exc)
        PUB_FETCH_STATE["updated_at"] = datetime.datetime.now().isoformat()
        with logging_context(PUB_FETCH_LOG_CONTEXT):
            logger.warning("publication fetch task failed error=%s", exc)
    except Exception as exc:
        PUB_FETCH_STATE["status"] = "failed"
        PUB_FETCH_STATE["message"] = f"Fetch publications failed: {exc}"
        PUB_FETCH_STATE["error"] = str(exc)
        PUB_FETCH_STATE["updated_at"] = datetime.datetime.now().isoformat()
        with logging_context(PUB_FETCH_LOG_CONTEXT):
            logger.exception("publication fetch task crashed")
    finally:
        PUB_FETCH_STATE["finished_at"] = datetime.datetime.now().isoformat()
        remove_handler(logger, handler)


async def sync_publications_from_agent(
    start_url: Optional[str] = None,
    max_blocks: Optional[int] = None,
) -> dict[str, Any]:
    """Fetch publication items, filter existing titles, and insert new rows."""
    config = _load_config()
    crawl_url = start_url or config.get("publication_url")
    if not crawl_url:
        raise ValueError("start_url is required when publication_url is not configured")

    existing_publications = await PublicationDBModel.all().values("title")
    existing_title_keys = {
        _normalize_title(item.get("title"))
        for item in existing_publications
        if item.get("title")
    }

    items = await asyncio.to_thread(
        crawl_publications,
        crawl_url,
        max_blocks,
    )
    created = []
    skipped_existing = []

    for item in items:
        title = _clean_text(item.get("title"))
        if not title:
            continue

        title_key = _normalize_title(title)
        if title_key in existing_title_keys:
            skipped_existing.append(item)
            continue

        now = datetime.datetime.now().isoformat()
        publication_data = {
            "id": str(uuid.uuid4()),
            "publisher": _clean_text(item.get("publisher")),
            "DOI": _clean_text(item.get("DOI")),
            "year": _clean_text(item.get("year")),
            "createDate": now,
            "source": crawl_url,
            "title": title,
            "url": _clean_text(item.get("url")),
            "booktitle": _clean_text(item.get("booktitle")),
            "abstract": "",
            "ISSN": "",
            "language": _clean_text(item.get("language")),
            "chapter": _clean_text(item.get("chapter")),
            "volume": _clean_text(item.get("volume")),
            "number": _clean_text(item.get("number")),
            "pages": _clean_text(item.get("pages")),
            "school": _clean_text(item.get("school")),
            "note": "",
            "author": _clean_text(item.get("author")),
            "authors": "",
            "containerTitle": "",
            "entry_type": "",
            "bib": "",
            "update_time": now,
        }
        await PublicationDBModel.create(**publication_data)
        existing_title_keys.add(title_key)
        created.append({field: publication_data[field] for field in ["id", *PUB_FIELDS]})

    return {
        "created": created,
        "created_count": len(created),
        "skipped_existing_count": len(skipped_existing),
        "agent_item_count": len(items),
        "max_blocks": max_blocks,
        "start_url": crawl_url,
    }


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def _normalize_title(title: Any) -> str:
    return "".join(_clean_text(title).split()).lower()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
