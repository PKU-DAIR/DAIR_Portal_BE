from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt by logical name.

    Example: `load_prompt("extract_news_titles")` resolves to
    `prompts/prompt_extract_news_titles.md`.
    """
    prompt_path = PROMPT_DIR / f"prompt_{name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")
