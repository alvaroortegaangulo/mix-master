import time
from playwright.sync_api import sync_playwright

def verify_glow():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to the local server
        page.goto("http://localhost:3000")

        # Wait for fonts and content to load
        time.sleep(3)

        # 1. Capture Hero Section Title
        # "Sonido de Estudio Perfeccionado por IA"
        # We need to capture the element and its surrounding to see the glow
        hero_h1 = page.locator("h1.glow-violet")
        if hero_h1.count() > 0:
            print("Found Hero H1 with glow-violet")
            hero_h1.screenshot(path="verification/hero_glow.png")
        else:
            print("Hero H1 not found or missing class")

        # 2. Scroll to 'Escucha la diferencia' section and capture
        # It's likely down the page. We can search by text.
        difference_title = page.get_by_role("heading", name="Escucha la diferencia")
        if difference_title.count() > 0:
            difference_title.scroll_into_view_if_needed()
            time.sleep(1) # wait for scroll/animations
            print("Found 'Escucha la diferencia' title")
            # Take a screenshot of the section or just the title
            difference_title.screenshot(path="verification/difference_glow.png")
        else:
             print("'Escucha la diferencia' title not found")
             # Fallback search by part of text
             fallback = page.locator("h2.glow-amber")
             if fallback.count() > 0:
                  print("Found fallback h2 with glow-amber")
                  fallback.first.scroll_into_view_if_needed()
                  fallback.first.screenshot(path="verification/difference_glow_fallback.png")

        browser.close()

if __name__ == "__main__":
    verify_glow()
