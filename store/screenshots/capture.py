#!/usr/bin/env python3
"""
Generate App Store Connect–compliant screenshots for HashCloud.

Required Apple sizes (portrait):
  - 6.7" / 6.9" iPhone : 1290 x 2796   (iPhone 15/16 Pro Max)
  - 6.5"      iPhone   : 1242 x 2688   (iPhone 11 Pro Max — still accepted)
  - 5.5"      iPhone   : 1242 x 2208   (iPhone 8 Plus)

Usage:
  pip install playwright
  python -m playwright install chromium
  python store/screenshots/capture.py \
      --base http://localhost:3000 \
      --email demo@hashcloud.app --password password123

Outputs go to /app/store/screenshots/{6.7,6.5,5.5}/.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Install Playwright first: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

OUT_DIR = Path("/app/store/screenshots")

DEVICES = {
    "6.7": {"w": 1290, "h": 2796},  # iPhone 15/16 Pro Max
    "6.5": {"w": 1242, "h": 2688},  # iPhone 11 Pro Max
    "5.5": {"w": 1242, "h": 2208},  # iPhone 8 Plus
}

# (route, filename-suffix)
PAGES = [
    ("/",       "1-dashboard"),
    ("/shop",   "2-shop"),
    ("/wallet", "3-wallet"),
    ("/profile", "4-profile"),
]


async def login(page, base, email, password):
    """Authenticate via the API directly, persist token to storage, then
    reload the app — avoids any UI flakiness with form validation/alerts."""
    # The API is behind a different origin (configured via EXPO_PUBLIC_BACKEND_URL).
    api_base = os.environ.get("EXPO_PUBLIC_BACKEND_URL", base).rstrip("/")
    # Visit root first so AsyncStorage's IndexedDB is bound to this origin.
    await page.goto(base, wait_until="domcontentloaded")
    auth_payload = {"email": email, "password": password, "api_base": api_base}
    js = """
    async ({email, password, api_base}) => {
      const post = (path, body) => fetch(api_base + '/api' + path, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(body),
      }).then(async r => ({ok:r.ok, status:r.status, data: await r.json().catch(()=>({}))}));

      // Try register, fall back to login.
      let r = await post('/auth/register', {email, password});
      if (!r.ok) r = await post('/auth/login', {email, password});
      if (!r.ok) return {ok:false, status:r.status, data:r.data};
      const token = r.data.access_token;

      // Persist the JWT exactly where the @react-native-async-storage web
      // adapter looks for it: window.localStorage. Values are JSON-encoded.
      window.localStorage.setItem('hc_access_token', JSON.stringify(token));
      return {ok:true};
    }
    """
    try:
        res = await page.evaluate(js, auth_payload)
        if not res or not res.get("ok"):
            print("  API auth failed:", res)
            return False
    except Exception as e:
        print("  Login failed:", e)
        return False
    # Reload so the session provider picks up the persisted token, then
    # wait until the tabs layout is mounted (tab bar links exist in DOM).
    await page.goto(f"{base}/", wait_until="networkidle")
    try:
        await page.wait_for_function(
            "() => !!document.querySelector('a[href$=\"/shop\"], a[href$=\"/wallet\"]')",
            timeout=15000,
        )
    except Exception:
        # If tab bar never appears, the redirect from / → /(tabs) didn't fire.
        # Tap the "Get Started" CTA on the onboarding screen to push to sign-up
        # — but only as a last resort.
        print("  Tab bar didn't render after auth; aborting.")
        return False
    await page.wait_for_timeout(1500)
    return True


async def capture_device(p, base, device_name, dims, email, password):
    out = OUT_DIR / device_name
    out.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {device_name}″ ({dims['w']}x{dims['h']}) ===")

    browser = await p.chromium.launch(headless=True, args=["--hide-scrollbars"])
    context = await browser.new_context(
        viewport={"width": dims["w"] // 3, "height": dims["h"] // 3},
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
        color_scheme="dark",
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        ),
    )
    page = await context.new_page()

    if not await login(page, base, email, password):
        print("  Could not authenticate — skipping device.")
        await browser.close()
        return

    # Capture dashboard first (we already landed on / after auth).
    await page.wait_for_timeout(1200)
    target = out / f"{device_name}-1-dashboard.png"
    await page.screenshot(path=str(target), full_page=False)
    print("  ✓", target)

    # Navigate via tab bar clicks (direct URL routing hits an existing
    # @react-navigation infinite-loop bug on the web build, so we go in-app).
    tab_routes = [
        ("hardware-chip", "/shop", "2-shop"),
        ("wallet", "/wallet", "3-wallet"),
        ("person-circle", "/profile", "4-profile"),
    ]
    for icon, route, suffix in tab_routes:
        try:
            # Tab buttons render as <a href="/shop"> elements on react-native-web.
            link = page.locator(f'a[href$="{route}"]').first
            await link.scroll_into_view_if_needed(timeout=2000)
            await link.click(timeout=5000)
            await page.wait_for_timeout(1500)
        except Exception as e:
            print(f"  tab click {route} failed: {e}")
            continue
        target = out / f"{device_name}-{suffix}.png"
        await page.screenshot(path=str(target), full_page=False)
        print("  ✓", target)

    await browser.close()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("EXPO_PUBLIC_BASE_URL", "http://localhost:3000"))
    ap.add_argument("--email", default=f"shots+{int(time.time())}@hashcloud.app")
    ap.add_argument("--password", default="password123")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Base URL:", args.base)
    print("Output  :", OUT_DIR)

    async with async_playwright() as p:
        for name, dims in DEVICES.items():
            await capture_device(p, args.base, name, dims, args.email, args.password)

    print("\nDone. Upload PNGs from", OUT_DIR, "to App Store Connect → App Previews and Screenshots.")


if __name__ == "__main__":
    asyncio.run(main())
