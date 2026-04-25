#!/usr/bin/env python3

import sys

from playwright.sync_api import sync_playwright


url = sys.argv[1] if len(sys.argv) > 1 else "https://www.scholat.com/org/PKUDAIR#"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")

    print("title:", page.title())
    print("url:", page.url)
    print("text:")
    print(page.locator("body").inner_text()[:2000])

    print("\nlinks:")
    for link in page.locator("a").evaluate_all(
        """els => els.slice(0, 20).map(a => ({
            text: a.innerText.trim(),
            href: a.href
        }))"""
    ):
        print(f"- {link['text'] or '(no text)'} -> {link['href']}")

    browser.close()
