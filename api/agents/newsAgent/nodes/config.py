import json
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parents[3] / "app_config.json"


def load_agent_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as file:
        return json.load(file)
