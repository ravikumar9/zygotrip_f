"""
UI Screenshot QA Automation — captures key pages from the Next.js frontend.

Pre-requisites:
  pip install playwright
  python -m playwright install chromium

Usage:
  python tools/ui_screenshots.py              # Default: http://localhost:3000
  python tools/ui_screenshots.py --base-url http://localhost:3000
  python tools/ui_screenshots.py --login      # Also capture authenticated pages

Output:  ui_screenshots/ (project root)
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright not installed. Run: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "ui_screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Pages to capture ──────────────────────────────────────────────────────
PAGES = [
    # (name, path, viewport_width, viewport_height, wait_for_selector)
    ("home_desktop",           "/",             1440, 900,  "main"),
    ("home_mobile",            "/",             390,  844,  "main"),
    ("hotels_listing_desktop", "/hotels",       1440, 900,  "[data-testid='hotel-card'], .skeleton"),
    ("hotels_listing_mobile",  "/hotels",       390,  844,  "[data-testid='hotel-card'], .skeleton"),
    ("wallet_desktop",         "/wallet",       1440, 900,  "main"),
    ("login_page",             "/login",        1440, 900,  "form"),
]

# Pages that need authentication
AUTH_PAGES = [
    ("wallet_authenticated",   "/wallet",       1440, 900,  "main"),
    ("bookings_list",          "/my-bookings",  1440, 900,  "main"),
]


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def capture(base_url: str = "http://localhost:3000", do_login: bool = False):
    ts = timestamp()
    run_dir = OUTPUT_DIR / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Capturing screenshots -> {run_dir}")
    print(f"   Base URL: {base_url}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        captured = 0

        for name, path, width, height, wait_sel in PAGES:
            try:
                page = context.new_page()
                page.set_viewport_size({"width": width, "height": height})
                page.goto(f"{base_url}{path}", wait_until="domcontentloaded", timeout=15000)

                try:
                    page.wait_for_selector(wait_sel, timeout=8000)
                except Exception:
                    pass

                page.wait_for_timeout(1000)

                out_path = run_dir / f"{name}.png"
                page.screenshot(path=str(out_path), full_page=True)
                print(f"  OK {name} -> {out_path.name}")
                captured += 1
                page.close()
            except Exception as e:
                print(f"  FAIL {name} -- {e}")

        # Authenticated pages
        if do_login:
            print("\n  Logging in for authenticated pages...")
            try:
                auth_page = context.new_page()
                auth_page.set_viewport_size({"width": 1440, "height": 900})
                auth_page.goto(f"{base_url}/login", wait_until="domcontentloaded", timeout=15000)
                auth_page.wait_for_selector("form", timeout=5000)

                auth_page.fill('input[type="email"], input[name="email"]', "testuser@zygotrip.com")
                auth_page.fill('input[type="password"], input[name="password"]', "Test@1234")
                auth_page.click('button[type="submit"]')
                auth_page.wait_for_timeout(3000)
                auth_page.close()

                for name, path, width, height, wait_sel in AUTH_PAGES:
                    try:
                        page = context.new_page()
                        page.set_viewport_size({"width": width, "height": height})
                        page.goto(f"{base_url}{path}", wait_until="domcontentloaded", timeout=15000)
                        try:
                            page.wait_for_selector(wait_sel, timeout=8000)
                        except Exception:
                            pass
                        page.wait_for_timeout(1000)

                        out_path = run_dir / f"{name}.png"
                        page.screenshot(path=str(out_path), full_page=True)
                        print(f"  OK {name} -> {out_path.name}")
                        captured += 1
                        page.close()
                    except Exception as e:
                        print(f"  FAIL {name} -- {e}")
            except Exception as e:
                print(f"  FAIL Login -- {e}")

        browser.close()

    print(f"\nDone! {captured} screenshots saved to {run_dir}")
    return run_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UI Screenshot QA")
    parser.add_argument("--base-url", default="http://localhost:3000", help="Frontend base URL")
    parser.add_argument("--login", action="store_true", help="Also capture authenticated pages")
    args = parser.parse_args()

    capture(args.base_url, args.login)
