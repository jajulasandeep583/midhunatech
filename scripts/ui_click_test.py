"""Real UI click test: log in through the app, Submit / Cancel / Record
Payment with actual taps. Run with the pwtest venv:
    MT_BASE=http://dev.localhost:8000 ~/pwtest/bin/python scripts/ui_click_test.py
"""
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("MT_BASE", "http://dev.localhost:8000")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chromium")
    page = browser.new_page(viewport={"width": 400, "height": 850})
    page.goto(f"{BASE}/midhunatech", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    if page.get_by_text("Sign in to continue").count():
        page.locator("input").first.fill("Administrator")
        page.fill("input[type=password]", "admin")
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_timeout(5000)

    def open_first(slug, has_text=None):
        page.goto(f"{BASE}/midhunatech/module/{slug}", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        loc = page.locator(".dl-item", has_text=has_text) if has_text else page.locator(".dl-item")
        loc.first.click()
        page.wait_for_timeout(3000)

    # 1) SUBMIT a draft journal entry via UI tap
    open_first("journal_entry", "MT smoke expense")
    b = page.locator(".dl-act")
    print("JE buttons before:", [b.nth(i).inner_text() for i in range(b.count())], flush=True)
    sub = page.locator(".dl-act", has_text="Submit")
    if sub.count():
        sub.click()
        page.wait_for_timeout(6000)
    print("JE buttons after Submit tap:",
          [b.nth(i).inner_text() for i in range(b.count())], flush=True)
    page.get_by_role("button", name="Close").click(); page.wait_for_timeout(1200)

    # 2) CANCEL a submitted quotation via UI taps (two-tap confirm)
    open_first("quotation")
    page.locator(".dl-act", has_text="Cancel").click()
    page.wait_for_timeout(700)
    page.locator(".dl-act", has_text="Tap again").click()
    page.wait_for_timeout(6000)
    print("QTN chip after Cancel taps:", page.locator(".dl-badge").first.inner_text(), flush=True)
    page.get_by_role("button", name="Close").click(); page.wait_for_timeout(1200)

    # 3) RECORD PAYMENT on an unpaid purchase invoice via UI taps
    open_first("purchase_invoice", "Unpaid")
    page.locator(".dl-act", has_text="Payment").click()
    page.wait_for_timeout(2500)
    page.locator(".dl-email-send").click()
    page.wait_for_timeout(7000)
    print("PINV chip after Record Payment tap:",
          page.locator(".dl-badge").first.inner_text(), flush=True)
    browser.close()
print("done", flush=True)
