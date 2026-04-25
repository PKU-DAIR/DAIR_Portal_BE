from typing import Any, TypedDict


class PubAgentState(TypedDict, total=False):
    # Original entry URL and the current cursor. For this agent both fields are
    # the same today, but keeping the shape explicit makes future pagination or
    # multi-source expansion easier.
    start_url: str
    current_url: str

    # One full page snapshot fetched by Playwright. Later nodes reuse these
    # fields instead of hitting the network again.
    page_title: str
    page_text: str
    page_html: str

    # Raw DOM blocks produced by the browser-side chunking script. Each block
    # contains compact text and a short HTML slice that help the LLM recover
    # venue/page metadata without sending the whole page.
    #
    # `max_blocks` is an optional debugging/throttling knob. When set, the
    # agent only keeps the first N normalized blocks and ignores the rest.
    raw_blocks: list[dict[str, Any]]
    max_blocks: int | None

    # Final normalized publications aligned to `PublicationDBModel`.
    items: list[dict[str, Any]]
    errors: list[str]
