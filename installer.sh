#!/bin/bash

set -e

source .venv/bin/activate
echo "Environment activated!"

pip install -r requirements.txt
echo "Libraries installed"

playwright install chromium
echo "Intsalled Chromium"

echo -n "PitWall Ready to Serve!"