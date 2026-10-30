@echo off
echo ===================================================
echo Starting PropertyWatch AI Backend Server (FastAPI)
echo ===================================================

cd /d "%~dp0backend"

if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo Initializing database seed data if required...
python -m app.seed_data

echo Launching Uvicorn server on http://127.0.0.1:8000 ...
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
