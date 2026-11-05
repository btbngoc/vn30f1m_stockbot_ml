# Auto Paper Trade Loop for VN30F1M Bot
# Runs paper-trade mode every 5 minutes during market hours

Set-Location $PSScriptRoot

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "🚀 VN30F1M BOT - LIVE PAPER TRADE AUTOMATION LOOP" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Monitoring internet connection & fetching VCI 1m candles automatically..." -ForegroundColor Yellow

$python = ".\.venv\Scripts\python.exe"

while ($true) {
    $now = Get-Date
    $timeStr = $now.ToString("HH:mm:ss")
    
    # Run paper trade pipeline step
    Write-Host "[$timeStr] Updating VCI data & checking paper trade signals..." -ForegroundColor Cyan
    & $python run_pipeline.py --mode paper-trade
    
    # Run monitor check
    & $python run_pipeline.py --mode monitor
    
    Write-Host "Waiting 5 minutes for next candle scan... (Press Ctrl+C to stop)" -ForegroundColor Gray
    Start-Sleep -Seconds 300
}
