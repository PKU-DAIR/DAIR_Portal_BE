({ titles = [], features = null }) => {
    // This script runs inside the browser page via Playwright.
    //
    // Goal:
    // 1. On the first page, use known title strings to learn repeated card-item
    //    selectors/XPath patterns.
    // 2. On later pages, reuse those features to collect card HTML without
    //    calling the LLM again.
    //
    // It deliberately does not extract link/date/image fields. The Python
    // finalizer sends all card HTML to the LLM once at the end.
    const norm = value => (value || "").replace(/\s+/g, " ").trim();

    // Compact element signature used for class-based card matching.
    // Example: <div class="profile-article active"> -> div|active.profile-article
    const signature = el => {
        if (!el) return "";
        const cls = [...el.classList].sort().join(".");
        return `${el.tagName.toLowerCase()}|${cls}`;
    };
    const hasClassSignature = sig => sig && sig.includes("|") && sig.split("|")[1];
    const matchesSignature = (el, sig) => signature(el) === sig;
    const shortHtml = el => (el.outerHTML || "").slice(0, 12000);

    // Visibility checks are important because some pages embed article data in
    // hidden blocks. Hidden text can match titles but should not be used to learn
    // visual card layout.
    const visibleElement = el => {
        if (!el || !el.isConnected) return false;
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;

        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    };

    const hasHiddenAncestor = el => {
        let cur = el;
        while (cur && cur !== document.body && cur !== document.documentElement) {
            const style = window.getComputedStyle(cur);
            if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
                return true;
            }
            cur = cur.parentElement;
        }
        return false;
    };

    const textNodes = () => {
        // TreeWalker lets us find exact text-node matches even when titles are
        // nested inside anchors/spans rather than directly in card elements.
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        return nodes;
    };

    const findTitleElement = title => {
        // Return the smallest visible element that contains the title text.
        // Hidden matches are skipped instead of climbing to a visible ancestor;
        // otherwise a hidden data blob could incorrectly map to the whole page.
        const target = norm(title);
        if (!target) return null;
        const matches = [];

        for (const node of textNodes()) {
            if (norm(node.textContent).includes(target)) {
                if (hasHiddenAncestor(node.parentElement)) continue;

                let el = node.parentElement;
                while (el && el !== document.body && !visibleElement(el)) {
                    el = el.parentElement;
                }
                if (visibleElement(el)) matches.push(el);
            }
        }

        return matches.sort((a, b) => {
            // Prefer the smallest visible match: usually the <a> or text wrapper.
            const ar = a.getBoundingClientRect();
            const br = b.getBoundingClientRect();
            return (ar.width * ar.height) - (br.width * br.height);
        })[0] || null;
    };

    const ancestors = el => {
        // Ordered from nearest ancestor to outer containers. Pair matching stops
        // at the first suitable sibling level, so this order favors item-level
        // cards over list-level wrappers.
        const result = [];
        let cur = el;
        while (cur && cur !== document.body && cur !== document.documentElement) {
            result.push(cur);
            cur = cur.parentElement;
        }
        return result;
    };

    const featureGroupsFrom = value => {
        // Accept both the current shape (`card_groups`) and older fallback
        // shapes so saved state/debug runs do not break immediately.
        if (!value) return [];
        if (Array.isArray(value.card_groups)) return value.card_groups;
        if (Array.isArray(value.signatures)) {
            return value.signatures.map(sig => ({ card_signature: sig, matches: 1 }));
        }
        if (value.card_signature) return [value];
        return [];
    };

    const classPredicate = el => {
        // XPath-safe class matching. We cannot use `@class="..."` because class
        // order may differ and elements often have multiple classes.
        const classes = [...el.classList];
        if (!classes.length) return "";
        return classes
            .map(cls => `contains(concat(' ', normalize-space(@class), ' '), ' ${cls} ')`)
            .join(" and ");
    };

    const absoluteXPath = el => {
        // Build a stable absolute-ish XPath. If an id appears, stop there; above
        // that point is usually irrelevant and more brittle.
        const parts = [];
        let cur = el;
        while (cur && cur.nodeType === Node.ELEMENT_NODE) {
            const tag = cur.tagName.toLowerCase();
            if (cur.id) {
                parts.unshift(`${tag}[@id="${cur.id}"]`);
                break;
            }
            if (!cur.parentElement) {
                parts.unshift(tag);
                break;
            }

            const siblings = [...cur.parentElement.children].filter(child => {
                return child.tagName === cur.tagName;
            });
            const index = siblings.length > 1 ? `[${siblings.indexOf(cur) + 1}]` : "";
            parts.unshift(`${tag}${index}`);
            cur = cur.parentElement;
        }
        return `//${parts.join("/")}`;
    };

    const relativeXPath = (ancestor, desc) => {
        // Describe how to get from an anonymous wrapper to the real card child.
        // This handles markup like: <div><div class="profile-article">...</div></div>
        const parts = [];
        let cur = desc;
        while (cur && cur !== ancestor && cur.nodeType === Node.ELEMENT_NODE) {
            const tag = cur.tagName.toLowerCase();
            const predicate = classPredicate(cur);
            parts.unshift(predicate ? `${tag}[${predicate}]` : tag);
            cur = cur.parentElement;
        }
        return cur === ancestor ? `./${parts.join("/")}` : "";
    };

    const evaluateXPath = xpath => {
        // XPathResult snapshots are easier to convert to arrays than iterators
        // and remain stable while we loop through them.
        const result = document.evaluate(
            xpath,
            document,
            null,
            XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
            null
        );
        const nodes = [];
        for (let i = 0; i < result.snapshotLength; i++) {
            nodes.push(result.snapshotItem(i));
        }
        return nodes;
    };

    const addFeature = (featuresByKey, feature, a, b) => {
        // Multiple title pairs can point to the same card XPath. Aggregate those
        // hits as `matches`; higher counts mean the feature is more reliable.
        if (!feature || !hasClassSignature(feature.card_signature)) return;

        const existing = featuresByKey.get(feature.xpath) || {
            ...feature,
            matches: 0,
            example_titles: [],
        };

        existing.matches += 1;
        for (const title of [a.title, b.title]) {
            if (title && !existing.example_titles.includes(title)) {
                existing.example_titles.push(title);
            }
        }
        featuresByKey.set(feature.xpath, existing);
    };

    const areSiblings = (a, b) => {
        // A repeated list item normally appears as sibling wrappers/cards under
        // one parent container.
        return a && b && a !== b && a.parentElement && a.parentElement === b.parentElement;
    };

    const rectAligned = (a, b) => {
        // Sibling items in a vertical list share left/right alignment; items in a
        // grid may share top/bottom alignment. A small tolerance absorbs subpixel
        // layout differences.
        const ar = a.getBoundingClientRect();
        const br = b.getBoundingClientRect();
        const tolerance = Math.max(8, Math.min(window.innerWidth, window.innerHeight) * 0.01);

        const leftAligned = Math.abs(ar.left - br.left) <= tolerance;
        const rightAligned = Math.abs(ar.right - br.right) <= tolerance;
        const topAligned = Math.abs(ar.top - br.top) <= tolerance;
        const bottomAligned = Math.abs(ar.bottom - br.bottom) <= tolerance;

        return leftAligned || rightAligned || topAligned || bottomAligned;
    };

    const cardWithinWrapper = (wrapper, titleEl) => {
        // If the sibling level is an anonymous wrapper, find the stable classed
        // element inside it that actually represents the card.
        for (const el of ancestors(titleEl)) {
            if (el === wrapper) break;
            if (el.parentElement === wrapper && hasClassSignature(signature(el))) return el;
        }

        for (const el of ancestors(titleEl)) {
            if (el === wrapper) break;
            if (hasClassSignature(signature(el))) return el;
        }

        return null;
    };

    const findSiblingCardFeature = (left, right) => {
        // Core learning rule:
        // for each pair of known titles, walk upward until we find aligned
        // sibling ancestors. If those siblings are anonymous wrappers, record the
        // relative path to the classed card child inside each wrapper.
        for (const a of ancestors(left.el)) {
            if (!a.parentElement) continue;

            for (const b of ancestors(right.el)) {
                if (!areSiblings(a, b)) continue;
                if (!rectAligned(a, b)) continue;

                const siblingsAreCards = hasClassSignature(signature(a)) && matchesSignature(b, signature(a));
                const leftCard = siblingsAreCards ? a : cardWithinWrapper(a, left.el);
                const rightCard = siblingsAreCards ? b : cardWithinWrapper(b, right.el);
                if (!leftCard || !rightCard) continue;
                if (!matchesSignature(rightCard, signature(leftCard))) continue;

                const parentXPath = absoluteXPath(a.parentElement);
                const cardXPath = siblingsAreCards ? "." : relativeXPath(a, leftCard);
                if (!cardXPath) continue;
                const cardQuery = siblingsAreCards
                    ? `*[${classPredicate(leftCard)}]`
                    : `*/${cardXPath.replace(/^\.\//, "")}`;

                return {
                    // Human-readable class signature for logs/debugging.
                    card_signature: signature(leftCard),
                    // Parent of the repeated wrappers/cards.
                    wrapper_parent_xpath: parentXPath,
                    // Path from one wrapper to its card child; "." means the
                    // sibling itself is the card.
                    card_relative_xpath: cardXPath,
                    // Full XPath used by later pages to collect cards.
                    xpath: `${parentXPath}/${cardQuery}`,
                };
            }
        }

        return null;
    };

    const learnFeaturesByTitlePairs = titleRecords => {
        // Compare every pair: a/b, a/c, b/c, ... . Noise in title candidates is
        // tolerated because real repeated card features accumulate more matches.
        const featuresByKey = new Map();

        for (let i = 0; i < titleRecords.length; i++) {
            for (let j = i + 1; j < titleRecords.length; j++) {
                const feature = findSiblingCardFeature(titleRecords[i], titleRecords[j]);
                if (feature) addFeature(featuresByKey, feature, titleRecords[i], titleRecords[j]);
            }
        }

        return [...featuresByKey.values()].sort((a, b) => b.matches - a.matches);
    };

    const collectCardsByFeatures = groups => {
        // Prefer XPath features because they can express anonymous wrappers. If
        // older state only has a class signature, fall back to full-page class
        // matching.
        const seen = new Set();
        const cards = [];

        for (const group of groups) {
            if (group.xpath) {
                for (const el of evaluateXPath(group.xpath)) {
                    if (seen.has(el)) continue;
                    const text = norm(el.innerText || el.textContent);
                    if (!text) continue;

                    seen.add(el);
                    cards.push(el);
                }
                continue;
            }

            for (const el of [...document.querySelectorAll("*")]) {
                if (!matchesSignature(el, group.card_signature) || seen.has(el)) continue;
                const text = norm(el.innerText || el.textContent);
                if (!text) continue;

                seen.add(el);
                cards.push(el);
            }
        }

        return cards;
    };

    const titleRecords = titles
        // First-page learning requires visible DOM title elements. Later pages
        // normally pass no titles and reuse `features`.
        .map(title => ({ title, el: findTitleElement(title) }))
        .filter(record => record.el);

    const existingGroups = featureGroupsFrom(features);
    const learnedGroups = existingGroups.length ? existingGroups : learnFeaturesByTitlePairs(titleRecords);
    const cards = collectCardsByFeatures(learnedGroups);
    const activeFeatures = learnedGroups.length ? { card_groups: learnedGroups } : null;

    const seenItems = new Set();
    const items = cards.map(card => {
        // Return only minimal card data. Final field extraction is intentionally
        // delayed to one LLM call after all pages are collected.
        const text = norm(card.innerText || card.textContent);
        const matchedTitle = titles.find(title => text.includes(norm(title))) || "";

        return {
            title: matchedTitle || text.slice(0, 160),
            text: text.slice(0, 1000),
            html: shortHtml(card),
        };
    }).filter(item => {
        const key = `${item.title}|${item.text.slice(0, 120)}`;
        if (!item.title || seenItems.has(key)) return false;
        seenItems.add(key);
        return true;
    });

    return {
        features: activeFeatures,
        cards: items,
    };
}
