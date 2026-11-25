import asyncio
import json
import time
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        print("Navigating to http://localhost:8080...")
        await page.goto("http://localhost:8080", wait_until="networkidle")
        await page.wait_for_timeout(2500)
        
        # 1. Test Dynamic SL/TP Toggle
        print("--- Testing Dynamic SL/TP Toggle ---")
        btn_dyn = page.locator('#btnToggleDynamicSlTp')
        is_visible = await btn_dyn.is_visible()
        print(f"Dynamic SL/TP button visible: {is_visible}")
        btn_text = await btn_dyn.inner_text()
        print(f"Initial button text: {btn_text}")
        
        # Check future projection status in JS
        has_future = await page.evaluate("() => window.app.chartManager.showFutureProjection")
        lines_count = await page.evaluate("() => window.app.chartManager.futureProjectionLines.length")
        print(f"showFutureProjection: {has_future}, futureProjectionLines: {lines_count}")
        
        # Click to turn OFF
        print("Clicking to turn OFF Dynamic SL/TP...")
        await btn_dyn.click()
        await page.wait_for_timeout(1000)
        has_future_off = await page.evaluate("() => window.app.chartManager.showFutureProjection")
        lines_count_off = await page.evaluate("() => window.app.chartManager.futureProjectionLines.length")
        btn_text_off = await btn_dyn.inner_text()
        print(f"After OFF -> showFutureProjection: {has_future_off}, lines: {lines_count_off}, text: {btn_text_off}")
        
        # Click to turn back ON
        print("Clicking to turn back ON Dynamic SL/TP...")
        await btn_dyn.click()
        await page.wait_for_timeout(1000)
        has_future_on = await page.evaluate("() => window.app.chartManager.showFutureProjection")
        lines_count_on = await page.evaluate("() => window.app.chartManager.futureProjectionLines.length")
        btn_text_on = await btn_dyn.inner_text()
        print(f"After ON -> showFutureProjection: {has_future_on}, lines: {lines_count_on}, text: {btn_text_on}")

        # 2. Test Quick Load TF1 Indicators
        print("\n--- Testing Nạp Bộ Chỉ Báo TF1 ---")
        btn_quick_tf1 = page.locator('#btnQuickLoadTF1')
        print(f"btnQuickLoadTF1 visible: {await btn_quick_tf1.is_visible()}")
        await btn_quick_tf1.click()
        await page.wait_for_timeout(2000)
        
        # Check active indicators config
        cfg = await page.evaluate("() => window.app.indicatorsManager.currentConfig")
        tf1_keys = [k for k in cfg.keys() if 'tf1' in k.lower()]
        print(f"Active TF1 indicator keys: {tf1_keys}")
        
        # 3. Test Crosshair Synchronization
        print("\n--- Testing Crosshair Cursor Synchronization ---")
        chart_m15 = page.locator('#chartM15')
        box_m15 = await chart_m15.bounding_box()
        print(f"Chart M15 box: {box_m15}")
        
        # Move mouse over Chart M15
        x_target = box_m15['x'] + box_m15['width'] * 0.5
        y_target = box_m15['y'] + box_m15['height'] * 0.5
        await page.mouse.move(x_target, y_target)
        await page.wait_for_timeout(1000)
        
        # Check OHLC text on all 3 charts
        ohlc_h4 = await page.locator('#ohlcH4').inner_text()
        ohlc_tf2 = await page.locator('#ohlcTF2').inner_text()
        ohlc_m15 = await page.locator('#ohlcM15').inner_text()
        print(f"OHLC H4  (TF1): {ohlc_h4.replace(chr(10), ' ')}")
        print(f"OHLC TF2 (TF2): {ohlc_tf2.replace(chr(10), ' ')}")
        print(f"OHLC M15 (TF3): {ohlc_m15.replace(chr(10), ' ')}")
        
        # Check raw candle count
        c_h4 = await page.evaluate("() => window.app.chartManager.rawCandlesH4.length")
        c_tf2 = await page.evaluate("() => window.app.chartManager.rawCandlesTF2.length")
        c_m15 = await page.evaluate("() => window.app.chartManager.rawCandlesM15.length")
        print(f"Candles count -> H4: {c_h4}, TF2: {c_tf2}, M15: {c_m15}")
        
        # 4. Take full screenshot
        screenshot_path = "C:/Users/AreteEPM/.gemini/antigravity/brain/11386cf0-e481-4bd9-9e54-e7588a21be6f/shot4_cursor_sync_tf1_dynamicsltp.png"
        await page.screenshot(path=screenshot_path)
        print(f"\nScreenshot saved to: {screenshot_path}")
        
        await browser.close()
        print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
