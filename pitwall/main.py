# Main File
# Imports
import time
from providers.x_provider import XProvider

def main():
    # Print the Strater
    provider = XProvider()

    provider.connect()
    posts = provider.find_posts()
    input("Enter to close......")
    provider.close()

if "__main__" == __name__:
    main()