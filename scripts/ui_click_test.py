"""Real-finger UI regression test on an emulated phone.

Runs the complete SALES INVOICE lifecycle the way a user does — every step
is a touch tap, native confirm dialogs are accepted like a person tapping
OK — then checks the action buttons of every other tile.

    MT_BASE=http://dev.localhost:8000 ~/pwtest/bin/python scripts/ui_click_test.py
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("MT_BASE", "http://dev.localhost:8000")
CUSTOMER = "MT Test Customer"
ITEM = "MT-TEST-ITEM"
results = []


def check(label, ok, detail=""):
    results.append((label, ok, detail))
    print(("  [OK]   " if ok else "  [FAIL] ") + label + (f" — {detail}" if detail else ""),
          flush=True)


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chromium")
    ctx = browser.new_context(**p.devices["Pixel 5"])   # touch + mobile viewport
    page = ctx.new_page()
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message.split("\n")[0]), d.accept()))

    # ── login through the app's own screen ──
    page.goto(f"{BASE}/midhunatech", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    if page.get_by_text("Sign in to continue").count():
        page.locator("input").first.fill("Administrator")
        page.fill("input[type=password]", "admin")
        page.get_by_role("button", name="Sign in").tap()
        page.wait_for_timeout(5000)
    check("login via the PWA login screen",
          not page.get_by_text("Sign in to continue").count())

    def open_list(slug):
        page.goto(f"{BASE}/midhunatech/module/{slug}", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)

    def buttons():
        b = page.locator(".dl-act")
        return [b.nth(i).inner_text() for i in range(b.count())]

    def tap(label, wait=6000):
        b = page.locator(".dl-act", has_text=label)
        if not b.count():
            return False
        b.first.tap()
        page.wait_for_timeout(wait)
        return True

    def chip():
        c = page.locator(".dl-badge")
        return c.first.inner_text() if c.count() else "(none)"

    def pick_link(locator, value):
        locator.fill(value)
        page.wait_for_timeout(1500)
        opts = page.locator(".df-link-list li")
        if opts.count():
            opts.first.tap()
            page.wait_for_timeout(500)

    # ══ SALES INVOICE — the full lifecycle, by touch ══
    open_list("sales_invoice")
    page.locator(".dl-fab").tap()
    page.wait_for_timeout(3500)
    pick_link(page.locator(".df-link input").first, CUSTOMER)
    item_input = page.locator(".df-item-card .df-link input")
    if item_input.count():
        pick_link(item_input.first, ITEM)
    nums = page.locator(".df-item-card input[type=number]")
    if nums.count() >= 1:
        nums.nth(0).fill("4")          # qty
    if nums.count() >= 2:
        nums.nth(1).fill("250")        # rate
    page.wait_for_timeout(400)
    page.locator(".df-submit").tap()   # ✓ Create & Submit
    page.wait_for_timeout(9000)
    opened = page.locator(".dl-detail-title").count() > 0
    inv = page.locator(".dl-detail-title").first.inner_text() if opened else ""
    check("Sales Invoice: created AND submitted by tapping the form",
          opened and chip() in ("Unpaid", "Overdue"), f"{inv} status {chip()}")

    # payment (partial) — outstanding should drop, status -> Partly Paid
    if opened:
        tap("Payment", 2500)
        amt = page.locator(".dl-email input[type=number]")
        if amt.count():
            amt.first.fill("100")
        page.locator(".dl-email-send").tap()
        page.wait_for_timeout(8000)
        check("Sales Invoice: payment recorded by tapping",
              chip() in ("Partly Paid", "Paid"), f"status {chip()}")

        # cancel — one tap, no confirmation step
        tapped = tap("Cancel", 8000)
        check("Sales Invoice: cancelled with one tap",
              tapped and chip() == "Cancelled", f"status {chip()}")

        # amend -> editable draft
        tapped = tap("Amend", 8000)
        after = buttons()
        check("Sales Invoice: amended into an editable draft",
              tapped and "✓ Submit" in " ".join(after), ", ".join(after))

        # delete the amended draft — one tap
        tapped = tap("Delete", 8000)
        check("Sales Invoice: draft deleted with one tap",
              tapped and page.locator(".dl-detail-title").count() == 0)

    # ══ every other tile: buttons present for its first record ══
    for slug in ("items", "customers", "suppliers", "quotation", "sales_order",
                 "delivery_note", "material_request", "purchase_order",
                 "purchase_receipt", "purchase_invoice", "stock_entry",
                 "warehouses", "payments", "journal_entry", "accounts"):
        open_list(slug)
        cards = page.locator(".dl-item")
        if cards.count():
            cards.first.tap()
            page.wait_for_timeout(3000)
            b = buttons()
            check(f"{slug}: action buttons render", len(b) >= 3, ", ".join(b))
            c = page.get_by_role("button", name="Close")
            if c.count():
                c.first.tap()
                page.wait_for_timeout(1000)
        else:
            check(f"{slug}: list has records", False, "no cards")

    browser.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed.", flush=True)
sys.exit(1 if failed else 0)
