from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "ui_screens"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch()

        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(f"{BASE_URL}/hotels/", wait_until="networkidle")
        page.locator(".hero").screenshot(path=str(OUTPUT_DIR / "hero_section.png"))

        search_input = page.locator('[data-autocomplete="search"]').first
        search_input.fill("Co")
        page.wait_for_selector(".search-suggestions:not([hidden])", timeout=5000)
        page.locator(".search-suggestions").screenshot(path=str(OUTPUT_DIR / "autocomplete.png"))

        page.locator(".sidebar-layout").screenshot(path=str(OUTPUT_DIR / "results_layout.png"))

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto(f"{BASE_URL}/hotels/", wait_until="networkidle")
        mobile.screenshot(path=str(OUTPUT_DIR / "mobile_hotels.png"), full_page=True)

        browser.close()


if __name__ == "__main__":
    capture()
