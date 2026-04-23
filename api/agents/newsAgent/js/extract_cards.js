({ titles = [], features = null }) => {
    const norm = value => (value || "").replace(/\s+/g, " ").trim();
    const signature = el => {
        if (!el) return "";
        const cls = [...el.classList].sort().join(".");
        return `${el.tagName.toLowerCase()}|${cls}`;
    };
    const matchesSignature = (el, sig) => !sig || signature(el) === sig;
    const shortHtml = el => (el.outerHTML || "").slice(0, 12000);

    const textNodes = () => {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        return nodes;
    };

    const findTitleElement = title => {
        const target = norm(title);
        if (!target) return null;

        for (const node of textNodes()) {
            if (norm(node.textContent).includes(target)) {
                return node.parentElement;
            }
        }
        return null;
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

    const findTitleInCard = (card, activeFeatures) => {
        if (activeFeatures && activeFeatures.title_signature) {
            const matched = [...card.querySelectorAll("*")].find(el => {
                return matchesSignature(el, activeFeatures.title_signature) && norm(el.innerText || el.textContent);
            });
            if (matched) return matched;
        }

        return card.querySelector("h1,h2,h3,h4,h5,h6,a") || card;
    };

    const learnFeatures = () => {
        const titleElements = titles.map(findTitleElement).filter(Boolean);
        let learned = null;
        let fallback = null;

        for (let i = 0; i < titleElements.length; i++) {
            for (let j = i + 1; j < titleElements.length; j++) {
                for (const a of ancestors(titleElements[i])) {
                    for (const b of ancestors(titleElements[j])) {
                        const sameParent = a !== b && a.parentElement && a.parentElement === b.parentElement;
                        if (!sameParent) continue;

                        fallback = fallback || {
                            card_signature: signature(a),
                            card_parent_signature: signature(a.parentElement),
                            title_signature: signature(titleElements[i]),
                        };

                        if (signature(a) === signature(b)) {
                            learned = {
                                card_signature: signature(a),
                                card_parent_signature: signature(a.parentElement),
                                title_signature: signature(titleElements[i]),
                            };
                            break;
                        }
                    }
                    if (learned) break;
                }
                if (learned) break;
            }
            if (learned) break;
        }

        if (learned || fallback) return learned || fallback;

        if (titleElements[0]) {
            return {
                card_signature: signature(titleElements[0]),
                card_parent_signature: signature(titleElements[0].parentElement),
                title_signature: signature(titleElements[0]),
            };
        }

        return null;
    };

    const activeFeatures = features && features.card_signature ? features : learnFeatures();
    let cards = [];

    if (activeFeatures) {
        const parents = [...document.querySelectorAll("*")].filter(el => {
            return matchesSignature(el, activeFeatures.card_parent_signature);
        });

        for (const parent of parents) {
            const children = [...parent.children].filter(el => {
                return matchesSignature(el, activeFeatures.card_signature);
            });
            if (children.length) cards.push(...children);
        }

        if (!cards.length) {
            cards = [...document.querySelectorAll("*")].filter(el => {
                return matchesSignature(el, activeFeatures.card_signature);
            });
        }
    }

    const seen = new Set();
    const items = cards.map(card => {
        const text = norm(card.innerText);
        const titleElement = findTitleInCard(card, activeFeatures);
        const titleText = norm(titleElement && (titleElement.innerText || titleElement.textContent));
        const matchedTitle = titles.find(title => text.includes(norm(title))) || "";
        const link = (titleElement && titleElement.closest("a[href]")) || card.querySelector("a[href]");
        const img = card.querySelector("img");
        const dateMatch = text.match(/(?:20|19)\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?|(?:20|19)\d{2}[-/.年]\d{1,2}/);

        return {
            title: matchedTitle || titleText,
            published_at: dateMatch ? dateMatch[0] : "",
            link: link ? link.href : "",
            image: img ? (img.currentSrc || img.src) : "",
            text: text.slice(0, 1000),
            html: shortHtml(card),
        };
    }).filter(item => {
        const key = `${item.title}|${item.link}|${item.text.slice(0, 80)}`;
        if (!item.title || seen.has(key)) return false;
        seen.add(key);
        return true;
    });

    return {
        features: activeFeatures,
        cards: items,
    };
}
