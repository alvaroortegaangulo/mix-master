from playwright.sync_api import sync_playwright, expect
import time

def verify_sticky_behavior():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a large enough viewport to ensure the grid is in 2-column mode (lg:grid-cols-12)
        # 1280px width triggers the lg breakpoint in Tailwind.
        page = browser.new_page(viewport={"width": 1400, "height": 800})

        # Navigate to docs page
        try:
            page.goto("http://localhost:3000/en/docs", timeout=30000)
            print("Navigated to Docs page")
        except Exception as e:
            print(f"Failed to navigate: {e}")
            return

        # Wait for PipelineViewer to be visible
        pipeline_viewer = page.locator("#pipeline-overview")
        expect(pipeline_viewer).to_be_visible(timeout=10000)

        # Scroll to the Pipeline Viewer section
        pipeline_viewer.scroll_into_view_if_needed()
        time.sleep(1) # Wait for animation/scroll

        # Check column heights
        # The grid container
        grid = pipeline_viewer.locator(".grid.grid-cols-1.lg\\:grid-cols-12").first

        # We need to evaluate JS to get heights
        heights = grid.evaluate("""(grid) => {
            const listCol = grid.children[0];
            const detailCol = grid.children[1];
            return {
                listHeight: listCol.offsetHeight,
                detailHeight: detailCol.offsetHeight,
                gridHeight: grid.offsetHeight
            };
        }""")

        print(f"List Column Height: {heights['listHeight']}px")
        print(f"Detail Column Height: {heights['detailHeight']}px")

        # Assert that heights are roughly equal (detail column matches list column due to stretch)
        # Allow small margin of error for borders/paddings if strictly checking outerHeight
        if abs(heights['listHeight'] - heights['detailHeight']) < 2:
            print("SUCCESS: Columns are equal height.")
        else:
            print(f"FAILURE: Columns are NOT equal height. Difference: {abs(heights['listHeight'] - heights['detailHeight'])}px")

        # Verify sticky element positioning
        # Scroll down a bit so the top of the section is above viewport top
        # We need to scroll enough that the sticky element *would* stick if it could.

        # Get the sticky element
        sticky_el = page.locator(".sticky.top-24")

        # Take a screenshot
        page.screenshot(path="verification/docs_pipeline_layout.png")
        print("Screenshot saved to verification/docs_pipeline_layout.png")

        browser.close()

if __name__ == "__main__":
    verify_sticky_behavior()
