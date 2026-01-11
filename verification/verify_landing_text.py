
from playwright.sync_api import sync_playwright

def verify_landing_text():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Grant permissions to avoid permission prompts
        context = browser.new_context(
            permissions=["microphone", "camera", "clipboard-read", "clipboard-write"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()

        try:
            # Go to the Spanish version of the landing page
            print("Navigating to http://localhost:3000/es")
            page.goto("http://localhost:3000/es", timeout=60000)

            # Wait for the text to appear
            print("Waiting for 'Street Noise' text...")
            page.wait_for_selector("text=Street Noise", timeout=10000)

            # Verify the genre/BPM text as well
            print("Waiting for 'Rock & Roll • 105 BPM' text...")
            page.wait_for_selector("text=Rock & Roll • 105 BPM", timeout=10000)

            # Scroll into view
            section = page.locator("text=Street Noise")
            section.scroll_into_view_if_needed()

            # Take a screenshot
            screenshot_path = "/home/jules/verification/landing_change.png"
            page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="/home/jules/verification/error.png")
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    verify_landing_text()
