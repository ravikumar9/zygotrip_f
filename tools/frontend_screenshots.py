"""
Step 25 — Visual Regression Screenshots for Next.js Frontend.

Captures key pages from the production Next.js frontend (port 3000)
and saves them to ui_screenshots/ for visual QA.

Usage:
  python tools/frontend_screenshots.py

Requires:
  - Next.js dev server running on port 3000
  - Django backend running on port 8000 (for API proxy)
  - pip install playwright && python -m playwright install chromium
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page

BASE_URL = "http://127.0.0.1:3000"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "ui_screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DESKTOP_VIEWPORT = {"width": 1440, "height": 900}
MOBILE_VIEWPORT = {"width": 390, "height": 844}


def wait_for_load(page: Page, timeout: int = 8000):
    """Wait for page to settle — hydration + images."""
    page.wait_for_load_state("networkidle", timeout=timeout)
    page.wait_for_timeout(1000)  # extra settle for client-side hydration


def capture_homepage(page: Page):
    """Homepage — hero search, popular destinations, offers."""
    print("  [1/8] Homepage (desktop)...")
    page.goto(BASE_URL, wait_until="domcontentloaded")
    wait_for_load(page)
    page.screenshot(path=str(OUTPUT_DIR / "homepage.png"), full_page=True)


def capture_search_results(page: Page):
    """Hotel listing/search results page."""
    print("  [2/8] Search results (desktop)...")
    page.goto(f"{BASE_URL}/hotels?location=Goa", wait_until="domcontentloaded")
    wait_for_load(page)
    page.screenshot(path=str(OUTPUT_DIR / "search_results.png"), full_page=True)


def capture_hotel_detail(page: Page) -> str | None:
    """Hotel detail page — first hotel from listings."""
    print("  [3/8] Hotel detail page (desktop)...")
    # Navigate to listings first to find a valid hotel slug
    page.goto(f"{BASE_URL}/hotels", wait_until="domcontentloaded")
    wait_for_load(page)

    # Try to find a hotel card link
    hotel_link = page.locator('a[href*="/hotels/"]').first
    if hotel_link.count() > 0:
        href = hotel_link.get_attribute("href")
        if href and "/hotels/" in href:
            slug = href.split("/hotels/")[-1].rstrip("/")
            detail_url = f"{BASE_URL}/hotels/{slug}"
            page.goto(detail_url, wait_until="domcontentloaded")
            wait_for_load(page)
            page.screenshot(
                path=str(OUTPUT_DIR / "hotel_page.png"), full_page=True
            )
            return slug

    # Fallback: just screenshot whatever is on /hotels
    page.screenshot(path=str(OUTPUT_DIR / "hotel_page.png"), full_page=True)
    return None


def capture_booking_page(page: Page):
    """Booking page — screenshot the /booking route."""
    print("  [4/8] Booking page (desktop)...")
    page.goto(f"{BASE_URL}/booking", wait_until="domcontentloaded")
    wait_for_load(page)
    page.screenshot(path=str(OUTPUT_DIR / "booking_page.png"), full_page=True)


def capture_wallet(page: Page):
    """Wallet page."""
    print("  [5/8] Wallet page (desktop)...")
    page.goto(f"{BASE_URL}/wallet", wait_until="domcontentloaded")
    wait_for_load(page)
    page.screenshot(path=str(OUTPUT_DIR / "wallet_page.png"), full_page=True)


def capture_mobile_homepage(page: Page):
    """Mobile viewport — homepage."""
    print("  [6/8] Homepage (mobile)...")
    page.goto(BASE_URL, wait_until="domcontentloaded")
    wait_for_load(page)
    page.screenshot(path=str(OUTPUT_DIR / "mobile_homepage.png"), full_page=True)


def capture_mobile_search(page: Page):
    """Mobile viewport — search results."""
    print("  [7/8] Search results (mobile)...")
    page.goto(f"{BASE_URL}/hotels", wait_until="domcontentloaded")
    wait_for_load(page)
    page.screenshot(
        path=str(OUTPUT_DIR / "mobile_search_results.png"), full_page=True
    )


def capture_city_landing(page: Page):
    """SEO city landing page — /hotels/in/goa."""
    print("  [8/8] City landing page (desktop)...")
    page.goto(f"{BASE_URL}/hotels/in/goa", wait_until="domcontentloaded")
    wait_for_load(page)
    page.screenshot(
        path=str(OUTPUT_DIR / "city_landing_goa.png"), full_page=True
    )


def main():
    print(f"Capturing screenshots to {OUTPUT_DIR}/\n")

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # --- Desktop captures ---
        desktop = browser.new_page(viewport=DESKTOP_VIEWPORT)
        capture_homepage(desktop)
        capture_search_results(desktop)
        capture_hotel_detail(desktop)
        capture_booking_page(desktop)
        capture_wallet(desktop)
        capture_city_landing(desktop)
        desktop.close()

        # --- Mobile captures ---
        mobile = browser.new_page(viewport=MOBILE_VIEWPORT)
        capture_mobile_homepage(mobile)
        capture_mobile_search(mobile)
        mobile.close()

        browser.close()

    print(f"\nDone! {len(list(OUTPUT_DIR.glob('*.png')))} screenshots saved to {OUTPUT_DIR}/")
    for f in sorted(OUTPUT_DIR.glob("*.png")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name:40s} {size_kb:>8.1f} KB")


if __name__ == "__main__":
    main()
