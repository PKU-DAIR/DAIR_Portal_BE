#!/usr/bin/env python3

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from api.agents.newsAgent.news_agent import crawl_team_news


config = json.loads((ROOT_DIR / "api/app_config.json").read_text(encoding="utf-8"))

url = config["scholar_url"]
max_pages = config.get("scholar_max_pages", 1)

result = crawl_team_news(url, max_pages=max_pages)
data = {
    "visited_urls": result.get("visited_urls", []),
    "items": result.get("items", []),
    "errors": result.get("errors", []),
}

print(json.dumps(data, ensure_ascii=False, indent=2))
print(f"\nvisited: {len(data['visited_urls'])}, items: {len(data['items'])}")
