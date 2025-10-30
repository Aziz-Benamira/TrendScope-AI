@echo off
echo 🎬 TrendScope-AI Setup Script
echo ==============================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose is not installed. Please install Docker Desktop first.
    exit /b 1
)

echo ✅ Docker and Docker Compose are installed
echo.

REM Check if .env file exists
if not exist .env (
    echo 📝 Creating .env file from template...
    copy .env.example .env
    echo ⚠️  Please edit .env file and add your API credentials:
    echo    - TMDB_API_KEY
    echo    - REDDIT_CLIENT_ID
    echo    - REDDIT_CLIENT_SECRET
    echo.
    pause
)

echo 🚀 Starting TrendScope-AI...
echo.

REM Start Cassandra first
echo 1️⃣ Starting Cassandra...
docker-compose up -d cassandra

echo ⏳ Waiting for Cassandra to be ready (this may take 30-60 seconds)...
timeout /t 30 /nobreak >nul

echo ✅ Cassandra should be ready
echo.

REM Initialize Cassandra schema
echo 2️⃣ Initializing Cassandra schema...
docker-compose run --rm -v %cd%/storage:/app python:3.10-slim bash -c "cd /app && pip install -r requirements.txt && python init_cassandra.py"

echo ✅ Cassandra schema initialized
echo.

REM Start remaining services
echo 3️⃣ Starting all services...
docker-compose up -d

echo.
echo ⏳ Waiting for all services to start...
timeout /t 20 /nobreak >nul

REM Check service status
echo.
echo 📊 Service Status:
docker-compose ps

echo.
echo ==========================================
echo ✅ TrendScope-AI is now running!
echo ==========================================
echo.
echo 📈 Access the dashboards:
echo    - Grafana:     http://localhost:3000 (admin/admin)
echo    - MLflow:      http://localhost:5000
echo    - Prometheus:  http://localhost:9090
echo    - Spark UI:    http://localhost:8080
echo.
echo 📝 View logs:
echo    docker-compose logs -f
echo.
echo 🛑 Stop services:
echo    docker-compose down
echo.
pause
