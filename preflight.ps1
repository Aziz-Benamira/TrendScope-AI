# Pre-flight Check for TrendScope-AI
Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "   TrendScope-AI Pre-Flight Check" -ForegroundColor Cyan
Write-Host "================================================`n" -ForegroundColor Cyan

$allGood = $true

# Check 1: Docker installed
Write-Host "[1/3] Checking if Docker is installed..." -NoNewline
try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
        Write-Host "      $dockerVersion" -ForegroundColor Gray
    } else {
        Write-Host " FAILED" -ForegroundColor Red
        $allGood = $false
    }
} catch {
    Write-Host " FAILED" -ForegroundColor Red
    Write-Host "      Docker is not installed!" -ForegroundColor Yellow
    Write-Host "      Download from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    $allGood = $false
}

# Check 2: Docker running
Write-Host "`n[2/3] Checking if Docker Desktop is running..." -NoNewline
try {
    $dockerPs = docker ps 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
    } else {
        Write-Host " FAILED" -ForegroundColor Red
        Write-Host "      Docker Desktop is NOT running!" -ForegroundColor Yellow
        Write-Host "      Please start Docker Desktop and wait for it to finish starting" -ForegroundColor Yellow
        $allGood = $false
    }
} catch {
    Write-Host " FAILED" -ForegroundColor Red
    Write-Host "      Docker Desktop is NOT running!" -ForegroundColor Yellow
    $allGood = $false
}

# Check 3: .env file
Write-Host "`n[3/3] Checking .env file..." -NoNewline
if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "TMDB_API_KEY=\w+" -and $envContent -match "REDDIT_CLIENT_ID=\w+") {
        Write-Host " OK" -ForegroundColor Green
        Write-Host "      API keys found in .env" -ForegroundColor Gray
    } else {
        Write-Host " WARNING" -ForegroundColor Yellow
        Write-Host "      .env file exists but API keys may be missing" -ForegroundColor Yellow
        Write-Host "      Please check your .env file" -ForegroundColor Yellow
        $allGood = $false
    }
} else {
    Write-Host " WARNING" -ForegroundColor Yellow
    Write-Host "      .env file not found - will create from .env.example" -ForegroundColor Yellow
}

Write-Host "`n================================================" -ForegroundColor Cyan

if ($allGood) {
    Write-Host "   ALL CHECKS PASSED!" -ForegroundColor Green
    Write-Host "================================================`n" -ForegroundColor Cyan
    Write-Host "Ready to launch! Run:" -ForegroundColor Green
    Write-Host "  .\launch.ps1`n" -ForegroundColor White
} else {
    Write-Host "   PLEASE FIX ISSUES ABOVE" -ForegroundColor Red
    Write-Host "================================================`n" -ForegroundColor Cyan
    Write-Host "ACTION REQUIRED:" -ForegroundColor Yellow
    Write-Host "  1. Make sure Docker Desktop is installed and running" -ForegroundColor White
    Write-Host "  2. Wait for Docker Desktop to fully start (whale icon in system tray)" -ForegroundColor White
    Write-Host "  3. Run this check again: .\preflight.ps1`n" -ForegroundColor White
}
