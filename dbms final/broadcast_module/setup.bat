@echo off
REM ----------------------------
REM Broadcast Module Setup Script
REM ----------------------------

echo Installing Python dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Starting Broadcast Module...
python main.py

echo.
echo Press any key to exit...
pause
