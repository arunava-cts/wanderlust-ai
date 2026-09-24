import asyncio
import os
import shutil
from playwright.async_api import async_playwright

ARTIFACTS_DIR = "/config/.gemini/antigravity/brain/daa47f0b-3f65-42a3-b5ee-5d8fd1c27f4e"
TEMP_VIDEO_DIR = "/tmp/playwright_videos"

async def record_demo():
    if os.path.exists(TEMP_VIDEO_DIR):
        shutil.rmtree(TEMP_VIDEO_DIR)
    os.makedirs(TEMP_VIDEO_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=TEMP_VIDEO_DIR,
            record_video_size={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        print("Navigating to local frontend http://localhost:8080...")
        await page.goto("http://localhost:8080")
        await page.wait_for_selector("#input")
        await asyncio.sleep(2)

        # Prompt 1: Core capability - Search destinations & Weather
        prompt1 = "Search destinations in Kyoto and check current weather"
        print(f"Sending Prompt 1: {prompt1}")
        await page.fill("#input", prompt1)
        await asyncio.sleep(1)
        await page.click("button[type='submit']")

        # Wait for agent response to appear
        print("Waiting for response to Prompt 1...")
        await page.wait_for_selector(".msg.agent", timeout=45000)
        await asyncio.sleep(6)

        # Prompt 2: Rich prompt with tool calls, budget calculation & artwork generation
        prompt2 = "Calculate a 3-day budget for 2 travelers visiting dest-001 and generate watercolor artwork of Arashiyama Bamboo Grove at sunrise"
        print(f"Sending Prompt 2: {prompt2}")
        await page.fill("#input", prompt2)
        await asyncio.sleep(1)
        await page.click("button[type='submit']")

        # Wait for agent response to appear and finish loading
        print("Waiting for response to Prompt 2...")
        # Wait until there are at least 2 agent messages
        await page.wait_for_function("document.querySelectorAll('.msg.agent').length >= 2", timeout=60000)
        await asyncio.sleep(10)

        # Scroll to bottom to ensure full content is visible in video
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(3)

        print("Closing context to save video...")
        await context.close()
        await browser.close()

    # Find the recorded video file
    video_files = [os.path.join(TEMP_VIDEO_DIR, f) for f in os.listdir(TEMP_VIDEO_DIR) if f.endswith(".webm") or f.endswith(".mp4")]
    if video_files:
        src_video = video_files[0]
        dest_video = os.path.join(ARTIFACTS_DIR, "demo_video.webm")
        shutil.copy(src_video, dest_video)
        print(f"Successfully recorded demo video: {dest_video}")
    else:
        print("No video file was found in temp dir.")

if __name__ == "__main__":
    asyncio.run(record_demo())
