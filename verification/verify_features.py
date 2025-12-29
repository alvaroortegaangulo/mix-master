from playwright.sync_api import sync_playwright, Page, expect

def run(playwright):
    browser = playwright.chromium.launch()
    page = browser.new_page()

    # 1. Navigate to the features section
    try:
        # Navigate to the Spanish locale as per user request context ("De tu DAW al Mundo")
        page.goto("http://localhost:3000/es", timeout=60000)

        # Wait for hydration
        page.wait_for_selector("#features", timeout=15000)

        # Scroll to the section
        features_section = page.locator("#features")
        features_section.scroll_into_view_if_needed()

        # Wait for animations to settle (Glassmorphism card, etc.)
        page.wait_for_timeout(2000)

        # 2. Verify content presence (using existing translations)
        # "De tu DAW al Mundo" should be present (via t.rich("title"))
        expect(features_section).to_contain_text("De tu DAW al")

        # Verify the icons are rendered (checking for svg presence in the nav buttons)
        # There should be 4 buttons
        buttons = features_section.locator("button")
        expect(buttons).to_have_count(4)

        # 3. Take Screenshot
        page.screenshot(path="verification/features_section.png", full_page=True)

        # Also take a specific screenshot of the features component
        features_section.screenshot(path="verification/features_component.png")

        print("Verification complete. Screenshots saved.")

    except Exception as e:
        print(f"Verification failed: {e}")
        page.screenshot(path="verification/error.png")
        raise e
    finally:
        browser.close()

with sync_playwright() as playwright:
    run(playwright)
