@echo off
echo ===================================================
echo Starting PropertyWatch AI Frontend (Vite React)
echo ===================================================

cd /d "%~dp0frontend"

if not exist "node_modules\" (
    echo Installing node dependencies...
    npm install
)

echo Launching Vite Dev Server on http://127.0.0.1:5173 ...
npx vite --port 5173 --host 127.0.0.1
pause
