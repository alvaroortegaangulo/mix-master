
import os
import time
from playwright.sync_api import sync_playwright, expect

def verify_blog_posts():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Create a context with locale 'en' to test English content
        context = browser.new_context(locale='en-US')
        page = context.new_page()

        try:
            # 1. Navigate to the blog index page
            print("Navigating to blog index...")
            # Ensure server is up - retry a few times
            for i in range(10):
                try:
                    page.goto("http://localhost:3000/en/blog", timeout=5000)
                    break
                except Exception as e:
                    print(f"Waiting for server... ({i+1}/10)")
                    time.sleep(2)

            # Wait for content to load
            page.wait_for_selector('h1', timeout=10000)

            # 2. Verify new blog posts are present in the list
            print("Checking for new blog posts...")
            new_posts = [
                "Stems vs. Stereo: Why Stem Mixing Changes the Game",
                "Mastering LUFS: The Ultimate Loudness Guide",
                "The Piroola Workflow: From Demo to Master in Minutes"
            ]

            for post_title in new_posts:
                expect(page.get_by_text(post_title)).to_be_visible()
                print(f"Found post: {post_title}")

            # 3. Navigate to one of the new blog posts and screenshot
            target_post = "Stems vs. Stereo: Why Stem Mixing Changes the Game"
            print(f"Navigating to: {target_post}")
            page.get_by_text(target_post).click()

            # Wait for the post content to load
            expect(page.get_by_role("heading", name="What are Stems?")).to_be_visible()

            # Take a screenshot
            screenshot_path = os.path.abspath("verification/blog_post_verification.png")
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved to: {screenshot_path}")

        except Exception as e:
            print(f"Verification failed: {e}")
            # Take a failure screenshot if possible
            try:
                page.screenshot(path="verification/failure.png")
            except:
                pass
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    verify_blog_posts()
