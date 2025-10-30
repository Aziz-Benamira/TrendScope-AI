# ============================================================
# TrendScope-AI: Complete Setup and Launch Script
# ============================================================
# This script will:
# 1. Check Docker is running
# 2. Install Python dependencies
# 3. Copy .env file
# 4. Build and launch all services
# 5. Monitor startup
# 6. Show you how to access results
# ============================================================

Write-Host "`n" -NoNewline
Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          TrendScope-AI Setup & Launch                 ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host "`n"

# ============================================================
# STEP 1: Check Prerequisites
# ============================================================

Write-Host "📋 STEP 1: Checking Prerequisites..." -ForegroundColor Yellow
Write-Host ""

# Check Docker
Write-Host "  🐳 Checking Docker..." -NoNewline
try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅ Docker is installed" -ForegroundColor Green
        Write-Host "     Version: $dockerVersion" -ForegroundColor Gray
    } else {
        throw "Docker not found"
    }
} catch {
    Write-Host " ❌ Docker is NOT installed or not running" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Check Docker is running
Write-Host "  🐳 Checking Docker daemon..." -NoNewline
try {
    docker ps > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅ Docker is running" -ForegroundColor Green
    } else {
        throw "Docker daemon not running"
    }
} catch {
    Write-Host " ❌ Docker daemon is NOT running" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start Docker Desktop and try again" -ForegroundColor Yellow
    exit 1
}

# Check Python
Write-Host "  🐍 Checking Python..." -NoNewline
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅ Python is installed" -ForegroundColor Green
        Write-Host "     Version: $pythonVersion" -ForegroundColor Gray
    } else {
        throw "Python not found"
    }
} catch {
    Write-Host " ⚠️  Python not found in PATH" -ForegroundColor Yellow
    Write-Host "     Continuing anyway (only needed for local testing)" -ForegroundColor Gray
}

Write-Host ""

# ============================================================
# STEP 2: Install Python Dependencies (for local testing)
# ============================================================

Write-Host "📦 STEP 2: Installing Python Dependencies..." -ForegroundColor Yellow
Write-Host ""

$dependencies = @(
    "kafka-python",
    "requests",
    "praw",
    "cassandra-driver",
    "pyspark",
    "river",
    "mlflow",
    "vaderSentiment",
    "prometheus-client",
    "python-dotenv"
)

Write-Host "  Installing the following packages:" -ForegroundColor Cyan
foreach ($dep in $dependencies) {
    Write-Host "    • $dep" -ForegroundColor Gray
}
Write-Host ""

try {
    Write-Host "  Running pip install..." -NoNewline
    $pipOutput = python -m pip install $dependencies -q 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅ All dependencies installed" -ForegroundColor Green
    } else {
        Write-Host " ⚠️  Some dependencies may have failed" -ForegroundColor Yellow
        Write-Host "     This is OK - Docker containers have their own dependencies" -ForegroundColor Gray
    }
} catch {
    Write-Host " ⚠️  Could not install dependencies" -ForegroundColor Yellow
    Write-Host "     This is OK - Docker containers have their own dependencies" -ForegroundColor Gray
}

Write-Host ""

# ============================================================
# STEP 3: Setup Environment File
# ============================================================

Write-Host "🔑 STEP 3: Setting Up Environment File..." -ForegroundColor Yellow
Write-Host ""

if (Test-Path ".env") {
    Write-Host "  ✅ .env file already exists" -ForegroundColor Green
    Write-Host "     Using existing configuration" -ForegroundColor Gray
} else {
    if (Test-Path ".env.example") {
        Write-Host "  📋 Copying .env.example to .env..." -NoNewline
        Copy-Item ".env.example" ".env"
        Write-Host " ✅ Done" -ForegroundColor Green
        Write-Host ""
        Write-Host "  ⚠️  IMPORTANT: Please verify your API keys in .env file!" -ForegroundColor Yellow
    } else {
        Write-Host "  ❌ .env.example not found!" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""

# ============================================================
# STEP 4: Clean Up Previous Containers (if any)
# ============================================================

Write-Host "🧹 STEP 4: Cleaning Up Previous Containers..." -ForegroundColor Yellow
Write-Host ""

Write-Host "  Stopping and removing old containers..." -NoNewline
docker-compose down -v 2>&1 | Out-Null
Write-Host " ✅ Done" -ForegroundColor Green

Write-Host ""

# ============================================================
# STEP 5: Build Docker Images
# ============================================================

Write-Host "🏗️  STEP 5: Building Docker Images..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  This may take 5-10 minutes on first run..." -ForegroundColor Gray
Write-Host ""

$buildResult = docker-compose build 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ All images built successfully" -ForegroundColor Green
} else {
    Write-Host "  ❌ Build failed!" -ForegroundColor Red
    Write-Host ""
    Write-Host $buildResult
    exit 1
}

Write-Host ""

# ============================================================
# STEP 6: Launch All Services
# ============================================================

Write-Host "🚀 STEP 6: Launching All Services..." -ForegroundColor Yellow
Write-Host ""

Write-Host "  Starting services in detached mode..." -NoNewline
$launchResult = docker-compose up -d 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host " ✅ Done" -ForegroundColor Green
} else {
    Write-Host " ❌ Failed!" -ForegroundColor Red
    Write-Host ""
    Write-Host $launchResult
    exit 1
}

Write-Host ""

# ============================================================
# STEP 7: Monitor Startup
# ============================================================

Write-Host "⏳ STEP 7: Monitoring Startup (this takes 2-3 minutes)..." -ForegroundColor Yellow
Write-Host ""

$services = @(
    "zookeeper",
    "kafka", 
    "cassandra",
    "spark-master",
    "spark-worker",
    "mlflow",
    "prometheus",
    "grafana"
)

Write-Host "  Waiting for core services to be healthy..." -ForegroundColor Gray
Write-Host ""

for ($i = 1; $i -le 30; $i++) {
    Write-Host "  [$i/30] Checking services..." -NoNewline
    $status = docker-compose ps --format json | ConvertFrom-Json
    $healthyCount = ($status | Where-Object { $_.State -eq "running" }).Count
    $totalCount = $status.Count
    
    Write-Host " $healthyCount/$totalCount running" -ForegroundColor Cyan
    
    if ($healthyCount -eq $totalCount) {
        Write-Host ""
        Write-Host "  ✅ All services are running!" -ForegroundColor Green
        break
    }
    
    Start-Sleep -Seconds 6
}

Write-Host ""

# ============================================================
# STEP 8: Initialize Cassandra Schema
# ============================================================

Write-Host "💾 STEP 8: Initializing Database Schema..." -ForegroundColor Yellow
Write-Host ""

Write-Host "  Waiting for Cassandra to be fully ready (30 seconds)..." -NoNewline
Start-Sleep -Seconds 30
Write-Host " ✅ Done" -ForegroundColor Green

Write-Host "  Creating database schema..." -NoNewline
try {
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
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅ Schema created" -ForegroundColor Green
    } else {
        Write-Host " ⚠️  Schema may already exist" -ForegroundColor Yellow
    }
} catch {
    Write-Host " ⚠️  Could not initialize schema" -ForegroundColor Yellow
    Write-Host "     Will retry automatically when services start" -ForegroundColor Gray
}

Write-Host ""

# ============================================================
# STEP 9: Show Status
# ============================================================

Write-Host "📊 STEP 9: Current System Status" -ForegroundColor Yellow
Write-Host ""

docker-compose ps

Write-Host ""

# ============================================================
# STEP 10: Show Access Information
# ============================================================

Write-Host "`n" -NoNewline
Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║          🎉 TrendScope-AI is LAUNCHING! 🎉           ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host "`n"

Write-Host "📍 HOW TO VIEW RESULTS:" -ForegroundColor Cyan
Write-Host ""

Write-Host "  1️⃣  GRAFANA DASHBOARDS (Main Visualization)" -ForegroundColor Yellow
Write-Host "     URL: " -NoNewline
Write-Host "http://localhost:3000" -ForegroundColor Cyan
Write-Host "     Login: " -NoNewline -ForegroundColor Gray
Write-Host "admin" -ForegroundColor White -NoNewline
Write-Host " / " -ForegroundColor Gray -NoNewline
Write-Host "admin" -ForegroundColor White
Write-Host "     Shows: Real-time TrendScores, predictions, ML metrics" -ForegroundColor Gray
Write-Host ""

Write-Host "  2️⃣  MLFLOW EXPERIMENTS (ML Tracking)" -ForegroundColor Yellow
Write-Host "     URL: " -NoNewline
Write-Host "http://localhost:5000" -ForegroundColor Cyan
Write-Host "     Shows: Model performance, MAE, RMSE, experiments" -ForegroundColor Gray
Write-Host ""

Write-Host "  3️⃣  PROMETHEUS METRICS (Raw Metrics)" -ForegroundColor Yellow
Write-Host "     URL: " -NoNewline
Write-Host "http://localhost:9090" -ForegroundColor Cyan
Write-Host "     Shows: Time-series metrics, queries" -ForegroundColor Gray
Write-Host ""

Write-Host "  4️⃣  SPARK UI (Processing Monitor)" -ForegroundColor Yellow
Write-Host "     URL: " -NoNewline
Write-Host "http://localhost:8080" -ForegroundColor Cyan
Write-Host "     Shows: Stream processing jobs, worker status" -ForegroundColor Gray
Write-Host ""

Write-Host "  5️⃣  TERMINAL LOGS (Real-time Activity)" -ForegroundColor Yellow
Write-Host "     Command: " -NoNewline
Write-Host "docker-compose logs -f" -ForegroundColor Cyan
Write-Host "     Shows: Live logs from all services" -ForegroundColor Gray
Write-Host ""

Write-Host "⏰ TIMELINE:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  • Now:         Services starting up" -ForegroundColor Gray
Write-Host "  • +5 min:      First TMDB data fetch" -ForegroundColor Gray
Write-Host "  • +10 min:     First TrendScores calculated" -ForegroundColor Gray
Write-Host "  • +15 min:     First ML predictions" -ForegroundColor Gray
Write-Host "  • +20 min:     Grafana shows graphs!" -ForegroundColor Green
Write-Host ""

Write-Host "📊 WHAT YOU'LL SEE IN GRAFANA:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  • TrendScore Timeline - Line graph showing movie trends over time" -ForegroundColor Gray
Write-Host "  • Top Trending Movies - Table of highest scoring movies" -ForegroundColor Gray
Write-Host "  • Prediction Accuracy - MAE, RMSE metrics" -ForegroundColor Gray
Write-Host "  • Sentiment Analysis - Positive/Negative/Neutral distribution" -ForegroundColor Gray
Write-Host "  • Reddit Activity - Mentions per movie" -ForegroundColor Gray
Write-Host ""

Write-Host "🔍 USEFUL COMMANDS:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  # View all logs" -ForegroundColor Gray
Write-Host "  docker-compose logs -f" -ForegroundColor White
Write-Host ""
Write-Host "  # View specific service logs" -ForegroundColor Gray
Write-Host "  docker-compose logs -f ml-service" -ForegroundColor White
Write-Host "  docker-compose logs -f tmdb-producer" -ForegroundColor White
Write-Host ""
Write-Host "  # Check service status" -ForegroundColor Gray
Write-Host "  docker-compose ps" -ForegroundColor White
Write-Host ""
Write-Host "  # Query Cassandra database" -ForegroundColor Gray
Write-Host "  docker-compose exec cassandra cqlsh" -ForegroundColor White
Write-Host "  > USE trendscope;" -ForegroundColor White
Write-Host "  > SELECT * FROM movie_trends LIMIT 10;" -ForegroundColor White
Write-Host ""
Write-Host "  # Stop everything" -ForegroundColor Gray
Write-Host "  docker-compose down" -ForegroundColor White
Write-Host ""

Write-Host "💡 TIP: Open Grafana now and watch data appear in real-time!" -ForegroundColor Yellow
Write-Host ""

Write-Host "🎬 Starting real-time log monitoring in 5 seconds..." -ForegroundColor Cyan
Write-Host "   (Press Ctrl+C to stop viewing logs)" -ForegroundColor Gray
Write-Host ""

Start-Sleep -Seconds 5

# Show logs
docker-compose logs -f
