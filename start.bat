@echo off
echo ========================================
echo    DocuMind AI - Starting Servers
echo ========================================
echo.

echo [1/2] Starting Backend Server...
start "DocuMind Backend" cmd /k "cd /d D:\documind\backend && venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 5 /nobreak >nul

echo [2/2] Starting Frontend Server...
start "DocuMind Frontend" cmd /k "cd /d D:\documind\frontend && npm run dev"

echo.
echo ========================================
echo   Servers Starting!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo ========================================
echo.
echo Press any key to exit this window...
pause >nul