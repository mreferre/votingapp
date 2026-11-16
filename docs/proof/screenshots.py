"""Capture proof screenshots of /votes with headless Chromium (Playwright).

Usage: python docs/proof/screenshots.py http://127.0.0.1:8081 <password>
"""
import os
import sys

from playwright.sync_api import sync_playwright

base, password = sys.argv[1], sys.argv[2]
out = os.path.dirname(os.path.abspath(__file__))

with sync_playwright() as p:
    browser = p.chromium.launch()
    for device, size in {"desktop": (1280, 900), "mobile": (390, 844)}.items():
        for scheme in ("light", "dark"):
            ctx = browser.new_context(
                viewport={"width": size[0], "height": size[1]},
                color_scheme=scheme,
                http_credentials={"username": "demo", "password": password},
            )
            page = ctx.new_page()
            page.goto(base + "/votes")
            page.screenshot(path=f"{out}/votes-{device}-{scheme}.png", full_page=True)
            ctx.close()

    # Vote click without reload: before / after on desktop light.
    ctx = browser.new_context(viewport={"width": 1280, "height": 900},
                              http_credentials={"username": "demo", "password": password})
    page = ctx.new_page()
    page.goto(base + "/votes")
    marker = page.evaluate("window.__noReload = 1")
    card = page.locator('.card[data-slug="chipotle"]')
    before = card.locator("[data-count]").inner_text()
    page.screenshot(path=f"{out}/vote-before.png")
    card.get_by_role("button").click()
    page.wait_for_function(
        "b => document.querySelector('.card[data-slug=chipotle] [data-count]').textContent !== b", arg=before)
    after = card.locator("[data-count]").inner_text()
    card.get_by_role("button").focus()
    page.screenshot(path=f"{out}/vote-after.png")
    print(f"chipotle before={before} after={after} no_reload={page.evaluate('window.__noReload') == 1}")
    print("status line:", page.locator("#status").inner_text())

    # Visible error handling: make the vote request fail.
    page.route("**/votes/vote/*", lambda route: route.fulfill(
        status=502, content_type="application/json", body='{"error": "Could not record your vote."}'))
    card.get_by_role("button").click()
    page.wait_for_selector("#error:not([hidden])")
    print("error banner:", page.locator("#error").inner_text())
    page.screenshot(path=f"{out}/vote-error.png")
    browser.close()
