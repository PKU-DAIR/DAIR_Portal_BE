({ maxChars = 6000, minChars = 1000, maxHtmlChars = 4000 }) => {
    // This script runs in the browser via Playwright.
    //
    // Goal:
    // 1. Keep publication entries grouped with nearby year/venue context.
    // 2. Split extremely long pages into medium DOM-aligned blocks so each block
    //    can fit into one LLM call.
    // 3. Avoid brittle selector assumptions because different lab pages use very
    //    different markup: paragraphs, list items, cards, tables, etc.
    const normalize = value => (value || "").replace(/\s+/g, " ").trim();

    const isVisible = el => {
        if (!el || !el.isConnected) return false;
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    };

    const splitText = (text, tag) => {
        // Last-resort fallback when one node is still too large even after
        // descending the DOM tree. We split by lines/sentences rather than raw
        // character windows to reduce the chance of cutting one citation apart.
        const pieces = normalize(text).split(/\n+|(?<=\.)\s+/).filter(Boolean);
        if (!pieces.length) return [];

        const chunks = [];
        let current = "";
        for (const piece of pieces) {
            const next = current ? `${current}\n${piece}` : piece;
            if (next.length > maxChars && current) {
                chunks.push({ tag, text: current.trim(), html: "" });
                current = piece;
            } else {
                current = next;
            }
        }
        if (current.trim()) chunks.push({ tag, text: current.trim(), html: "" });
        return chunks;
    };

    const flushBuffer = (chunks, buffer, tag) => {
        const text = normalize(buffer.map(item => item.text).join("\n\n"));
        const html = buffer.map(item => item.html).join("\n");
        if (!text) return;
        chunks.push({
            tag,
            text,
            html: html.slice(0, maxHtmlChars),
        });
    };

    const splitNode = (node, depth = 0) => {
        if (!node || !isVisible(node)) return [];

        const tag = (node.tagName || "div").toLowerCase();
        const text = normalize(node.innerText || "");
        const html = (node.innerHTML || "").trim();
        if (!text) return [];

        if (text.length <= maxChars) {
            return [{ tag, text, html: html.slice(0, maxHtmlChars) }];
        }

        const children = Array.from(node.children || []).filter(child => {
            return isVisible(child) && normalize(child.innerText || "");
        });

        if (!children.length || depth >= 6) {
            return splitText(text, tag);
        }

        const chunks = [];
        let buffer = [];
        let bufferLen = 0;
        for (const child of children) {
            const childText = normalize(child.innerText || "");
            const childHtml = (child.outerHTML || "").trim();
            if (!childText) continue;

            if (childText.length > maxChars) {
                if (buffer.length) {
                    flushBuffer(chunks, buffer, tag);
                    buffer = [];
                    bufferLen = 0;
                }
                chunks.push(...splitNode(child, depth + 1));
                continue;
            }

            if (bufferLen + childText.length > maxChars && bufferLen >= minChars) {
                flushBuffer(chunks, buffer, tag);
                buffer = [{ text: childText, html: childHtml }];
                bufferLen = childText.length;
                continue;
            }

            buffer.push({ text: childText, html: childHtml });
            bufferLen += childText.length;
        }

        if (buffer.length) flushBuffer(chunks, buffer, tag);
        if (!chunks.length) return splitText(text, tag);
        return chunks;
    };

    // Prefer `main` when present because it usually excludes nav/sidebar noise.
    const roots = [];
    const main = document.querySelector("main");
    if (main) {
        roots.push(main);
    } else {
        roots.push(...Array.from(document.body.children || []));
    }
    if (!roots.length) roots.push(document.body);

    const chunks = [];
    for (const root of roots) {
        chunks.push(...splitNode(root, 0));
    }
    return chunks;
};
