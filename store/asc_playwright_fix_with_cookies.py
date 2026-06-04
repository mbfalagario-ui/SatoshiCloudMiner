#!/usr/bin/env python3
"""Use the user's exported ASC session cookies to navigate the IAP pages
and update the 10 REJECTED en-US localization descriptions via the web
UI (since the API refuses to mutate REJECTED localizations).
"""
from __future__ import annotations
import sys, time, json, pathlib
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

APP_ID = "6773104756"
COOKIES_FILE = "/tmp/asc_cookies.json"
SHOT_DIR = pathlib.Path("/tmp/asc_screens_v2")
SHOT_DIR.mkdir(exist_ok=True, parents=True)

# productId → (new display name, new description, ASC numeric id)
IAPS = [
    ("welcome_199",    "Newcomer Boost",             "One-time 50 GH/s boost credit",   "6773119536"),
    ("rookie_299",     "Daily Booster",              "One-time 100 GH/s boost credit",  "6773119594"),
    ("pro_499",        "Pro Rig",                    "One-time 230 GH/s boost credit",  "6773119538"),
    ("elite_999",      "Elite Rig",                  "One-time 500 GH/s boost credit",  "6773119735"),
    ("ultra_1999",     "Ultra Rig",                  "One-time 1100 GH/s boost credit", "6773119542"),
    ("mega_4999",      "Mega Rig",                   "One-time 2300 GH/s boost credit", "6773119720"),
    ("giga_9999",      "Giga Rig",                   "One-time 3500 GH/s boost credit", "6773119629"),
    ("titan_14999",    "Titan Rig",                  "One-time 4700 GH/s boost credit", "6773119723"),
    ("colossus_19999", "Colossus Rig",               "One-time 7500 GH/s boost credit", "6773119739"),
    ("adfree_399",     "Ad-Free + Priority Support", "Removes ads. Priority support.",  "6773125872"),
]


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def cookies_for_playwright(raw):
    out = []
    for c in raw:
        item = {
            "name":   c["name"],
            "value":  c["value"],
            "domain": c["domain"],
            "path":   c.get("path", "/"),
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
            "sameSite": "Lax",
        }
        if "expirationDate" in c and c["expirationDate"]:
            item["expires"] = int(c["expirationDate"])
        out.append(item)
    return out


def update_iap(page: Page, pid: str, disp: str, desc: str, num_id: str, idx: int) -> bool:
    url = f"https://appstoreconnect.apple.com/apps/{APP_ID}/distribution/iaps/{num_id}"
    log(f"IAP {idx+1}/10 — {pid} — opening")
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    page.screenshot(path=str(SHOT_DIR / f"iap_{idx+1:02d}_{pid}_a_loaded.png"), full_page=False)

    # Look for the page title to confirm we're on the IAP edit page
    title_visible = False
    for sel in [f"h1:has-text('{disp}')",
                f"h2:has-text('{disp}')",
                f":has-text('In-App Purchase')"]:
        try:
            if page.locator(sel).first.is_visible(timeout=2000):
                title_visible = True
                break
        except Exception:
            pass
    log(f"  title visible: {title_visible}")

    # ASC IAP page has localizations table. Each row has the language and a
    # "Edit" pencil button. Find the "English (U.S.)" row and click it (or
    # its Edit button).
    en_us_locator = None
    for sel in [
        "text=English (U.S.)",
        "td:has-text('English (U.S.)')",
        "[aria-label*='English (U.S.)' i]",
        "div:has-text('English (U.S.)')",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=3000):
                en_us_locator = loc
                break
        except Exception:
            pass

    if not en_us_locator:
        page.screenshot(path=str(SHOT_DIR / f"iap_{idx+1:02d}_{pid}_b_no_enus.png"), full_page=True)
        log(f"  ❌ no 'English (U.S.)' row found")
        return False

    # Try clicking it
    try:
        en_us_locator.click()
        page.wait_for_timeout(2500)
    except Exception as e:
        log(f"  could not click row: {e}")
        # Try clicking nearest Edit button
        try:
            edit_btn = page.get_by_role("button", name="Edit").first
            edit_btn.click()
            page.wait_for_timeout(2500)
        except Exception:
            pass

    page.screenshot(path=str(SHOT_DIR / f"iap_{idx+1:02d}_{pid}_c_clicked_enus.png"), full_page=False)

    # Now find the description textarea
    desc_field = None
    for sel in [
        'textarea[aria-label*="description" i]',
        'textarea[id*="description" i]',
        'textarea[name*="description" i]',
        'textarea',
    ]:
        try:
            locs = page.locator(sel)
            cnt = locs.count()
            for i in range(cnt):
                el = locs.nth(i)
                if el.is_visible(timeout=1000):
                    desc_field = el
                    break
            if desc_field:
                break
        except Exception:
            pass

    if not desc_field:
        page.screenshot(path=str(SHOT_DIR / f"iap_{idx+1:02d}_{pid}_d_no_field.png"), full_page=True)
        log(f"  ❌ description field not found")
        return False

    log(f"  found description field — clearing + typing new value")
    try:
        # Focus the textarea with force-click (bypass overlay interception)
        desc_field.click(force=True, timeout=5000)
        page.wait_for_timeout(400)
        # Select all + delete using real keyboard events (React listens)
        page.keyboard.press("Control+A")
        page.wait_for_timeout(150)
        page.keyboard.press("Backspace")
        page.wait_for_timeout(200)
        # Type new value via real keyboard events
        page.keyboard.type(desc, delay=20)
        page.wait_for_timeout(500)
    except Exception as e:
        log(f"  fill failed: {e}")
        return False

    # Also force-update displayName via real keyboard
    try:
        name_field = page.locator("#displayName").first
        if name_field.is_visible(timeout=1500):
            name_field.click(force=True)
            page.wait_for_timeout(300)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(disp, delay=20)
            page.wait_for_timeout(400)
    except Exception:
        pass

    page.screenshot(path=str(SHOT_DIR / f"iap_{idx+1:02d}_{pid}_e_typed.png"), full_page=False)

    # Verify the field actually shows our new text
    verified = False
    try:
        actual = desc_field.input_value(timeout=2000)
        verified = (actual.strip() == desc.strip())
        log(f"  verify field: {'✅' if verified else '❌'} actual={actual!r}")
    except Exception as e:
        log(f"  verify failed: {e}")

    if not verified:
        # Fall back: try Playwright's fill() with force=True via JS
        try:
            desc_field.evaluate("(el, v) => { el.focus(); }", desc)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.wait_for_timeout(200)
            page.keyboard.insert_text(desc)
            page.wait_for_timeout(300)
            actual = desc_field.input_value(timeout=2000)
            verified = (actual.strip() == desc.strip())
            log(f"  verify after insert_text: {'✅' if verified else '❌'} actual={actual!r}")
        except Exception as e:
            log(f"  insert_text fallback failed: {e}")

    if not verified:
        log(f"  ❌ could not set description; skipping save")
        return False

    # Click Save — force=True bypasses overlay
    saved = False
    for label in ["Save", "Save Localization", "Confirm", "Done"]:
        try:
            btn = page.get_by_role("button", name=label).first
            if btn.is_visible(timeout=1500):
                btn.click(force=True, timeout=5000)
                saved = True
                log(f"  clicked: {label}")
                page.wait_for_timeout(5000)
                break
        except Exception:
            pass

    page.screenshot(path=str(SHOT_DIR / f"iap_{idx+1:02d}_{pid}_f_after_save.png"), full_page=False)
    log(f"  {'✅' if saved else '❌'} {pid} {'SAVED' if saved else 'save FAILED'}")
    return saved


def main():
    log("starting; loading cookies")
    cookies = json.loads(pathlib.Path(COOKIES_FILE).read_text())
    pw_cookies = cookies_for_playwright(cookies)
    log(f"loaded {len(pw_cookies)} cookies")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
            viewport={"width": 1440, "height": 900},
        )
        ctx.add_cookies(pw_cookies)
        page = ctx.new_page()

        # Verify session works — try opening the IAPs index
        log("verifying session")
        page.goto(f"https://appstoreconnect.apple.com/apps/{APP_ID}/distribution/iaps",
                  wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(4000)
        page.screenshot(path=str(SHOT_DIR / "00_iaps_index.png"), full_page=False)
        log(f"URL after navigate: {page.url}")

        if "sign" in page.url.lower() or "auth" in page.url.lower():
            log("❌ session cookies didn't restore login")
            browser.close()
            return 1

        results = {}
        for idx, (pid, disp, desc, num_id) in enumerate(IAPS):
            ok = False
            try:
                ok = update_iap(page, pid, disp, desc, num_id, idx)
            except Exception as e:
                log(f"  ❌ {pid} threw: {e}")
            results[pid] = ok

        with open("/tmp/asc_iap_fix_results_v2.json", "w") as f:
            json.dump(results, f, indent=2)
        ok_n = sum(1 for v in results.values() if v)
        log(f"DONE — {ok_n}/{len(IAPS)} updated")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
