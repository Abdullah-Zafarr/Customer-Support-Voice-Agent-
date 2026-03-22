# 🚀 AI Voice Agent - Local Run & Expose Script

Write-Host "Starting AI Voice Agent (FastAPI Backend)..." -ForegroundColor Cyan
# Start the backend server in a separate window so you can see live logs
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '--- FastAPI Logs ---' -ForegroundColor Yellow; .\.venv\Scripts\python main.py" -WindowStyle Normal

Start-Sleep -Seconds 3 # Give it a moment to start the server

Write-Host "Creating Secure HTTPS Tunnel via Serveo..." -ForegroundColor Green
Write-Host "-------------------------------------------"
Write-Host "Share the URL below with your boss for testing!" -ForegroundColor White
Write-Host "-------------------------------------------"

# Create the public tunnel. 
ssh -R 80:localhost:8000 serveo.net
