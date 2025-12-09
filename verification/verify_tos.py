from playwright.sync_api import sync_playwright, expect

def verify_tos(page):
    # 1. Go to the home page
    page.goto("http://localhost:3000")

    # 2. HIDE COOKIE BANNER (Interferes with clicks)
    # Inject CSS to hide the cookie script wrapper
    page.add_style_tag(content="#cookiescript_injected_wrapper { display: none !important; }")

    # 3. Scroll to footer and verify "Terms of Service" link exists
    tos_link = page.get_by_role("link", name="Terms of Service")
    tos_link.scroll_into_view_if_needed()
    expect(tos_link).to_be_visible()

    # 4. Click the link
    tos_link.click()

    # 5. Verify URL and Title
    expect(page).to_have_url("http://localhost:3000/terms-of-service")
    expect(page.get_by_role("heading", name="Terms of Service")).to_be_visible()

    # 6. Take screenshot of the TOS page
    page.screenshot(path="verification/tos_page.png", full_page=True)

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_tos(page)
            print("Verification successful!")
        except Exception as e:
            print(f"Verification failed: {e}")
            page.screenshot(path="verification/error_retry.png")
            raise
        finally:
            browser.close()
