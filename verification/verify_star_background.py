from playwright.sync_api import sync_playwright
import time

def verify_stars(page):
    # Navigate to home where StarBackground is likely used (e.g. in PipelineInteractiveDiagram)
    # The user said "Pipeline de Audio" section, which corresponds to PipelineInteractiveDiagram.
    # It might be on the landing page or scrolled down.

    # We strip CSP headers to allow interception if needed, but here we just need to render.
    # However, sometimes local fetch fails if CSP blocks.

    # Go to home
    page.goto("http://localhost:3000/")

    # Wait for hydration
    page.wait_for_load_state("networkidle")

    # Scroll to the pipeline section
    # The component is PipelineInteractiveDiagram. Let's look for text "Pipeline" or try to find the section.
    # User mentioned "Pipeline de Audio". In English it might be "Audio Pipeline" or "Pipeline".
    # We can try to find an element with text "Pipeline" and scroll to it.

    pipeline_header = page.get_by_text("Pipeline", exact=False).first
    if pipeline_header.is_visible():
        pipeline_header.scroll_into_view_if_needed()
    else:
        # Fallback: Scroll down a bit
        page.evaluate("window.scrollBy(0, 1000)")

    # Wait for particles to load (they have animation)
    time.sleep(2)

    # Take a screenshot of the viewport
    page.screenshot(path="verification/stars_verification.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Grant permissions or modify context if needed
        context = browser.new_context()
        page = context.new_page()
        try:
            verify_stars(page)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()
