import asyncio
import os
import subprocess
import time
from playwright.async_api import async_playwright

async def capture():
    os.makedirs("screenshots", exist_ok=True)

    # Start simple http server
    server = subprocess.Popen(
        ["python", "-m", "http.server", "8765", "--directory", "docs"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(1.5)

    base_url = "http://localhost:8765/index.html"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        viewports = [
            ("360", 360, 800),
            ("768", 768, 1024),
            ("1024", 1024, 768),
            ("1440", 1440, 900),
            ("1920", 1920, 1080),
        ]

        # 1. Capture Feed across all required widths
        for name, w, h in viewports:
            page = await browser.new_page(viewport={"width": w, "height": h})
            await page.goto(base_url, wait_until="networkidle")
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"screenshots/screen_feed_{name}.png", full_page=False)
            print(f"Captured screen_feed_{name}.png")
            await page.close()

        # 2. Capture other tabs at 1440x900 desktop resolution
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(base_url, wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # Deals tab
        await page.click('button[data-tab="tab-deals"]')
        await page.wait_for_timeout(500)
        await page.screenshot(path="screenshots/screen_deals_1440.png")
        print("Captured screen_deals_1440.png")

        # Market tab
        await page.click('button[data-tab="tab-market"]')
        await page.wait_for_timeout(500)
        await page.screenshot(path="screenshots/screen_market_1440.png")
        print("Captured screen_market_1440.png")

        # Items Catalog tab
        await page.click('button[data-tab="tab-items"]')
        await page.wait_for_timeout(500)
        await page.screenshot(path="screenshots/screen_items_1440.png")
        print("Captured screen_items_1440.png")

        # Journal & Accuracy tab
        await page.click('button[data-tab="tab-journal"]')
        await page.wait_for_timeout(500)
        await page.screenshot(path="screenshots/screen_journal_1440.png")
        print("Captured screen_journal_1440.png")

        # Positions tab
        await page.click('button[data-tab="tab-positions"]')
        await page.wait_for_timeout(500)
        await page.screenshot(path="screenshots/screen_positions_1440.png")
        print("Captured screen_positions_1440.png")

        # Deep-dive Modal
        await page.click('button[data-tab="tab-items"]')
        await page.wait_for_timeout(300)
        first_analyze_btn = page.locator('button:has-text("🔍 Анализ")').first
        if await first_analyze_btn.is_visible():
            await first_analyze_btn.click()
            await page.wait_for_timeout(800)
            await page.screenshot(path="screenshots/screen_deepdive_modal_1440.png")
            print("Captured screen_deepdive_modal_1440.png")

        await browser.close()

    server.terminate()
    print("All screenshots successfully captured!")

if __name__ == "__main__":
    asyncio.run(capture())
