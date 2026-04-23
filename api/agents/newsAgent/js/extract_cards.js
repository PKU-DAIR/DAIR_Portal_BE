({ titles = [], features = null }) => {
    const norm = value => (value || "").replace(/\s+/g, " ").trim();
    const signature = el => {
        if (!el) return "";
        const cls = [...el.classList].sort().join(".");
        return `${el.tagName.toLowerCase()}|${cls}`;
    };
    const hasClassSignature = sig => sig && sig.includes("|") && sig.split("|")[1];
    const matchesSignature = (el, sig) => signature(el) === sig;
    const shortHtml = el => (el.outerHTML || "").slice(0, 12000);
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
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        return nodes;
    };

    const findTitleElement = title => {
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
            const ar = a.getBoundingClientRect();
            const br = b.getBoundingClientRect();
            return (ar.width * ar.height) - (br.width * br.height);
        })[0] || null;
    };

    const ancestors = el => {
        const result = [];
        let cur = el;
        while (cur && cur !== document.body && cur !== document.documentElement) {
            result.push(cur);
            cur = cur.parentElement;
        }
        return result;
    };

    const featureGroupsFrom = value => {
        if (!value) return [];
        if (Array.isArray(value.card_groups)) return value.card_groups;
        if (Array.isArray(value.signatures)) {
            return value.signatures.map(sig => ({ card_signature: sig, matches: 1 }));
        }
        if (value.card_signature) return [value];
        return [];
    };

    const classPredicate = el => {
        const classes = [...el.classList];
        if (!classes.length) return "";
        return classes
            .map(cls => `contains(concat(' ', normalize-space(@class), ' '), ' ${cls} ')`)
            .join(" and ");
    };

    const absoluteXPath = el => {
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
        return a && b && a !== b && a.parentElement && a.parentElement === b.parentElement;
    };

    const rectAligned = (a, b) => {
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
                    card_signature: signature(leftCard),
                    wrapper_parent_xpath: parentXPath,
                    card_relative_xpath: cardXPath,
                    xpath: `${parentXPath}/${cardQuery}`,
                };
            }
        }

        return null;
    };

    const learnFeaturesByTitlePairs = titleRecords => {
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
        .map(title => ({ title, el: findTitleElement(title) }))
        .filter(record => record.el);

    const existingGroups = featureGroupsFrom(features);
    const learnedGroups = existingGroups.length ? existingGroups : learnFeaturesByTitlePairs(titleRecords);
    const cards = collectCardsByFeatures(learnedGroups);
    const activeFeatures = learnedGroups.length ? { card_groups: learnedGroups } : null;

    const seenItems = new Set();
    const items = cards.map(card => {
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
