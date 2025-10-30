# ============================================================
# TrendScope-AI: Simple Launch Script
# ============================================================

Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "   TrendScope-AI Setup & Launch" -ForegroundColor Cyan
Write-Host "================================================`n" -ForegroundColor Cyan

# Step 1: Check Docker
Write-Host "[1/8] Checking Docker..." -ForegroundColor Yellow
try {
    docker --version | Out-Null
    docker ps | Out-Null
    Write-Host "  OK - Docker is running`n" -ForegroundColor Green
} catch {
    Write-Host "  ERROR - Docker is not running!" -ForegroundColor Red
    Write-Host "  Please start Docker Desktop and try again`n" -ForegroundColor Yellow
    exit 1
}

# Step 2: Install Python dependencies
Write-Host "[2/8] Installing Python dependencies..." -ForegroundColor Yellow
$packages = "kafka-python", "requests", "praw", "cassandra-driver", "pyspark", "river", "mlflow", "vaderSentiment", "prometheus-client", "python-dotenv"
python -m pip install $packages -q 2>&1 | Out-Null
Write-Host "  OK - Dependencies installed`n" -ForegroundColor Green

# Step 3: Check .env file
Write-Host "[3/8] Checking .env file..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  OK - .env file exists`n" -ForegroundColor Green
} else {
    Write-Host "  Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "  OK - .env created`n" -ForegroundColor Green
}

# Step 4: Clean up old containers
Write-Host "[4/8] Cleaning up old containers..." -ForegroundColor Yellow
docker-compose down -v 2>&1 | Out-Null
Write-Host "  OK - Cleanup complete`n" -ForegroundColor Green

# Step 5: Build Docker images
Write-Host "[5/8] Building Docker images (this may take 5-10 minutes)..." -ForegroundColor Yellow
Write-Host "  Please wait...`n" -ForegroundColor Gray
docker-compose build 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK - All images built successfully`n" -ForegroundColor Green
} else {
    Write-Host "  ERROR - Build failed!`n" -ForegroundColor Red
    exit 1
}

# Step 6: Launch services
Write-Host "[6/8] Launching all services..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n  OK - All services started`n" -ForegroundColor Green
} else {
    Write-Host "`n  ERROR - Failed to start services!`n" -ForegroundColor Red
    exit 1
}

# Step 7: Wait for services
Write-Host "[7/8] Waiting for services to initialize (60 seconds)..." -ForegroundColor Yellow
for ($i = 1; $i -le 12; $i++) {
    Write-Host "  [$i/12] " -NoNewline
    Start-Sleep -Seconds 5
    Write-Host "." -NoNewline -ForegroundColor Gray
}
Write-Host "`n  OK - Services should be ready`n" -ForegroundColor Green

# Step 8: Initialize Cassandra
Write-Host "[8/8] Initializing database schema..." -ForegroundColor Yellow
docker-compose exec -T cassandra cqlsh -e "
CREATE KEYSPACE IF NOT EXISTS trendscope 
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE trendscope;

CREATE TABLE IF NOT EXISTS movie_trends (
    movie_title TEXT,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    popularity DOUBLE,
    vote_average DOUBLE,
    vote_count INT,
    mentions_count INT,
    avg_sentiment DOUBLE,
    trend_score DOUBLE,
    PRIMARY KEY ((movie_title), window_start)
) WITH CLUSTERING ORDER BY (window_start DESC);

CREATE TABLE IF NOT EXISTS predictions (
    movie_title TEXT,
    prediction_time TIMESTAMP,
    actual_trend_score DOUBLE,
    predicted_trend_score DOUBLE,
    prediction_error DOUBLE,
    PRIMARY KEY ((movie_title), prediction_time)
) WITH CLUSTERING ORDER BY (prediction_time DESC);

CREATE TABLE IF NOT EXISTS model_metrics (
    metric_name TEXT,
    timestamp TIMESTAMP,
    value DOUBLE,
    PRIMARY KEY ((metric_name), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC);
" 2>&1 | Out-Null

Write-Host "  OK - Database initialized`n" -ForegroundColor Green

# Show status
Write-Host "`n================================================" -ForegroundColor Green
Write-Host "   LAUNCH COMPLETE!" -ForegroundColor Green
Write-Host "================================================`n" -ForegroundColor Green

Write-Host "Current Status:" -ForegroundColor Cyan
docker-compose ps

Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "   HOW TO VIEW RESULTS" -ForegroundColor Cyan
Write-Host "================================================`n" -ForegroundColor Cyan

Write-Host "1. GRAFANA (Main Dashboard)" -ForegroundColor Yellow
Write-Host "   URL:   http://localhost:3000" -ForegroundColor White
Write-Host "   Login: admin / admin" -ForegroundColor Gray
Write-Host ""

Write-Host "2. MLFLOW (ML Experiments)" -ForegroundColor Yellow
Write-Host "   URL:   http://localhost:5000" -ForegroundColor White
Write-Host ""

Write-Host "3. PROMETHEUS (Metrics)" -ForegroundColor Yellow
Write-Host "   URL:   http://localhost:9090" -ForegroundColor White
Write-Host ""

Write-Host "4. SPARK UI (Processing)" -ForegroundColor Yellow
Write-Host "   URL:   http://localhost:8080" -ForegroundColor White
Write-Host ""

Write-Host "5. LIVE LOGS" -ForegroundColor Yellow
Write-Host "   Command: docker-compose logs -f" -ForegroundColor White
Write-Host ""

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   TIMELINE" -ForegroundColor Cyan
Write-Host "================================================`n" -ForegroundColor Cyan

Write-Host "  Now:      Services starting" -ForegroundColor Gray
Write-Host "  +5 min:   First data fetched" -ForegroundColor Gray
Write-Host "  +10 min:  First TrendScores" -ForegroundColor Gray
Write-Host "  +15 min:  First predictions" -ForegroundColor Gray
Write-Host "  +20 min:  Graphs in Grafana!" -ForegroundColor Green
Write-Host ""

Write-Host "TIP: Open Grafana now and watch data appear!`n" -ForegroundColor Yellow

Write-Host "Starting log viewer in 5 seconds (Ctrl+C to exit)..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

docker-compose logs -f
