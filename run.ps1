# QueryFlow AI Launcher
# Run this script using: powershell -ExecutionPolicy Bypass -File .\run.ps1

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "           STARTING QUERYFLOW AI             " -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1. Start backend FastAPI
Write-Host "[1/2] Starting FastAPI Backend on http://localhost:8000..." -ForegroundColor Yellow
$BackendJob = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "Write-Host 'Starting FastAPI Backend...'; .venv\Scripts\python -m uvicorn backend.main:app --port 8000 --reload" -PassThru -WindowStyle Normal

# 2. Start frontend Next.js dev server
Write-Host "[2/2] Starting Next.js Dev Server on http://localhost:3000..." -ForegroundColor Yellow
$FrontendJob = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "Write-Host 'Starting Next.js Frontend...'; cd frontend; npm run dev" -PassThru -WindowStyle Normal

Write-Host "==============================================" -ForegroundColor Green
Write-Host "QueryFlow AI is running!" -ForegroundColor Green
Write-Host "- Backend API: http://localhost:8000" -ForegroundColor Green
Write-Host "- Frontend UI: http://localhost:3000" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host "Press Ctrl+C in this console or close the spawned windows to stop." -ForegroundColor Gray
