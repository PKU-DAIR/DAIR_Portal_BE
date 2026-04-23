from typing import Any, TypedDict


class NewsAgentState(TypedDict, total=False):
    # 原始入口 URL 和当前图执行游标。`current_url` 可能是真实 URL，
    # 也可能是 JS/SPA 分页时生成的内部 synthetic 标记。
    start_url: str
    current_url: str
    max_pages: int
    visited_urls: list[str]

    # 当前页面快照。`page_html` 让后续节点可以在“已经点击/翻页后的 DOM”
    # 上执行脚本，而不是重新打开第一页。
    page_text: str
    page_html: str

    # 点击分页后得到的新页面会通过这些字段传给下一轮循环。
    # `fetch_page_node` 会消费并清空它们。
    pending_page_text: str
    pending_page_html: str

    # 当分页由 JS 实现且 URL 不稳定/不变化时，记录已点击的候选按钮 index。
    # 后续需要从 `start_url` 重新打开页面并回放这些点击，恢复到同一运行时页面。
    pagination_click_indices: list[int]

    # 首轮 LLM 提取出的线索。card 提取在第一页学到 DOM 特征后，
    # 后续页面通常会跳过标题提取，直接复用这些特征抓 card。
    title_candidates: list[str]
    next_page_texts: list[str]
    pagination_texts: list[str]

    # `extract_cards.js` 学到的 card 选择器/XPath 模式。
    dom_features: dict[str, Any]

    # `raw_cards` 跨页面保存 card 的 HTML/text；最终节点会把这些原始 card
    # 一次性交给 LLM，结构化成标准新闻条目。
    page_items: list[dict[str, Any]]
    raw_cards: list[dict[str, Any]]

    # 数据库或外部调用方已经存在的标题。最终 LLM 解析前会先按标题过滤，
    # 避免对已爬取过的新闻重复消耗 token。
    existing_titles: list[str]
    items: list[dict[str, Any]]
    next_url: str | None
    errors: list[str]
