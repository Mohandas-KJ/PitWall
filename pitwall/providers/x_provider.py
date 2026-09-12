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
        return posts

    def close(self):
        self.browser.close()
        self.playwright.stop()
