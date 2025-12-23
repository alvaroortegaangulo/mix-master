import time
import re
from playwright.sync_api import sync_playwright, Page, expect

def test_pipeline_icons(page: Page):
    # Listen to console logs
    page.on("console", lambda msg: print(f"Console: {msg.text}"))
    page.on("pageerror", lambda exc: print(f"PageError: {exc}"))
    # page.on("requestfailed", lambda req: print(f"Request failed: {req.url} {req.failure}"))

    mock_stages = [
        {"key": "S1_STEM_DC_OFFSET", "label": "DC Offset", "description": "Technical Prep", "index": 1, "mediaSubdir": None, "updatesCurrentDir": False, "previewMixRelPath": None},
        {"key": "S2_GROUP_PHASE_DRUMS", "label": "Phase Alignment", "description": "Calibration", "index": 2, "mediaSubdir": None, "updatesCurrentDir": False, "previewMixRelPath": None},
        {"key": "S5_STEM_DYNAMICS_GENERIC", "label": "Dynamics", "description": "Dynamics", "index": 3, "mediaSubdir": None, "updatesCurrentDir": False, "previewMixRelPath": None},
        {"key": "S6_MANUAL_CORRECTION", "label": "Correction", "description": "Manual", "index": 4, "mediaSubdir": None, "updatesCurrentDir": False, "previewMixRelPath": None},
        {"key": "S7_MIXBUS_TONAL_BALANCE", "label": "Tonal Balance", "description": "Mastering", "index": 5, "mediaSubdir": None, "updatesCurrentDir": False, "previewMixRelPath": None},
    ]

    # Global interceptor
    def handle_route(route):
        url = route.request.url
        # Match pipeline/stages on any host
        if "pipeline/stages" in url:
            print(f"MATCHED PIPELINE STAGES: {url}")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=str(mock_stages).replace("'", '"').replace("None", "null").replace("False", "false").replace("True", "true"),
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization"
                }
            )
        elif "jobs/" in url and "status" in url:
             route.fulfill(status=404, headers={"Access-Control-Allow-Origin": "*"})
        else:
            route.continue_()

    page.route("**", handle_route)

    print("Navigating to mix page...")
    page.goto("http://localhost:3000/en/mix")

    print("Waiting for Pipeline IA...")
    page.get_by_text("Pipeline IA").wait_for()

    print("Waiting for stages to load...")
    try:
        page.get_by_text("DC Offset").wait_for(timeout=5000)
        print("Found stage text!")
    except:
        print("Did not find stage text.")

    time.sleep(2)
    page.screenshot(path="verification/verification.png", full_page=True)

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Bypass CSP to allow fetching from 127.0.0.1 if strictly blocked
        context = browser.new_context(viewport={"width": 1280, "height": 1024}, bypass_csp=True)
        page = context.new_page()
        try:
            test_pipeline_icons(page)
            print("Verification screenshot taken at verification/verification.png")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()
