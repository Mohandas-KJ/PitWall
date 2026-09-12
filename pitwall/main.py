# Main File
# Imports
import time
from providers.x_provider import XProvider
from report.terminal import render_dashboard

def main():
    # Print the Strater
    provider = XProvider()

    provider.connect()

    posts = []

    for iter in range(5):
        posts.append(provider.find_posts(iter))

    render_dashboard(posts,output_path="dashboard.html",open_browser=True)

    input("Enter to close......")
    provider.close()

if "__main__" == __name__:
    main()