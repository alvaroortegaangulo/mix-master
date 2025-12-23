from playwright.sync_api import sync_playwright

def verify_header_removal():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the homepage
        try:
            page.goto("http://localhost:3000")
            page.wait_for_load_state("networkidle")

            # Take a screenshot of the header
            # The header is a fixed element at the top
            page.screenshot(path="verification/header_verification.png", clip={"x": 0, "y": 0, "width": 1920, "height": 100})
            print("Screenshot taken.")

            # Assert RSS is NOT present
            # We search for "RSS" text or link
            content = page.content()
            if "RSS" in content or "rss.xml" in content:
                print("FAILURE: RSS link still present in the page.")
            else:
                print("SUCCESS: RSS link NOT found.")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    verify_header_removal()
