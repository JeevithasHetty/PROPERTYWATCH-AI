@echo off
echo ===================================================
echo Running PropertyWatch AI Automated Test Suite
echo ===================================================

cd /d "%~dp0backend"
call venv\Scripts\activate.bat
pytest -v
pause
