
import os
from playwright.sync_api import Page, expect, sync_playwright

def test_report_ui(page: Page):
    # Mock API responses
    # 1. Pipeline Stages
    page.route("**/pipeline/stages", lambda route: route.fulfill(
        status=200,
        body=json.dumps([
            {"key": "S7_MIXBUS_TONAL_BALANCE", "label": "Mixbus Tonal Balance", "description": "EQ", "index": 7},
            {"key": "S11_REPORT_GENERATION", "label": "Reporting", "description": "Report", "index": 11}
        ])
    ))

    # 2. Cleanup
    page.route("**/cleanup-temp", lambda route: route.fulfill(status=200))

    # 3. Start Job
    page.route("**/mix", lambda route: route.fulfill(
        status=200,
        body=json.dumps({"jobId": "job_mock_123"})
    ))

    # 4. Job Status (Done with Result)
    page.route("**/jobs/job_mock_123", lambda route: route.fulfill(
        status=200,
        body=json.dumps({
            "status": "done",
            "jobId": "job_mock_123",
            "full_song_url": "/mock_audio.mp3",
            "metrics": {
                "final_peak_dbfs": -1.0,
                "final_rms_dbfs": -10.0,
                "tempo_bpm": 120,
                "key": "C",
                "scale": "Major"
            }
        })
    ))

    # 5. Report JSON
    report_data = {
        "pipeline_version": "1.0",
        "generated_at_utc": "2023-10-27T10:00:00Z",
        "style_preset": "Urban",
        "general_summary": "The mix sounds great.",
        "final_metrics": {
            "lufs_integrated": -9.5,
            "true_peak_dbtp": -0.5,
            "lra": 4.5,
            "crest_factor_db": 12.0
        },
        "stages": [
            {
                "contract_id": "S7_MIXBUS_TONAL_BALANCE",
                "stage_id": "S7_MIXBUS_TONAL_BALANCE",
                "name": "Mixbus Tonal Balance",
                "status": "analyzed",
                "parameters": {
                    "EQ Gains (dB)": {"Low": "+2.0", "High": "-1.5"}
                },
                "images": {
                    "waveform": "mock_wave.png",
                    "spectrogram": "mock_spec.png"
                }
            },
            {
                "contract_id": "S8_MIXBUS_COLOR_GENERIC",
                "name": "Mixbus Color",
                "status": "analyzed",
                "parameters": {
                    "Saturation Drive (dB)": "0.50"
                }
            }
        ]
    }

    page.route("**/files/job_mock_123/S11_REPORT_GENERATION/report.json", lambda route: route.fulfill(
        status=200,
        body=json.dumps(report_data)
    ))

    # Mock Image requests
    page.route("**/files/job_mock_123/S11_REPORT_GENERATION/*.png", lambda route: route.fulfill(
        status=200,
        body=b"fake_image_bytes",
        headers={"Content-Type": "image/png"}
    ))

    # Go to page
    page.goto("http://localhost:3003")

    # Wait for hydration
    page.wait_for_timeout(1000)

    # Upload Dummy File
    # Create a dummy file
    with open("dummy.mp3", "wb") as f:
        f.write(b"ID3" + b"\x00"*100)

    page.set_input_files("input[type='file']", "dummy.mp3")

    # Click Generate
    page.get_by_text("Generate AI Mix").click()

    # Wait for result panel
    # Debugging: Take screenshot before checking result panel
    page.screenshot(path="frontend_debug_before_result.png")

    try:
        expect(page.get_by_text("AI mix & mastering (resultado)")).to_be_visible(timeout=15000)
    except Exception as e:
        print("Could not find 'AI mix & mastering (resultado)'. Check if job finished.")
        # Maybe the mock didn't work as expected or polling logic in component is different
        raise e

    # Click "Ver Informe" (Open Report)
    page.get_by_text("Ver Informe").click()

    # Wait for Report Modal
    expect(page.get_by_text("Mix Summary")).to_be_visible()
    expect(page.get_by_text("Urban")).to_be_visible()

    # Check Stages
    expect(page.get_by_text("Mixbus Tonal Balance")).to_be_visible()

    # Expand First Stage
    page.get_by_text("Mixbus Tonal Balance").click()

    # Check Parameters
    expect(page.get_by_text("EQ Gains (dB)")).to_be_visible()
    expect(page.get_by_text("+2.0")).to_be_visible()

    # Check Images present (by checking alt text)
    expect(page.get_by_alt_text("Waveform")).to_be_visible()

    # Screenshot
    page.screenshot(path="frontend_verification_report.png", full_page=True)


import json

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            test_report_ui(page)
            print("Frontend verification passed!")
        except Exception as e:
            print(f"Frontend verification failed: {e}")
            page.screenshot(path="frontend_failure.png")
        finally:
            browser.close()
