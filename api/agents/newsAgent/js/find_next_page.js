({ mode = "inspect", nextTexts = [], paginationTexts = [] }) => {
    // This script has two modes:
    // - inspect: find the most likely pagination container and serialize all
    //   candidate controls for LLM analysis.
    // - click_next: click the control whose text means "next page".
    const norm = value => (value || "").replace(/\s+/g, " ").trim().toLowerCase();
    const textOf = el => (el.innerText || el.textContent || el.value || el.getAttribute("aria-label") || el.title || "").replace(/\s+/g, " ").trim();

    // Hidden controls are ignored so the LLM sees only actionable candidates.
    const visible = el => {
        if (!el || !el.isConnected) return false;
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    };
    const defaults = ["首页", "上一页", "下一页", "尾页", "上页", "下页", "previous", "prev", "next", "<", ">", "‹", "›", "«", "»"];
    const nextDefaults = ["下一页", "下页", "next", ">", "›", "»"];
    // Merge LLM-discovered labels with universal defaults. Page numbers are
    // handled separately by the numeric regex below.
    const labels = [...new Set([...nextTexts, ...paginationTexts, ...defaults].map(norm).filter(Boolean))];
    const nextLabels = [...new Set([...nextTexts, ...nextDefaults].map(norm).filter(Boolean))];

    // Include `[onclick]` because many legacy sites implement pagination through
    // script calls such as `goToPage(2)` rather than href navigation.
    const controls = [...document.querySelectorAll("a,button,input,[role='button'],[onclick]")].filter(visible);
    const candidateControls = controls.filter(el => {
        const text = norm(textOf(el));
        if (!text) return false;
        return labels.some(label => text === label || text.includes(label)) || /^\d+$/.test(text);
    });

    const containerScore = el => {
        // A real paginator should contain several candidate controls. Score
        // containers by number of candidates plus known label/page-number hits,
        // and mildly penalize very large text blocks.
        const contained = candidateControls.filter(candidate => el.contains(candidate));
        if (contained.length < 2) return 0;
        const text = norm(textOf(el));
        const labelHits = labels.filter(label => text.includes(label)).length;
        const numericHits = (text.match(/\b\d+\b/g) || []).length;
        return contained.length * 10 + labelHits * 5 + numericHits - Math.min(text.length / 200, 20);
    };

    const containers = [];
    for (const candidate of candidateControls) {
        // Walk upward from each candidate to find a common compact container.
        let cur = candidate.parentElement;
        while (cur && cur !== document.body && cur !== document.documentElement) {
            const score = containerScore(cur);
            if (score > 0) containers.push({ el: cur, score });
            cur = cur.parentElement;
        }
    }

    const container = containers.sort((a, b) => b.score - a.score)[0]?.el || null;
    const candidates = (container ? candidateControls.filter(el => container.contains(el)) : candidateControls)
        .map((el, index) => ({
            index,
            text: textOf(el),
            href: el.href || "",
            onclick: el.getAttribute("onclick") || "",
            disabled: Boolean(el.disabled || el.getAttribute("aria-disabled") === "true"),
            className: el.className || "",
            html: (el.outerHTML || "").slice(0, 1000),
        }));

    if (mode === "click_next") {
        // Always prefer the semantic "next page" control. Page numbers are only
        // used by the LLM to understand current/total page state, not as the
        // primary click target.
        const scopedControls = container ? controls.filter(el => container.contains(el)) : controls;
        const candidate = scopedControls.find(el => {
            if (el.disabled || el.getAttribute("aria-disabled") === "true") return false;
            const text = norm(textOf(el));
            if (!text) return false;
            return nextLabels.some(label => text === label || text.includes(label));
        });
        if (!candidate) return { clicked: false };
        candidate.scrollIntoView({ block: "center", inline: "center" });
        candidate.click();
        return { clicked: true, text: textOf(candidate), html: (candidate.outerHTML || "").slice(0, 1000) };
    }

    return {
        container_html: container ? (container.outerHTML || "").slice(0, 12000) : "",
        container_text: container ? textOf(container) : "",
        candidates,
    };
}
