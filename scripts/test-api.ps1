# AURA API Testing Script
# Tests all API endpoints

$baseUrl = "http://localhost:8000"
$results = @()

function Test-Endpoint {
    param(
        [string]$Method,
        [string]$Endpoint,
        [object]$Body = $null
    )
    
    $url = "$baseUrl$Endpoint"
    $result = @{
        Method = $Method
        Endpoint = $Endpoint
        Status = "Unknown"
        StatusCode = 0
        Error = $null
    }
    
    try {
        $params = @{
            Uri = $url
            Method = $Method
            TimeoutSec = 5
            UseBasicParsing = $true
        }
        
        if ($Body) {
            $params.Body = ($Body | ConvertTo-Json)
            $params.ContentType = "application/json"
        }
        
        $response = Invoke-WebRequest @params
        $result.Status = "Success"
        $result.StatusCode = $response.StatusCode
    } catch {
        $result.Status = "Failed"
        $result.StatusCode = $_.Exception.Response.StatusCode.value__
        $result.Error = $_.Exception.Message
    }
    
    return $result
}

Write-Host "`n=== AURA API Testing ===" -ForegroundColor Cyan
Write-Host "Base URL: $baseUrl`n" -ForegroundColor Gray

# Health Checks
Write-Host "Health Checks:" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Endpoint "/health"
$results += Test-Endpoint -Method "GET" -Endpoint "/api/system-status"

# Quotes
Write-Host "`nQuotes:" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Endpoint "/api/quote-of-day"

# Brokers
Write-Host "`nBrokers:" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Endpoint "/api/brokers/status"

# Paper Trading
Write-Host "`nPaper Trading:" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Endpoint "/api/paper-trading/portfolio"
$results += Test-Endpoint -Method "GET" -Endpoint "/api/paper-trading/history"

# AI Predictions
Write-Host "`nAI Predictions:" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Endpoint "/api/ai/predict/XAU"

# CMS
Write-Host "`nCMS:" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Endpoint "/api/cms/quotes"

# Notifications
Write-Host "`nNotifications:" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Endpoint "/api/notifications"
$results += Test-Endpoint -Method "GET" -Endpoint "/api/notifications/stats"

# Analytics
Write-Host "`nAnalytics:" -ForegroundColor Yellow
$results += Test-Endpoint -Method "GET" -Endpoint "/api/analytics/performance"

# Summary
Write-Host "`n=== Test Results Summary ===" -ForegroundColor Cyan
$success = ($results | Where-Object { $_.Status -eq "Success" }).Count
$failed = ($results | Where-Object { $_.Status -eq "Failed" }).Count
$total = $results.Count

Write-Host "Total: $total" -ForegroundColor White
Write-Host "Success: $success" -ForegroundColor Green
Write-Host "Failed: $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })

Write-Host "`nDetailed Results:" -ForegroundColor Yellow
$results | ForEach-Object {
    $color = if ($_.Status -eq "Success") { "Green" } else { "Red" }
    Write-Host "  $($_.Method) $($_.Endpoint) - $($_.Status) ($($_.StatusCode))" -ForegroundColor $color
    if ($_.Error) {
        Write-Host "    Error: $($_.Error)" -ForegroundColor DarkGray
    }
}

