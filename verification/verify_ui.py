from playwright.sync_api import sync_playwright

def verify_mixtool_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        # Mock translations since we might not have full locale support in bare environment or waiting for hydration
        # Actually Next.js should handle it. We'll go to /en/mix or /es/mix.
        # The user's request was in Spanish, so let's try /es/mix if possible, or /en/mix.
        # I'll try /en/mix first as it's likely default.

        # We need to simulate a user state or mock the mix page.
        # The mix page requires authentication usually, but let's see if we can view the UI components
        # or if it redirects to login.
        # If it redirects, I might need to mock the auth or use a test account.
        # Alternatively, since I modified the component `MixTool.tsx`, I can just check if it renders.
        # If the page redirects, I can try to access the component in isolation if there was a storybook, but there isn't.

        # Let's try to go to /mix.
        try:
            page.goto("http://localhost:3000/en/mix", timeout=10000)

            # Check if we are redirected to login
            if "login" in page.url or "auth" in page.url:
                print("Redirected to login. Attempting to bypass or log in.")
                # If there's a way to bypass auth locally?
                # Maybe I can just modify MixTool to render without auth for a sec?
                # Or better, just verify the login page if I can't get past.
                # But I need to see MixTool.

                # Let's try to mock the AuthContext if possible, or just click "Mix my Track" if that leads to a demo?
                # The task description says "/mix" is for authenticated users.
                pass

            page.wait_for_timeout(3000) # Wait for hydration

            # Take a screenshot of the Upload Dropzone
            page.screenshot(path="/home/jules/verification/mixtool_ui.png", full_page=True)
            print("Screenshot taken at /home/jules/verification/mixtool_ui.png")

        except Exception as e:
            print(f"Error: {e}")
            # Take screenshot anyway
            page.screenshot(path="/home/jules/verification/error_state.png")

        browser.close()

if __name__ == "__main__":
    verify_mixtool_ui()
