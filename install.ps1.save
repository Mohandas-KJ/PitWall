$ErrorActionPreference = "Stop"

# Activate virtual environment
& ".\.venv\Scripts\Activate.ps1"
Write-Host "Environment activated!"

# Install Python dependencies
pip install -r requirements.txt
Write-Host "Libraries installed"

# Install Playwright Chromium
playwright install chromium
Write-Host "Installed Chromium"

Write-Host -NoNewline "PitWall Ready to Serve!"
