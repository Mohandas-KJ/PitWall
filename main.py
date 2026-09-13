"""
PitWall Root Entrypoint.
Delegates directly to pitwall/main.py.
"""

import sys
import os

# Add pitwall directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "pitwall"))

from pitwall.main import main

if __name__ == "__main__":
    main()
