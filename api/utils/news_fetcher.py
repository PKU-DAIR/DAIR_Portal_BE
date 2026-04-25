import asyncio
import datetime
import logging
import os
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Optional
from urllib.request import Request, urlopen

from tortoise.expressions import Q

from api.agents.newsAgent.news_agent import crawl_team_news
from api.logger import get_logger, logging_context, remove_handler
from api.models.db_init import ensure_folder
from api.models.db_models import NewsDBModel
from api.utils.image_compress import clear_compressed_image_cache


CONFIG_PATH = Path(__file__).resolve().parents[1] / "app_config.json"
NEWS_FIELDS = ["id", "title", "description", "news_type", "publisher_id", "publish_time", "update_time", "external"]
DEFAULT_NEWS_TYPE = "news"
BANNER_FILE_NAME = "banner.jpg"
DOWNLOAD_TIMEOUT_SECONDS = 20
USER_AGENT = "Mozilla/5.0 (compatible; DAIR-Portal-NewsFetcher/1.0)"
NEWS_FETCH_LOG_LIMIT = 5000
NEWS_FETCH_LOG_CONTEXT = "news_fetch"

logger = get_logger()
NEWS_FETCH_STATE: dict[str, Any] = {
    "status": "idle",
    "message": "No news fetch task has been started",
    "params": {},
    "created_at": None,
    "updated_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
    "logs": deque(maxlen=NEWS_FETCH_LOG_LIMIT),
}


class InMemoryTaskLogHandler(logging.Handler):
    """Collect logs for the singleton news fetch task state."""

    def __init__(self):
        super().__init__()
        self.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "log_context", "") != NEWS_FETCH_LOG_CONTEXT:
            return
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()
        NEWS_FETCH_STATE["logs"].append(message)
        NEWS_FETCH_STATE["updated_at"] = datetime.datetime.now().isoformat()


async def _query_news(search: Optional[str] = None):
    if search:
        return await NewsDBModel.filter(Q(title__icontains=search) | Q(description__icontains=search)).values(*NEWS_FIELDS)
    return await NewsDBModel.all().values(*NEWS_FIELDS)


def start_news_sync_task(
    start_url: Optional[str] = None,
    max_pages: Optional[int] = None,
    *,
    search: Optional[str] = None,
    publisher_id: Optional[str] = None,
) -> dict[str, Any]:
    now = datetime.datetime.now().isoformat()
    if NEWS_FETCH_STATE["status"] == "running":
        return get_news_sync_task()

    NEWS_FETCH_STATE.update(
        {
            "status": "running",
            "message": "News fetch task started",
            "params": {
                "start_url": start_url,
                "max_pages": max_pages,
                "search": search,
                "publisher_id": publisher_id,
            },
            "created_at": now,
            "updated_at": now,
            "finished_at": None,
            "result": None,
            "error": None,
            "logs": deque(maxlen=NEWS_FETCH_LOG_LIMIT),
        }
    )
    asyncio.create_task(
        _run_news_sync_task(
            start_url=start_url,
            max_pages=max_pages,
            search=search,
            publisher_id=publisher_id,
        )
    )
    return get_news_sync_task()


def get_news_sync_task() -> dict[str, Any]:
    return {
        "status": NEWS_FETCH_STATE["status"],
        "message": NEWS_FETCH_STATE["message"],
        "params": NEWS_FETCH_STATE["params"],
        "created_at": NEWS_FETCH_STATE["created_at"],
        "updated_at": NEWS_FETCH_STATE["updated_at"],
        "finished_at": NEWS_FETCH_STATE["finished_at"],
        "result": NEWS_FETCH_STATE["result"],
        "error": NEWS_FETCH_STATE["error"],
        "logs": list(NEWS_FETCH_STATE["logs"]),
    }


async def _run_news_sync_task(
    start_url: Optional[str] = None,
    max_pages: Optional[int] = None,
    *,
    search: Optional[str] = None,
    publisher_id: Optional[str] = None,
) -> None:
    handler = InMemoryTaskLogHandler()
    logger.addHandler(handler)
    try:
        with logging_context(NEWS_FETCH_LOG_CONTEXT):
            logger.info("news fetch task started")
            result = await sync_news_from_agent(
                start_url=start_url,
                max_pages=max_pages,
                search=search,
                publisher_id=publisher_id,
            )
            NEWS_FETCH_STATE["status"] = "success"
            NEWS_FETCH_STATE["message"] = "News fetch task finished successfully"
            NEWS_FETCH_STATE["result"] = result
            NEWS_FETCH_STATE["updated_at"] = datetime.datetime.now().isoformat()
            logger.info(
                "news fetch task finished created_count=%s skipped_existing_count=%s",
                result.get("created_count", 0),
                result.get("skipped_existing_count", 0),
            )
    except ValueError as exc:
        NEWS_FETCH_STATE["status"] = "failed"
        NEWS_FETCH_STATE["message"] = str(exc)
        NEWS_FETCH_STATE["error"] = str(exc)
        NEWS_FETCH_STATE["updated_at"] = datetime.datetime.now().isoformat()
        with logging_context(NEWS_FETCH_LOG_CONTEXT):
            logger.warning("news fetch task failed error=%s", exc)
    except Exception as exc:
        NEWS_FETCH_STATE["status"] = "failed"
        NEWS_FETCH_STATE["message"] = f"Fetch news failed: {exc}"
        NEWS_FETCH_STATE["error"] = str(exc)
        NEWS_FETCH_STATE["updated_at"] = datetime.datetime.now().isoformat()
        with logging_context(NEWS_FETCH_LOG_CONTEXT):
            logger.exception("news fetch task crashed")
    finally:
        NEWS_FETCH_STATE["finished_at"] = datetime.datetime.now().isoformat()
        remove_handler(logger, handler)


async def sync_news_from_agent(
    start_url: Optional[str] = None,
    max_pages: Optional[int] = None,
    *,
    search: Optional[str] = None,
    publisher_id: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch latest news with news_agent and insert new rows into NewsDBModel.

    Existing database titles are passed into the agent first, then the returned
    items are deduplicated again by normalized title. When duplicate titles are
    returned, the item with more complete fields is kept.
    """
    existing_news = await _query_news(search)
    existing_titles = [item["title"] for item in existing_news if item.get("title")]
    existing_title_keys = {_normalize_title(title) for title in existing_titles}

    config = _load_config()
    crawl_url = start_url or config.get("scholar_url")
    if not crawl_url:
        raise ValueError("start_url is required when scholar_url is not configured")

    page_limit = int(max_pages if max_pages is not None else config.get("scholar_max_pages", 10))
    agent_result = await asyncio.to_thread(
        crawl_team_news,
        crawl_url,
        page_limit,
        existing_titles=existing_titles,
    )
    unique_items = _dedupe_news_items(agent_result.get("items", []))

    created = []
    skipped_existing = []
    image_errors = []
    for item in unique_items:
        title = _clean_text(item.get("title"))
        if not title:
            continue

        title_key = _normalize_title(title)
        if title_key in existing_title_keys:
            skipped_existing.append(item)
            continue

        news_id = str(uuid.uuid4())
        ensure_folder(f"news/{news_id}")
        publish_time = _normalize_publish_time(item.get("published_at")) or datetime.datetime.now().isoformat()
        update_data = {
            "id": news_id,
            "title": title,
            "news_type": DEFAULT_NEWS_TYPE,
            "description": _clean_text(item.get("description")) or "",
            "external": _clean_text(item.get("link")),
            "publish_time": publish_time,
            "update_time": publish_time,
        }
        if publisher_id:
            update_data["publisher_id"] = publisher_id

        await NewsDBModel.create(**update_data)
        existing_title_keys.add(title_key)

        image_url = _clean_text(item.get("image"))
        if image_url:
            image_error = await _save_banner_image(image_url, news_id)
            if image_error:
                image_errors.append({"id": news_id, "title": title, "image": image_url, "error": image_error})

        created.append({**update_data, "image": image_url, "source_page": item.get("source_page", "")})

    return {
        "created": created,
        "created_count": len(created),
        "skipped_existing_count": len(skipped_existing),
        "agent_item_count": len(agent_result.get("items", [])),
        "unique_item_count": len(unique_items),
        "visited_urls": agent_result.get("visited_urls", []),
        "errors": [*agent_result.get("errors", []), *image_errors],
    }


def _dedupe_news_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_title: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"))
        if not title:
            continue

        title_key = _normalize_title(title)
        current = {**item, "title": title}
        existing = best_by_title.get(title_key)
        if existing is None or _completeness_score(current) > _completeness_score(existing):
            best_by_title[title_key] = current

    return list(best_by_title.values())


def _completeness_score(item: dict[str, Any]) -> tuple[int, int]:
    important_fields = ("title", "published_at", "link", "image", "source_page", "description")
    filled_fields = [_clean_text(item.get(field)) for field in important_fields]
    filled_count = sum(1 for value in filled_fields if value)
    total_length = sum(len(value) for value in filled_fields)
    return filled_count, total_length


async def _save_banner_image(image_url: str, news_id: str) -> Optional[str]:
    image_dir = f"news/{news_id}"
    image_path = os.path.join(image_dir, BANNER_FILE_NAME)
    try:
        image_bytes = await asyncio.to_thread(_download_image, image_url)
        with open(image_path, "wb") as file:
            file.write(image_bytes)
        clear_compressed_image_cache(image_dir)
    except Exception as exc:
        return str(exc)
    return None


def _download_image(image_url: str) -> bytes:
    request = Request(image_url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        return response.read()


def _normalize_title(title: str) -> str:
    return "".join(_clean_text(title).split()).lower()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_publish_time(value: Any) -> str:
    published_at = _clean_text(value)
    if not published_at:
        return ""
    try:
        return datetime.datetime.fromisoformat(published_at).isoformat()
    except ValueError:
        pass
    try:
        return datetime.date.fromisoformat(published_at).isoformat()
    except ValueError:
        return published_at


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    import json

    with CONFIG_PATH.open(encoding="utf-8") as file:
        return json.load(file)
