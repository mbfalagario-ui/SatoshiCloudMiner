#!/usr/bin/env python3
"""Capture fresh App Store screenshots from the running Expo web app
at 3 device sizes Apple requires for an app with supportsTablet=true:

  - 6.7"/6.9" iPhone (1290 × 2796)
  - 6.5"  iPhone (1242 × 2688)
  - 12.9" iPad   (2048 × 2732)

Screens captured per device: login, dashboard, shop, profile.
"""
from __future__ import annotations
import sys, time, pathlib
from playwright.sync_api import sync_playwright

REVIEWER_EMAIL = "appreview1@hashratecloudminer.app"
REVIEWER_PASSWORD = "AppReview2026!"

OUT = pathlib.Path("/tmp/asc_shots")
OUT.mkdir(exist_ok=True, parents=True)

DEVICES = [
    ("iphone_67", 430, 932, 3),    # 1290×2796 device pixels
    ("iphone_65", 414, 896, 3),    # 1242×2688 device pixels
    ("ipad_129", 1024, 1366, 2),   # 2048×2732 device pixels
]


def shot(page, name):
    p = str(OUT / f"{name}.png")
    page.screenshot(path=p, full_page=False)
    print(f"  📸 {p}", flush=True)


def login(page, context):
    """Bypass the form by hitting production API directly (context.request
    is server-side, no CORS), then injecting the token into localStorage.
    """
    page.goto("http://localhost:3000/sign-in", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)

    # Direct API call to production (no CORS for context.request)
    resp = context.request.post(
        "https://api.hashratecloudminer.com/api/auth/login",
        data={"email": REVIEWER_EMAIL, "password": REVIEWER_PASSWORD},
        headers={"Content-Type": "application/json"},
    )
    if not resp.ok:
        print(f"  ❌ login failed: {resp.status}")
        return
    data = resp.json()
    token = data.get("access_token") or data.get("token") or ""
    print(f"  login ok, token len={len(token)}", flush=True)

    # Inject into localStorage under all plausible keys
    page.evaluate(
        """(t) => {
            const value = JSON.stringify(t);
            try { localStorage.setItem('hc_access_token', value); } catch(e){}
            try { localStorage.setItem('@RNAsyncStorageEntry@hc_access_token', value); } catch(e){}
            try { localStorage.setItem('@async-storage-hc_access_token', value); } catch(e){}
        }""",
        token,
    )
    page.wait_for_timeout(300)
    # Navigate to home to hydrate auth context
    page.goto("http://localhost:3000/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(6000)
    print(f"  post-login url={page.url}", flush=True)


def capture_for_device(p, key, w, h, scale):
    print(f"\n=== {key}  {w}x{h}  ×{scale} ===")
    ctx = p.chromium.launch(headless=True, args=["--no-sandbox"]).new_context(
        viewport={"width": w, "height": h},
        device_scale_factor=scale,
        is_mobile=(key.startswith("iphone")),
        has_touch=True,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    )
    page = ctx.new_page()

    # 1. Landing (not logged in)
    page.goto("http://localhost:3000/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(5000)
    shot(page, f"{key}_1_landing")

    # 2. Sign in
    login(page, ctx)
    shot(page, f"{key}_2_dashboard")

    # 3. Shop
    try:
        page.goto("http://localhost:3000/shop", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(4000)
    except Exception:
        try:
            page.get_by_text("Store", exact=False).first.click(force=True)
            page.wait_for_timeout(3000)
        except Exception:
            pass
    shot(page, f"{key}_3_shop")

    # 4. Profile (must show Delete account button)
    try:
        page.goto("http://localhost:3000/profile", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(4000)
    except Exception:
        pass
    # Scroll to the Delete account button specifically — RN Web uses overflow
    # scroll on internal divs, document.body.scrollHeight doesn't work.
    try:
        page.evaluate(
            """() => {
                // Scroll every scrollable container to bottom
                document.querySelectorAll('*').forEach(el => {
                    const s = getComputedStyle(el);
                    if ((s.overflow === 'scroll' || s.overflowY === 'scroll' ||
                         s.overflow === 'auto' || s.overflowY === 'auto') &&
                        el.scrollHeight > el.clientHeight) {
                        el.scrollTop = el.scrollHeight;
                    }
                });
                // Find Delete account text & scrollIntoView
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    if ((el.textContent || '').trim() === 'Delete account') {
                        el.scrollIntoView({block: 'center'});
                        return true;
                    }
                }
                return false;
            }"""
        )
        page.wait_for_timeout(1500)
    except Exception as e:
        print(f"  scroll-to-delete failed: {e}", flush=True)
    shot(page, f"{key}_4_profile")

    ctx.close()


def main():
    with sync_playwright() as p:
        for key, w, h, scale in DEVICES:
            try:
                capture_for_device(p, key, w, h, scale)
            except Exception as e:
                print(f"  ❌ {key}: {e}")
    print()
    print("DONE — output in /tmp/asc_shots/")
    for f in sorted(OUT.iterdir()):
        print(f"  {f.stat().st_size:>9} bytes  {f.name}")


if __name__ == "__main__":
    main()
