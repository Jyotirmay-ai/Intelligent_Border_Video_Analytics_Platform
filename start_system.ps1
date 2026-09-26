# IBVAP Master Startup Script
$ROOT = "D:\software Projects\SIH\ibvap-full-project"

Write-Host "Step 1: Clearing existing processes..." -ForegroundColor Yellow
Stop-Process -Name "node" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue

Write-Host "Step 2: Launching System Stack..." -ForegroundColor Green
# Run start_all.ps1 using the call operator with full path
& "$ROOT\start_all.ps1"

Write-Host "System is now booting. Please check the opened terminal windows." -ForegroundColor White
