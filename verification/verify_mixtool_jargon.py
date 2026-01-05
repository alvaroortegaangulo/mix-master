from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a mobile-ish viewport to ensure layout is compact or desktop to see full list
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # Navigate to the mix page
        # We need to bypass the upload step.
        # Since I modified MixTool.tsx to force state (I will do that next), I can just visit the page.
        page.goto("http://localhost:3000/es/mix")

        # Wait for the text "Limpieza" to appear, indicating the pipeline is visible
        try:
            page.wait_for_selector("text=Limpieza", timeout=10000)
            print("Found 'Limpieza'")
        except:
            print("Did not find 'Limpieza' immediately. Checking if upload step is forced.")

        # Take a screenshot
        page.screenshot(path="verification/mixtool_jargon.png", full_page=True)

        browser.close()

if __name__ == "__main__":
    run()
