"""
This Module helps establishing Connection to X.com
Then it redirects to F1 X.com page
Gives a successful browser connection
"""

# Imports
from playwright.sync_api import sync_playwright

# Define Class
class XProvider:

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    def connect(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        self.page = self.browser.new_page()
        self.page.goto("https://x.com/F1")
        print("Connected to F1!")

    def find_posts(self):
        posts = self.page.locator("article")
        print(f"Found {posts.count()} posts!")

        # Get no of Posts
        first_post = posts.nth(0)

        # Extrct Link
        status_link = first_post.locator('a[href^="/F1/status/"]:not([href*="/photo/"])').first

        # Text
        text = first_post.locator('div[dir="auto"]').inner_text()

        # Timestamp
        timestamp = status_link.inner_text()

        # Extract URL
        href = status_link.get_attribute("href")
        url = f"https://x.com{href}"

        images = first_post.locator('img[src*="pbs.twimg.com/media"]')
        image_url = []

        for i in range(images.count()):
            src = images.nth(i).get_attribute("src")
            if src:
                image_url.append(src)


        return text,timestamp,url,image_url

    def close(self):
        self.browser.close()
        self.playwright.stop()
