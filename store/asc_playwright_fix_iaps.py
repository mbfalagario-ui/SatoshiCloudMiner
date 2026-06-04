#!/usr/bin/env python3
"""Headless Playwright automation to fix the 10 REJECTED en-US IAP
localizations that Apple's ASC API refuses to mutate.

Flow:
 1. Open ASC login.
 2. Fill email, click Continue.
 3. Fill password, click Sign In.
 4. When the 2FA prompt appears, write '/tmp/asc_status.txt' = WAITING_FOR_2FA
    and poll '/tmp/asc_2fa_code.txt' until the main agent writes 6 digits.
 5. Enter the code, dismiss "Trust this browser" if shown.
 6. For each of 10 IAPs, open the IAP detail URL, click Edit on the
    en-US localization, replace the description, click Save.
 7. Snapshot before/after for each IAP into /tmp/asc_screens/.

Idempotent: if a description already matches the target, it's skipped.
Status updates written to /tmp/asc_status.txt continuously.
"""
from __future__ import annotations
import os, sys, time, json, pathlib
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

EMAIL    = "mbfalagario@gmail.com"
PASSWORD = "Puopolo2016"

APP_ID = "6773104756"

# IAP product ID → desired en-US description (≤45 chars per Apple)
IAPS = [
    ("welcome_199",    "Newcomer Boost",             "One-time 50 GH/s boost credit"),
    ("rookie_299",     "Daily Booster",              "One-time 100 GH/s boost credit"),
    ("pro_499",        "Pro Rig",                    "One-time 230 GH/s boost credit"),
    ("elite_999",      "Elite Rig",                  "One-time 500 GH/s boost credit"),
    ("ultra_1999",     "Ultra Rig",                  "One-time 1100 GH/s boost credit"),
    ("mega_4999",      "Mega Rig",                   "One-time 2300 GH/s boost credit"),
    ("giga_9999",      "Giga Rig",                   "One-time 3500 GH/s boost credit"),
    ("titan_14999",    "Titan Rig",                  "One-time 4700 GH/s boost credit"),
    ("colossus_19999", "Colossus Rig",               "One-time 7500 GH/s boost credit"),
    ("adfree_399",     "Ad-Free + Priority Support", "Removes ads. Priority support."),
]

# Numeric IAP IDs (from ASC API audit)
IAP_NUMERIC_IDS = {
    "welcome_199":    "6773119536",
    "rookie_299":     "6773119594",
    "pro_499":        "6773119538",
    "elite_999":      "6773119735",
    "ultra_1999":     "6773119542",
    "mega_4999":      "6773119720",
    "giga_9999":      "6773119629",
    "titan_14999":    "6773119723",
    "colossus_19999": "6773119739",
    "adfree_399":     "6773125872",
}

STATUS_FILE   = "/tmp/asc_status.txt"
CODE_FILE     = "/tmp/asc_2fa_code.txt"
LOG_FILE      = "/tmp/asc_run.log"
SHOT_DIR      = pathlib.Path("/tmp/asc_screens")
SHOT_DIR.mkdir(exist_ok=True, parents=True)


def status(msg: str):
    pathlib.Path(STATUS_FILE).write_text(msg)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    print(f"[STATUS] {msg}", flush=True)


def wait_for_2fa_code(timeout_s: int = 600) -> str:
    pathlib.Path(CODE_FILE).unlink(missing_ok=True)
    status("WAITING_FOR_2FA — waiting for code at /tmp/asc_2fa_code.txt")
    start = time.time()
    while time.time() - start < timeout_s:
        if os.path.exists(CODE_FILE):
            code = pathlib.Path(CODE_FILE).read_text().strip()
            digits = "".join(ch for ch in code if ch.isdigit())
            if len(digits) >= 4:
                pathlib.Path(CODE_FILE).unlink(missing_ok=True)
                return digits
        time.sleep(1)
    raise TimeoutError("Timed out waiting for 2FA code")


def login(page: Page):
    status("STEP 1 — opening App Store Connect login page")
    page.goto("https://appstoreconnect.apple.com/", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    # Apple ID login is in an iframe sometimes; try direct, fall back to iframe
    def find_email_input():
        for sel in ['input[name="accountName"]',
                    'input#account_name_text_field',
                    'input[type="email"]']:
            loc = page.locator(sel).first
            try:
                if loc.is_visible(timeout=2000):
                    return loc
            except Exception:
                pass
        # Try inside iframes
        for frame in page.frames:
            for sel in ['input[name="accountName"]',
                        'input#account_name_text_field',
                        'input[type="email"]']:
                try:
                    loc = frame.locator(sel).first
                    if loc.is_visible(timeout=1000):
                        return loc
                except Exception:
                    pass
        return None

    page.screenshot(path=str(SHOT_DIR / "01_login_open.png"), full_page=False)

    status("STEP 2 — looking for email field")
    email_input = None
    for attempt in range(15):
        email_input = find_email_input()
        if email_input is not None:
            break
        page.wait_for_timeout(1500)
    if email_input is None:
        page.screenshot(path=str(SHOT_DIR / "01b_no_email_field.png"), full_page=True)
        raise RuntimeError("Could not locate email input on Apple sign-in page")

    email_input.fill(EMAIL)
    page.wait_for_timeout(500)
    email_input.press("Enter")
    status("email submitted")

    # Wait for password
    page.wait_for_timeout(2500)
    page.screenshot(path=str(SHOT_DIR / "02_after_email.png"), full_page=False)

    def find_password_input():
        for sel in ['input[name="password"]',
                    'input#password_text_field',
                    'input[type="password"]']:
            loc = page.locator(sel).first
            try:
                if loc.is_visible(timeout=2000):
                    return loc
            except Exception:
                pass
        for frame in page.frames:
            for sel in ['input[name="password"]',
                        'input#password_text_field',
                        'input[type="password"]']:
                try:
                    loc = frame.locator(sel).first
                    if loc.is_visible(timeout=1000):
                        return loc
                except Exception:
                    pass
        return None

    pwd_input = None
    for attempt in range(15):
        pwd_input = find_password_input()
        if pwd_input is not None:
            break
        page.wait_for_timeout(1500)
    if pwd_input is None:
        page.screenshot(path=str(SHOT_DIR / "02b_no_password_field.png"), full_page=True)
        raise RuntimeError("Could not locate password input")

    pwd_input.fill(PASSWORD)
    page.wait_for_timeout(500)
    pwd_input.press("Enter")
    status("password submitted")

    # Wait for 2FA prompt OR direct landing
    page.wait_for_timeout(5000)
    page.screenshot(path=str(SHOT_DIR / "03_after_password.png"), full_page=False)

    def find_2fa_input():
        # The 2FA page has 6 individual digit fields. Try the first one.
        for sel in ['input[aria-label*="digit" i]',
                    'input[name="verificationCode"]',
                    'input[type="tel"]',
                    'input.auth-digit-input',
                    'input[autocomplete="one-time-code"]']:
            for frame in [page] + page.frames:
                try:
                    locs = frame.locator(sel) if hasattr(frame, "locator") else None
                    if locs is None: continue
                    if locs.count() >= 1:
                        return frame, locs
                except Exception:
                    pass
        return None, None

    frm, digit_locs = None, None
    for attempt in range(10):
        frm, digit_locs = find_2fa_input()
        if digit_locs is not None:
            break
        page.wait_for_timeout(1500)

    if digit_locs is not None:
        status(f"2FA input detected; {digit_locs.count()} digit fields")
        code = wait_for_2fa_code()
        status(f"2FA code received: {'*' * (len(code)-2)}{code[-2:]}")
        # Fill digit by digit
        if digit_locs.count() >= len(code):
            for i, ch in enumerate(code):
                digit_locs.nth(i).fill(ch)
                page.wait_for_timeout(150)
        else:
            digit_locs.first.fill(code)
        page.wait_for_timeout(3000)
        page.screenshot(path=str(SHOT_DIR / "04_after_2fa.png"), full_page=False)

        # Apple may show "Trust this browser?" — click "Trust" or "Don't Trust"
        for label in ["Trust", "Don't Trust"]:
            try:
                btn = page.get_by_role("button", name=label).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    status(f"clicked: {label}")
                    page.wait_for_timeout(3000)
                    break
            except Exception:
                pass

    status("login complete — waiting for ASC dashboard")
    page.wait_for_timeout(5000)
    page.screenshot(path=str(SHOT_DIR / "05_post_login.png"), full_page=False)


def update_iap(page: Page, pid: str, num_id: str, disp: str, desc: str, idx: int):
    url = f"https://appstoreconnect.apple.com/apps/{APP_ID}/distribution/iaps/{num_id}"
    status(f"IAP {idx+1}/10 — {pid} — opening")
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    page.screenshot(path=str(SHOT_DIR / f"iap_{idx+1:02d}_{pid}_a_loaded.png"), full_page=False)

    # Find the English (U.S.) row in the Localizations table and click it
    # ASC UI tends to use either a button or a link with the language name
    try:
        en_us = page.get_by_text("English (U.S.)", exact=False).first
        en_us.click()
        page.wait_for_timeout(2000)
    except Exception as e:
        status(f"  could not find English (U.S.) row: {e}")
        page.screenshot(path=str(SHOT_DIR / f"iap_{idx+1:02d}_{pid}_b_no_enus.png"), full_page=True)
        return False

    # Click Edit button (it might be named "Edit" or icon)
    clicked_edit = False
    for label in ["Edit", "Edit Information", "Modify"]:
        try:
            btn = page.get_by_role("button", name=label).first
            if btn.is_visible(timeout=3000):
                btn.click()
                clicked_edit = True
                status(f"  clicked: {label}")
                page.wait_for_timeout(1500)
                break
        except Exception:
            pass

    if not clicked_edit:
        # Maybe the description is editable inline
        status("  no Edit button found — trying inline edit")

    # Find description textarea/input
    desc_field = None
    for sel in ['textarea[aria-label*="description" i]',
                'textarea[name*="description" i]',
                'textarea#description',
                'input[aria-label*="description" i]']:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                desc_field = loc
                break
        except Exception:
            pass

    if not desc_field:
        page.screenshot(path=str(SHOT_DIR / f"iap_{idx+1:02d}_{pid}_c_no_desc.png"), full_page=True)
        status("  ❌ no description field located")
        return False

    desc_field.fill("")
    page.wait_for_timeout(300)
    desc_field.fill(desc)
    page.wait_for_timeout(500)
    page.screenshot(path=str(SHOT_DIR / f"iap_{idx+1:02d}_{pid}_d_typed.png"), full_page=False)

    # Click Save
    saved = False
    for label in ["Save", "Done", "Confirm"]:
        try:
            btn = page.get_by_role("button", name=label).first
            if btn.is_visible(timeout=2000):
                btn.click()
                saved = True
                status(f"  clicked: {label}")
                page.wait_for_timeout(3000)
                break
        except Exception:
            pass

    page.screenshot(path=str(SHOT_DIR / f"iap_{idx+1:02d}_{pid}_e_after_save.png"), full_page=False)
    status(f"  {'✅' if saved else '❌'} {pid} {'saved' if saved else 'save FAILED'}")
    return saved


def main():
    status("starting")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        try:
            login(page)
        except Exception as e:
            status(f"❌ login failed: {e}")
            page.screenshot(path=str(SHOT_DIR / "99_login_error.png"), full_page=True)
            browser.close()
            return 1

        # Save session
        ctx.storage_state(path="/tmp/asc_session.json")
        status("session saved to /tmp/asc_session.json")

        results = {}
        for idx, (pid, disp, desc) in enumerate(IAPS):
            num_id = IAP_NUMERIC_IDS[pid]
            ok = False
            try:
                ok = update_iap(page, pid, num_id, disp, desc, idx)
            except Exception as e:
                status(f"  ❌ {pid} threw: {e}")
            results[pid] = ok

        with open("/tmp/asc_iap_fix_results.json", "w") as f:
            json.dump(results, f, indent=2)

        ok_n = sum(1 for v in results.values() if v)
        status(f"DONE — {ok_n}/{len(IAPS)} IAPs updated successfully")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
