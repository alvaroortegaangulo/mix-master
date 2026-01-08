from playwright.sync_api import sync_playwright

def verify_pipeline_diagram():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a large viewport to trigger the 2xl breakpoint (>= 1536px)
        context = browser.new_context(viewport={"width": 1600, "height": 1080})
        page = context.new_page()

        # Navigate to the landing page
        page.goto("http://localhost:3000/es")

        # Wait for the pipeline section to load
        page.wait_for_selector("text=Pipeline de Audio")

        # Scroll to the section
        element = page.locator("text=Pipeline de Audio")
        element.scroll_into_view_if_needed()

        # Take a screenshot of the pipeline section
        # We need to capture the state where cards are collapsed
        # By default, the first card might be active.
        # We want to check the collapsed cards (indexes 1, 2, 3, 4)

        page.screenshot(path="verification/pipeline_2xl.png")

        browser.close()

if __name__ == "__main__":
    verify_pipeline_diagram()
