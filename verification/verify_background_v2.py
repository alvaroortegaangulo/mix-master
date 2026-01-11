from playwright.sync_api import sync_playwright

def verify_pipeline_background():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        try:
            page.goto("http://localhost:3000/en", timeout=60000)

            # Wait for content to load
            page.wait_for_load_state("networkidle")

            # Try to find any section first to debug
            print("Page title:", page.title())

            # The BenefitsSection has id="benefits"
            benefits_section = page.locator("#benefits")

            if benefits_section.count() > 0:
                benefits_section.scroll_into_view_if_needed()
                page.wait_for_timeout(2000)
                benefits_section.screenshot(path="verification/benefits_section.png")
                print("Screenshot taken at verification/benefits_section.png")
            else:
                print("Benefits section not found. Taking full page screenshot.")
                page.screenshot(path="verification/full_page_debug.png", full_page=True)

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification/error_debug.png", full_page=True)
        finally:
            browser.close()

if __name__ == "__main__":
    verify_pipeline_background()
