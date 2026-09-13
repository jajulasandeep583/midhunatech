"""Real UI click regression test — logs in through the app's own PWA login
screen and performs every lifecycle action with genuine taps.

    MT_BASE=http://dev.localhost:8000 ~/pwtest/bin/python scripts/ui_click_test.py
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("MT_BASE", "http://dev.localhost:8000")
results = []


def check(label, ok, detail=""):
    results.append((label, ok, detail))
    print(("  [OK]   " if ok else "  [FAIL] ") + label + (f" — {detail}" if detail else ""),
          flush=True)


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chromium")
    page = browser.new_page(viewport={"width": 400, "height": 850})

    # ── login through the app's own screen ──
    page.goto(f"{BASE}/midhunatech", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    if page.get_by_text("Sign in to continue").count():
        page.locator("input").first.fill("Administrator")
        page.fill("input[type=password]", "admin")
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_timeout(5000)
    check("login via the PWA login screen",
          not page.get_by_text("Sign in to continue").count())

    def open_list(slug):
        page.goto(f"{BASE}/midhunatech/module/{slug}", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)

    def open_card(has_text=None, index=0):
        loc = page.locator(".dl-item", has_text=has_text) if has_text else page.locator(".dl-item")
        if not loc.count():
            return False
        loc.nth(index).click()
        page.wait_for_timeout(3000)
        return True

    def buttons():
        b = page.locator(".dl-act")
        return [b.nth(i).inner_text() for i in range(b.count())]

    def tap(label):
        b = page.locator(".dl-act", has_text=label)
        if not b.count():
            return False
        b.first.click()
        page.wait_for_timeout(1000)
        return True

    def confirm_yes():
        """Accept the confirmation dialog if one appeared."""
        y = page.locator(".dl-confirm-yes")
        if not y.count():
            return False
        y.click()
        page.wait_for_timeout(6000)
        return True

    def close_sheet():
        c = page.get_by_role("button", name="Close")
        if c.count():
            c.first.click()
            page.wait_for_timeout(1200)

    def chip():
        c = page.locator(".dl-badge")
        return c.first.inner_text() if c.count() else "(none)"

    # ── 1. CREATE + SUBMIT a quotation with real taps ──
    open_list("quotation")
    page.locator(".dl-fab").click()
    page.wait_for_timeout(3500)
    page.locator(".df-link input").first.fill("MT Test Customer")
    page.wait_for_timeout(1500)
    opt = page.locator(".df-link-list li")
    if opt.count():
        opt.first.click()
    page.wait_for_timeout(600)
    # line item: item_code + qty
    item_inputs = page.locator(".df-item-card .df-link input")
    if item_inputs.count():
        item_inputs.first.fill("MT-TEST-ITEM")
        page.wait_for_timeout(1500)
        o2 = page.locator(".df-link-list li")
        if o2.count():
            o2.first.click()
    qty = page.locator(".df-item-card input[type=number]")
    if qty.count():
        qty.first.fill("3")
    page.wait_for_timeout(400)
    page.locator(".df-submit").click()       # ✓ Create & Submit
    page.wait_for_timeout(8000)
    created_ok = page.locator(".dl-detail-title").count() > 0
    check("create + submit a quotation by tapping the form", created_ok,
          f"status {chip()}" if created_ok else "sheet did not open")

    # ── 2. CANCEL it (dialog) ──
    if created_ok:
        tapped = tap("Cancel")
        dialog = page.locator(".dl-confirm-yes").count() > 0
        check("Cancel opens a confirmation dialog", tapped and dialog)
        confirm_yes()
        check("Cancel completes", chip() == "Cancelled", f"status {chip()}")

        # ── 3. AMEND it ──
        tapped = tap("Amend")
        page.wait_for_timeout(6000)
        after = buttons()
        check("Amend creates an editable draft", tapped and "✓ Submit" in " ".join(after),
              ", ".join(after))

        # ── 4. DELETE the amended draft (dialog) ──
        tapped = tap("Delete")
        dialog = page.locator(".dl-confirm-yes").count() > 0
        check("Delete opens a confirmation dialog", tapped and dialog)
        confirm_yes()
        check("Delete closes the sheet", page.locator(".dl-detail-title").count() == 0)

    # ── 5. every tile: buttons render for the first record ──
    for slug in ("items", "customers", "suppliers", "sales_order", "sales_invoice",
                 "purchase_invoice", "payments", "journal_entry", "accounts"):
        open_list(slug)
        if open_card():
            b = buttons()
            check(f"{slug}: action buttons render", len(b) >= 3, ", ".join(b))
            close_sheet()
        else:
            check(f"{slug}: list has records", False, "no cards")

    browser.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed.", flush=True)
sys.exit(1 if failed else 0)
