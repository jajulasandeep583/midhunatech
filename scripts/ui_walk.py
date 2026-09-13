import os
from playwright.sync_api import sync_playwright

BASE = "http://dev.localhost:8000"
OUT = "/home/frappe/frappe-bench/shots"
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chromium")
    page = browser.new_page(viewport={"width": 400, "height": 850})
    page.goto(f"{BASE}/midhunatech", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    if page.get_by_text("Sign in to continue").count():
        page.locator("input").first.fill("Administrator")
        page.fill("input[type=password]", "admin")
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_timeout(4000)

    def open_detail(slug, shotname):
        page.goto(f"{BASE}/midhunatech/module/{slug}", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        cards = page.locator(".dl-item")
        if not cards.count():
            print(slug, ": no cards", flush=True)
            return
        cards.first.click()
        page.wait_for_timeout(3500)
        try:
            page.screenshot(path=f"{OUT}/{shotname}.png", timeout=8000,
                            animations="disabled")
            print("shot:", shotname, flush=True)
        except Exception as e:
            print("shot failed:", shotname, str(e)[:60], flush=True)
        btns = page.locator(".dl-act")
        print(slug, "buttons:",
              [btns.nth(i).inner_text() for i in range(btns.count())], flush=True)

    open_detail("journal_entry", "je-detail")
    open_detail("purchase_invoice", "pinv-detail")
    browser.close()
print("done", flush=True)
