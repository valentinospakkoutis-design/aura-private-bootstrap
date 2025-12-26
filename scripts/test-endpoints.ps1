# PowerShell Endpoint Testing Script
# Tests all API endpoints for production readiness

param(
    [string]$ApiUrl = "http://localhost:8000"
)

Write-Host "🧪 Testing API Endpoints..." -ForegroundColor Cyan
Write-Host "Base URL: $ApiUrl`n" -ForegroundColor Gray
Write-Host ("─" * 80) -ForegroundColor Gray

$endpoints = @(
    @{Name="Health"; Method="GET"; Path="/health"},
    @{Name="System Status"; Method="GET"; Path="/api/system-status"},
    @{Name="Quote of Day"; Method="GET"; Path="/api/quote-of-day"},
    @{Name="AI Predict"; Method="GET"; Path="/api/ai/predict/XAUUSDT"},
    @{Name="AI Predictions"; Method="GET"; Path="/api/ai/predictions"},
    @{Name="AI Signals"; Method="GET"; Path="/api/ai/signals"},
    @{Name="AI Assets"; Method="GET"; Path="/api/ai/assets"},
    @{Name="AI Status"; Method="GET"; Path="/api/ai/status"},
    @{Name="Portfolio"; Method="GET"; Path="/api/trading/portfolio"},
    @{Name="Paper Trading Stats"; Method="GET"; Path="/api/paper-trading/statistics"},
    @{Name="Broker Status"; Method="GET"; Path="/api/brokers/status"},
    @{Name="CMS Quotes"; Method="GET"; Path="/api/cms/quotes"},
    @{Name="Analytics Performance"; Method="GET"; Path="/api/analytics/performance"},
    @{Name="Notifications"; Method="GET"; Path="/api/notifications"}
)

$results = @()
$successCount = 0

foreach ($endpoint in $endpoints) {
    $url = "$ApiUrl$($endpoint.Path)"
    $startTime = Get-Date
    
    try {
        $response = Invoke-WebRequest -Uri $url -Method $endpoint.Method -ErrorAction Stop
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalMilliseconds
        
        $success = $response.StatusCode -eq 200
        if ($success) { $successCount++ }
        
        $icon = if ($success) { "✅" } else { "❌" }
        Write-Host "$icon $($endpoint.Method.PadRight(4)) $($endpoint.Path.PadRight(40)) $($response.StatusCode.ToString().PadLeft(3)) $([math]::Round($duration).ToString().PadLeft(8))ms" -ForegroundColor $(if ($success) { "Green" } else { "Red" })
        
        $results += @{
            Name = $endpoint.Name
            Path = $endpoint.Path
            Status = $response.StatusCode
            Success = $success
            Duration = $duration
        }
    } catch {
        $icon = "❌"
        Write-Host "$icon $($endpoint.Method.PadRight(4)) $($endpoint.Path.PadRight(40)) ERROR" -ForegroundColor Red
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Yellow
        
        $results += @{
            Name = $endpoint.Name
            Path = $endpoint.Path
            Status = "ERROR"
            Success = $false
            Duration = 0
        }
    }
    
    Start-Sleep -Milliseconds 100
}

Write-Host ("─" * 80) -ForegroundColor Gray
$totalCount = $endpoints.Count
$successRate = [math]::Round(($successCount / $totalCount) * 100, 1)

Write-Host "`n📊 Results: $successCount/$totalCount passed ($successRate%)" -ForegroundColor $(if ($successCount -eq $totalCount) { "Green" } else { "Yellow" })

$failures = $results | Where-Object { -not $_.Success }
if ($failures.Count -gt 0) {
    Write-Host "`n❌ Failed Endpoints:" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host "   $($failure.Path) - $($failure.Status)" -ForegroundColor Yellow
    }
}

exit $(if ($successCount -eq $totalCount) { 0 } else { 1 })

