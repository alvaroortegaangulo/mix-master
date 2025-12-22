from playwright.sync_api import sync_playwright, expect

def verify_hero_bg():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Navigate to the home page
            print("Navigating to home page...")
            page.goto("http://localhost:3000")

            # Wait for the hero section to be visible
            print("Waiting for hero section...")
            # The hero section contains text "Studio Sound"
            expect(page.get_by_text("Studio Sound")).to_be_visible(timeout=30000)

            # Check if the background image is present in the DOM
            # It should be an img with src containing "background_hero.webp"
            # Note: next/image might rewrite the src, but it usually contains the original filename in the query or path
            print("Checking for background image...")
            bg_image = page.locator('img[alt="Hero Background"]')
            expect(bg_image).to_be_visible()

            # Check opacity class
            # We used opacity-20. Playwright can check class or computed style.
            # Checking class is easier if we trust tailwind
            print("Checking opacity...")
            expect(bg_image).to_have_class(re.compile(r"opacity-20"))

            # Take a screenshot of the hero section
            print("Taking screenshot...")
            # We can screenshot the whole viewport which should show the hero
            page.screenshot(path="verification/hero_bg.png")
            print("Screenshot saved to verification/hero_bg.png")

        except Exception as e:
            print(f"Verification failed: {e}")
            page.screenshot(path="verification/error.png")
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    import re
    verify_hero_bg()
