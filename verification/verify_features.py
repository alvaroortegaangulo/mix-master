
from playwright.sync_api import sync_playwright

def verify_features_section():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Emulate a large desktop screen to see the full section
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        try:
            # Navigate to the local dev server
            print('Navigating to http://localhost:3000...')
            response = page.goto('http://localhost:3000', wait_until='networkidle')
            if not response or response.status != 200:
                print('Failed to load page')
                return

            print('Page loaded. Looking for #features section...')
            # Wait for the features section to be visible
            # The id is 'features'
            features_section = page.locator('#features')
            features_section.wait_for(state='visible', timeout=10000)

            # Scroll to the section
            features_section.scroll_into_view_if_needed()

            # Wait a bit for animations (Aurora is animated)
            print('Waiting for animations...')
            page.wait_for_timeout(3000)

            # Take a screenshot of the features section
            features_section.screenshot(path='verification/features_aurora.png')
            print('Screenshot saved to verification/features_aurora.png')

        except Exception as e:
            print(f'Error: {e}')
            # Take a fallback screenshot if possible
            try:
                page.screenshot(path='verification/error_screenshot.png')
                print('Saved error_screenshot.png')
            except:
                pass
        finally:
            browser.close()

if __name__ == '__main__':
    verify_features_section()
