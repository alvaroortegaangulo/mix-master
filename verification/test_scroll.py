from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Mocking the scroll reveal behavior since we cannot easily scroll and capture transitions in a static screenshot without complex timing
        # Instead, we load the page and check if elements have the correct initial classes

        # Start app (assuming running on 3000)
        page.goto("http://localhost:3000")

        # Wait for hydration
        page.wait_for_timeout(2000)

        # Scroll down to trigger reveals
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000) # Wait for animation to start

        page.screenshot(path="verification/landing_scroll.png", full_page=True)
        browser.close()

if __name__ == "__main__":
    run()
