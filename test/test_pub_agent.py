#!/usr/bin/env python3

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from api.agents.pubAgent.pub_agent import crawl_publications


config = json.loads((ROOT_DIR / "api/app_config.json").read_text(encoding="utf-8"))

url = config.get("publication_url")
if not url:
    raise ValueError("Missing publication_url in api/app_config.json")

items = crawl_publications(url)

print(json.dumps(items, ensure_ascii=False, indent=2))
print(f"\nitems: {len(items)}")
