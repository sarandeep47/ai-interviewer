# AI Interviewer Startup Script
# This script launches both the backend FastAPI server and the frontend React Vite server.

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "      Starting AI Interviewer Suite      " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Start FastAPI Backend in a new window
Write-Host "[+] Launching FastAPI backend on http://localhost:8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Starting Backend (FastAPI)...' -ForegroundColor Green; cd backend; .\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000"

# 2. Start Vite Frontend in a new window
Write-Host "[+] Launching Vite frontend on http://localhost:5173..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Starting Frontend (Vite)...' -ForegroundColor Cyan; cd frontend; npm run dev"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Both servers are launching in separate windows." -ForegroundColor Yellow
Write-Host "Backend API: http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend app: http://localhost:5173" -ForegroundColor Yellow
Write-Host "=========================================" -ForegroundColor Cyan
