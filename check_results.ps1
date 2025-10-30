# ============================================================
# TrendScope-AI: Quick Results Checker
# ============================================================
# Run this script anytime to check if data is flowing
# ============================================================

Write-Host "`n" -NoNewline
Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          TrendScope-AI Results Checker                ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host "`n"

# ============================================================
# 1. Check Services Status
# ============================================================

Write-Host "🐳 Service Status:" -ForegroundColor Yellow
Write-Host ""
docker-compose ps
Write-Host ""

# ============================================================
# 2. Check Kafka Topics
# ============================================================

Write-Host "📨 Kafka Topics (Data Streams):" -ForegroundColor Yellow
Write-Host ""

$topics = @("tmdb_stream", "reddit_stream", "trend_stream", "predictions_stream")

foreach ($topic in $topics) {
    Write-Host "  Checking $topic..." -NoNewline
    try {
        $result = docker-compose exec -T kafka kafka-run-class kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic $topic 2>&1
        if ($LASTEXITCODE -eq 0 -and $result) {
            $offset = ($result -split ':')[-1]
            Write-Host " ✅ $offset messages" -ForegroundColor Green
        } else {
            Write-Host " ⚠️  Topic not ready yet" -ForegroundColor Yellow
        }
    } catch {
        Write-Host " ⚠️  Not available yet" -ForegroundColor Yellow
    }
}

Write-Host ""

# ============================================================
# 3. Check Cassandra Data
# ============================================================

Write-Host "💾 Cassandra Database:" -ForegroundColor Yellow
Write-Host ""

Write-Host "  Checking movie_trends table..." -NoNewline
try {
    $result = docker-compose exec -T cassandra cqlsh -e "SELECT COUNT(*) FROM trendscope.movie_trends;" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅ Data found" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Latest 5 TrendScores:" -ForegroundColor Cyan
        docker-compose exec -T cassandra cqlsh -e "SELECT movie_title, window_start, trend_score FROM trendscope.movie_trends LIMIT 5;" 2>&1
    } else {
        Write-Host " ⚠️  No data yet" -ForegroundColor Yellow
    }
} catch {
    Write-Host " ⚠️  Database not ready" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================
# 4. Check ML Service Metrics
# ============================================================

Write-Host "🤖 ML Service Metrics:" -ForegroundColor Yellow
Write-Host ""

Write-Host "  Fetching metrics from http://localhost:8000/metrics..." -NoNewline
try {
    $metrics = Invoke-WebRequest -Uri "http://localhost:8000/metrics" -TimeoutSec 5 2>&1
    if ($metrics.StatusCode -eq 200) {
        Write-Host " ✅ Available" -ForegroundColor Green
        Write-Host ""
        
        # Parse key metrics
        $content = $metrics.Content
        
        if ($content -match 'predictions_total (\d+\.?\d*)') {
            Write-Host "  Total Predictions: " -NoNewline -ForegroundColor Cyan
            Write-Host $matches[1] -ForegroundColor White
        }
        
        if ($content -match 'model_mae (\d+\.?\d*)') {
            Write-Host "  Current MAE: " -NoNewline -ForegroundColor Cyan
            Write-Host $matches[1] -ForegroundColor White
        }
        
        if ($content -match 'model_rmse (\d+\.?\d*)') {
            Write-Host "  Current RMSE: " -NoNewline -ForegroundColor Cyan
            Write-Host $matches[1] -ForegroundColor White
        }
    } else {
        Write-Host " ⚠️  Not responding" -ForegroundColor Yellow
    }
} catch {
    Write-Host " ⚠️  Not available yet" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================
# 5. Recent Logs Summary
# ============================================================

Write-Host "📋 Recent Activity (Last 10 lines per service):" -ForegroundColor Yellow
Write-Host ""

$logServices = @("tmdb-producer", "reddit-producer", "spark-processor", "ml-service")

foreach ($service in $logServices) {
    Write-Host "  ──────────────────────────────────────" -ForegroundColor Gray
    Write-Host "  $service" -ForegroundColor Cyan
    Write-Host "  ──────────────────────────────────────" -ForegroundColor Gray
    docker-compose logs --tail=5 $service 2>&1 | Select-Object -Last 5
    Write-Host ""
}

# ============================================================
# 6. Access URLs
# ============================================================

Write-Host "`n" -NoNewline
Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║          📊 View Results Here:                        ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host "`n"

Write-Host "  🎨 Grafana (Dashboards):  " -NoNewline
Write-Host "http://localhost:3000" -ForegroundColor Cyan
Write-Host "     Login: admin / admin" -ForegroundColor Gray
Write-Host ""

Write-Host "  🔬 MLflow (Experiments):  " -NoNewline
Write-Host "http://localhost:5000" -ForegroundColor Cyan
Write-Host ""

Write-Host "  📈 Prometheus (Metrics):  " -NoNewline
Write-Host "http://localhost:9090" -ForegroundColor Cyan
Write-Host ""

Write-Host "  ⚙️  Spark UI (Jobs):       " -NoNewline
Write-Host "http://localhost:8080" -ForegroundColor Cyan
Write-Host ""

Write-Host "`n💡 TIP: If no data yet, wait 5-10 minutes and run this script again!" -ForegroundColor Yellow
Write-Host "`n"
