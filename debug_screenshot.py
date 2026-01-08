from playwright.sync_api import sync_playwright

def debug_screenshot():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:3000/en/mix/result/mock-job-123")
        page.screenshot(path="verification/debug_fail.png")
        print("Captured debug_fail.png")
        browser.close()

if __name__ == "__main__":
    debug_screenshot()
