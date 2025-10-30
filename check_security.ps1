# Security Check Script
Write-Host "`n================================================" -ForegroundColor Red
Write-Host "       SECURITY STATUS CHECK" -ForegroundColor Red
Write-Host "================================================`n" -ForegroundColor Red

Write-Host "Checking security status...`n" -ForegroundColor Yellow

# Check 1: .env in gitignore
Write-Host "1. Checking .gitignore..." -NoNewline
if (Select-String -Path ".gitignore" -Pattern "^\.env$" -Quiet) {
    Write-Host " OK - .env is in .gitignore" -ForegroundColor Green
} else {
    Write-Host " FAIL - .env NOT in .gitignore!" -ForegroundColor Red
}

# Check 2: .env not tracked by git
Write-Host "2. Checking git status..." -NoNewline
$gitStatus = git status --porcelain 2>&1
if ($gitStatus -notmatch "\.env$" -and $gitStatus -notmatch "\.env ") {
    Write-Host " OK - .env is not tracked" -ForegroundColor Green
} else {
    Write-Host " WARNING - .env appears in git status!" -ForegroundColor Red
}

# Check 3: .env.example has no real keys
Write-Host "3. Checking .env.example..." -NoNewline
$envExample = Get-Content ".env.example" -Raw
if ($envExample -match "your_.*_here") {
    Write-Host " OK - .env.example is safe" -ForegroundColor Green
} else {
    Write-Host " WARNING - .env.example might contain real keys!" -ForegroundColor Yellow
}

# Check 4: .env exists locally
Write-Host "4. Checking local .env..." -NoNewline
if (Test-Path ".env") {
    Write-Host " OK - .env exists locally" -ForegroundColor Green
    
    # Check if it has keys
    $env = Get-Content ".env" -Raw
    if ($env -match "TMDB_API_KEY=\w+" -and $env -match "REDDIT_CLIENT_ID=\w+") {
        Write-Host "5. API keys in .env..." -NoNewline
        Write-Host " OK - Keys found" -ForegroundColor Green
    } else {
        Write-Host "5. API keys in .env..." -NoNewline
        Write-Host " WARNING - Keys missing!" -ForegroundColor Yellow
    }
} else {
    Write-Host " FAIL - .env does NOT exist!" -ForegroundColor Red
}

Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "       NEXT STEPS" -ForegroundColor Cyan
Write-Host "================================================`n" -ForegroundColor Cyan

Write-Host "CRITICAL - Revoke Exposed Keys:" -ForegroundColor Red
Write-Host "   1. TMDB: https://www.themoviedb.org/settings/api" -ForegroundColor Yellow
Write-Host "      - Regenerate your API key" -ForegroundColor Gray
Write-Host "   2. Reddit: https://www.reddit.com/prefs/apps" -ForegroundColor Yellow
Write-Host "      - Delete the app and create a new one" -ForegroundColor Gray
Write-Host ""

Write-Host "Update .env with NEW keys:" -ForegroundColor Cyan
Write-Host "   notepad .env" -ForegroundColor White
Write-Host ""

Write-Host "Test new keys:" -ForegroundColor Green
Write-Host "   python test_api_keys.py" -ForegroundColor White
Write-Host ""

Write-Host "Read SECURITY_ALERT.md for detailed instructions`n" -ForegroundColor Yellow
