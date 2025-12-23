from playwright.sync_api import Page, expect, sync_playwright
import time
import os

def test_mixtool(page: Page):
    # Ensure dummy file exists
    if not os.path.exists("verification/dummy.wav"):
        with open("verification/dummy.wav", "wb") as f:
            f.write(b"RIFF....WAVEfmt ....data....") # minimal dummy

    # 1. Go to Mix page (ES)
    print("Navigating to /es/mix...")
    page.goto("http://localhost:3000/es/mix")

    # Hide cookie script
    page.add_style_tag(content="#cookiescript_injected_wrapper { display: none !important; }")

    # 2. Upload dummy file
    print("Uploading file...")
    # Find input[type=file]
    page.set_input_files('input[type="file"]', "verification/dummy.wav")

    # 3. Wait for pipeline steps
    print("Waiting for pipeline steps...")
    # "Technical Calibration & EQ" should be visible
    # In Spanish: "Calibración Técnica y EQ"
    calibration_group = page.get_by_text("Calibración Técnica y EQ")
    expect(calibration_group).to_be_visible(timeout=20000)
    print("Found 'Calibración Técnica y EQ'")

    # 4. Verify Space & Depth is NOT visible
    # In Spanish: "Espacio y Profundidad"
    space_group = page.get_by_text("Espacio y Profundidad")
    expect(space_group).not_to_be_visible()
    print("Confirmed 'Espacio y Profundidad' is missing")

    # 5. Verify Colors (Visual check via screenshot, but we can check classes)
    # Technical Calibration & EQ should have purple theme
    # Find the parent div of the text
    # This is brittle but useful for debugging
    # We expect some purple classes
    # content = page.content()
    # if "text-purple-400" in content:
    #     print("Found purple text class")

    # 6. Take screenshot
    print("Taking screenshot...")
    page.screenshot(path="verification/mixtool_verified.png", full_page=True)

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            test_mixtool(page)
        finally:
            browser.close()
