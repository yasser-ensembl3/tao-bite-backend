@echo off
echo ==========================================
echo   Tao of Founders - Backend Launcher
echo ==========================================
echo.

REM Check if venv exists
if not exist "venv\" (
    echo [WARNING] Virtual environment not found!
    echo [INFO] Creating virtual environment...
    python -m venv venv
    echo [SUCCESS] Virtual environment created
    echo.
)

REM Activate venv
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if .env exists
if not exist ".env" (
    echo [WARNING] .env file not found!
    echo [INFO] Please create .env from .env.example and add your API keys
    echo.
    echo Run: copy .env.example .env
    echo Then edit .env with your API keys
    echo.
    pause
)

REM Start the server
echo [INFO] Starting Flask server on http://localhost:8080
echo.
python app.py

pause
