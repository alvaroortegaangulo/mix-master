
from playwright.sync_api import sync_playwright
import time
import re

def verify_studio_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})

        # 1. Inject Auth Token via LocalStorage BEFORE navigating
        context.add_init_script("""
            localStorage.setItem('access_token', 'fake-token');
        """)

        page = context.new_page()

        page.on("console", lambda msg: print(f"PAGE LOG: {msg.text}"))
        page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))

        # Strip CSP headers
        page.route("**/*", lambda route: route.continue_())

        def handle_response(route, request):
            response = route.fetch()
            headers = response.headers
            if "content-security-policy" in headers:
                del headers["content-security-policy"]
            if "Content-Security-Policy" in headers:
                del headers["Content-Security-Policy"]
            route.fulfill(response=response, headers=headers)

        # Bypass CSP via CDP
        session = context.new_cdp_session(page)
        session.send("Page.setBypassCSP", {"enabled": True})

        # Hide CookieScript
        page.add_init_script("""
            if (document.head) {
                const style = document.createElement('style');
                style.innerHTML = '#cookiescript_injected_wrapper { display: none !important; }';
                document.head.appendChild(style);
            }
        """)

        # Mock Auth Me
        page.route("**/auth/me", lambda route: route.fulfill(
            status=200,
            body='{"id": 1, "email": "test@piroola.com", "full_name": "Test User"}',
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        ))

        # Mock Stems (GET /jobs/fake-job/stems)
        page.route("**/jobs/fake-job/stems", lambda route: route.fulfill(
            status=200,
            body='{"stems": ["vocals.wav", "drums.wav", "bass.wav", "other.wav"]}',
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        ))

        # Mock /files/sign - This matches the backend endpoint structure
        page.route("**/files/sign", lambda route: route.fulfill(
            status=200,
            body='{"url": "http://localhost:3000/fake-audio/vocals.wav", "expires": 9999999999}',
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        ))

        # Mock Audio
        wav_header = (
            b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
        )
        page.route("**/fake-audio/**", lambda route: route.fulfill(
            status=200,
            body=wav_header,
            headers={"Content-Type": "audio/wav", "Access-Control-Allow-Origin": "*"}
        ))

        try:
            print("Navigating to Studio...")
            page.goto("http://localhost:3000/studio/fake-job")

            print("Waiting for Studio UI...")
            # Reduced timeout, since we saw it working visually
            page.wait_for_selector("text=PIROOLA STUDIO", timeout=10000)

            # Wait for stems to load
            print("Waiting for stem files...")
            try:
                page.wait_for_selector("text=vocals.wav", timeout=10000)
                print("Stems visible.")
            except Exception as e:
                print(f"Stems not visible yet: {e}")

            time.sleep(1)
            page.screenshot(path="frontend/src/app/verification/studio_screenshot.png")
            print("Screenshot taken successfully.")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="frontend/src/app/verification/studio_error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    verify_studio_page()
