from playwright.sync_api import sync_playwright

def verify_pipeline_background():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a larger viewport to see the background clearly
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        # We need to serve the frontend. Assuming it is running on localhost:3000
        # If not, we might need to start it or build it.
        # For now, let us try to access the homepage where BenefitsSection is likely used
        try:
            page.goto("http://localhost:3000")

            # Wait for the section to be visible.
            # The BenefitsSection has id="benefits"
            benefits_section = page.locator("#benefits")
            benefits_section.scroll_into_view_if_needed()

            # Give it a moment for animations to start/render
            page.wait_for_timeout(2000)

            # Take a screenshot of the Benefits Section
            benefits_section.screenshot(path="verification/benefits_section.png")
            print("Screenshot taken at verification/benefits_section.png")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    verify_pipeline_background()
