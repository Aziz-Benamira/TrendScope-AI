#!/bin/bash

echo "🎬 TrendScope-AI Setup Script"
echo "=============================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and add your API credentials:"
    echo "   - TMDB_API_KEY"
    echo "   - REDDIT_CLIENT_ID"
    echo "   - REDDIT_CLIENT_SECRET"
    echo ""
    read -p "Press Enter after you've updated the .env file..."
fi

echo "🚀 Starting TrendScope-AI..."
echo ""

# Start Cassandra first
echo "1️⃣ Starting Cassandra..."
docker-compose up -d cassandra

echo "⏳ Waiting for Cassandra to be ready (this may take 30-60 seconds)..."
sleep 30

# Check if Cassandra is ready
until docker-compose exec -T cassandra cqlsh -e "DESCRIBE keyspaces;" &> /dev/null; do
    echo "   Still waiting for Cassandra..."
    sleep 10
done

echo "✅ Cassandra is ready"
echo ""

# Initialize Cassandra schema
echo "2️⃣ Initializing Cassandra schema..."
docker-compose run --rm -v $(pwd)/storage:/app python:3.10-slim bash -c "cd /app && pip install -r requirements.txt && python init_cassandra.py"

echo "✅ Cassandra schema initialized"
echo ""

# Start remaining services
echo "3️⃣ Starting all services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for all services to start..."
sleep 20

# Check service status
echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "=========================================="
echo "✅ TrendScope-AI is now running!"
echo "=========================================="
echo ""
echo "📈 Access the dashboards:"
echo "   - Grafana:     http://localhost:3000 (admin/admin)"
echo "   - MLflow:      http://localhost:5000"
echo "   - Prometheus:  http://localhost:9090"
echo "   - Spark UI:    http://localhost:8080"
echo ""
echo "📝 View logs:"
echo "   docker-compose logs -f"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
echo ""
