
from playwright.sync_api import sync_playwright

def verify_landing_page(page):
    page.goto("http://localhost:3001/en")

    # Wait for the page to load
    page.wait_for_selector('h1')

    # Scroll down to capture different sections
    # Capture the transition between Hero and Listen Difference
    page.evaluate("window.scrollTo(0, 500)")
    page.wait_for_timeout(500)
    page.screenshot(path="/home/jules/verification/section_transition_1.png")

    # Capture the transition between Listen Difference and Pipeline
    page.evaluate("window.scrollTo(0, 1200)")
    page.wait_for_timeout(500)
    page.screenshot(path="/home/jules/verification/section_transition_2.png")

    # Capture the transition between Pipeline and Live Analysis
    page.evaluate("window.scrollTo(0, 2000)")
    page.wait_for_timeout(500)
    page.screenshot(path="/home/jules/verification/section_transition_3.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_landing_page(page)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()
