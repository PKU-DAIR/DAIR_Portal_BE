({ nextTexts = [] }) => {
    const current = location.href;
    const norm = value => (value || "").replace(/\s+/g, " ").trim().toLowerCase();
    const defaults = ["下一页", "下页", "next", ">", "›", "»"];
    const labels = [...new Set([...nextTexts, ...defaults].map(norm).filter(Boolean))];

    const relNext = document.querySelector('a[rel="next"], link[rel="next"]');
    if (relNext && relNext.href && relNext.href !== current) return relNext.href;

    const candidates = [...document.querySelectorAll("a[href], button, [role='button']")];
    for (const el of candidates) {
        const text = norm(el.innerText || el.textContent || el.getAttribute("aria-label") || el.title);
        const matches = labels.some(label => text === label || (label.length > 1 && text.includes(label)));
        if (!matches) continue;

        if (el.href && el.href !== current) return el.href;
        const link = el.closest("a[href]") || el.querySelector("a[href]");
        if (link && link.href && link.href !== current) return link.href;
    }

    return null;
}
