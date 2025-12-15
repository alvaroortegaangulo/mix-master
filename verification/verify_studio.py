
import os
import json
import base64
import struct
from playwright.sync_api import sync_playwright, Page, Route, Request

# Mock data
STUB_JOB_ID = "stub-job-id"
STUB_USER = {"id": 1, "email": "test@piroola.com", "full_name": "Test User"}

def handle_file_request(route: Route, headers):
    # Generate 0.5s of silence
    sample_rate = 44100
    duration = 0.5
    num_samples = int(sample_rate * duration)
    num_channels = 2
    bits_per_sample = 16
    block_align = num_channels * (bits_per_sample // 8)
    byte_rate = sample_rate * block_align
    data_size = num_samples * block_align

    wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE', b'fmt ', 16, 1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample, b'data', data_size)

    data = b'\x00' * data_size

    headers["Content-Type"] = "audio/wav"
    route.fulfill(status=200, headers=headers, body=wav_header + data)

def verify_studio(page: Page):
    page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))
    page.on("pageerror", lambda exc: print(f"PAGE ERROR: {exc}"))

    # Hide cookies
    page.add_style_tag(content="#cookiescript_injected_wrapper { display: none !important; }")

    # Inject auth
    page.add_init_script("""
        window.localStorage.setItem('access_token', 'fake-token');
    """)

    # Mock Web Audio API
    page.add_init_script("""
    window.AudioContext = class {
      constructor() {
        this.state = 'running';
        this.destination = {};
      }
      createGain() { return { connect: () => {}, gain: { value: 1, setTargetAtTime: () => {} } }; }
      createStereoPanner() { return { connect: () => {}, pan: { value: 0, setTargetAtTime: () => {} } }; }
      createBufferSource() { return { connect: () => {}, start: () => {}, stop: () => {}, buffer: null }; }
      decodeAudioData(ab) {
        return Promise.resolve({
          duration: 30,
          length: 44100 * 30,
          sampleRate: 44100,
          numberOfChannels: 2,
          getChannelData: () => new Float32Array(44100 * 30)
        });
      }
      close() {}
      resume() {}
      get currentTime() { return 0; }
    };
    window.webkitAudioContext = window.AudioContext;
    """)

    def handle_backend(route: Route):
        req = route.request
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*"
        }

        if req.method == "OPTIONS":
            route.fulfill(status=200, headers=headers)
            return

        url = req.url
        if "/auth/me" in url:
            headers["Content-Type"] = "application/json"
            route.fulfill(status=200, headers=headers, json=STUB_USER)
        elif f"/jobs/{STUB_JOB_ID}/stems" in url:
             headers["Content-Type"] = "application/json"
             route.fulfill(status=200, headers=headers, json={"stems": ["vocals.wav", "drums.wav"]})
        elif ".wav" in url:
             handle_file_request(route, headers)
        elif "sign" in url or "file" in url:
             headers["Content-Type"] = "application/json"
             route.fulfill(status=200, headers=headers, json={"url": "http://localhost:3000/mock.wav"})
        else:
            route.continue_()

    page.route("**/*", handle_backend)

    print(f"Navigating to /studio/{STUB_JOB_ID}...")
    page.goto(f"http://localhost:3000/studio/{STUB_JOB_ID}", wait_until="domcontentloaded", timeout=60000)

    print("Page loaded. Waiting for waveform...")
    page.wait_for_timeout(5000) # Give extra time for audio loading

    waveform = page.locator(".w-full.h-\\[300px\\]")
    if waveform.count() > 0:
        print("Waveform container found.")

        # Check shadow root content
        shadow_html = waveform.evaluate("el => el.shadowRoot ? el.shadowRoot.innerHTML : ''")
        print(f"Shadow root content length: {len(shadow_html)}")

        if len(shadow_html) > 50:
             print("SUCCESS: WaveSurfer rendered inside shadow root.")
        else:
             print("WARNING: Waveform container/shadow root is empty. WaveSurfer might have failed to load audio.")

        page.screenshot(path="verification/studio_waveform.png")
    else:
        print("Waveform container NOT found!")
        page.screenshot(path="verification/studio_fail.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(bypass_csp=True)
        page = context.new_page()
        try:
            verify_studio(page)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()
