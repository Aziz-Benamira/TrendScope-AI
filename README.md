# 🎬 TrendScope-AI

**Real-Time Movie Trend Analysis with RAG-Powered Insights**

A comprehensive data streaming and AI platform that combines real-time trend analytics with conversational AI for movie insights.

---

## 🎯 Overview

TrendScope-AI is an end-to-end streaming analytics platform that:

1. **Ingests** real-time data from TMDB API and Reddit discussions
2. **Processes** streams with Apache Spark for sentiment analysis and trend scoring
3. **Stores** embeddings in ChromaDB for semantic search
4. **Generates** insights using RAG (Retrieval-Augmented Generation) with Ollama/Mistral

### Key Features

| Feature | Technology | Description |
|---------|------------|-------------|
| **Real-time Streaming** | Kafka + Spark | Live data ingestion and processing |
| **Sentiment Analysis** | VADER | Analyze Reddit discussions and reviews |
| **TrendScore Algorithm** | Custom Formula | Rank movies: 50% Popularity + 30% Mentions + 20% Sentiment |
| **Vector Database** | ChromaDB | 29,365+ review embeddings for semantic search |
| **RAG Chat Interface** | Ollama + Mistral | Conversational AI with retrieval-augmented generation |
| **Modern Dashboard** | React + Vite + TailwindCSS | Real-time stats, trending movies, live charts |
| **Live Statistics** | Dynamic Updates | Track movies, reviews, Reddit activity |
| **Docker Deployment** | Docker Compose | One-command setup with 11 services |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                     │
│     TMDB API ─────────┐         ┌───────── Reddit API                   │
└───────────────────────┼─────────┼───────────────────────────────────────┘
                        │         │
                        ▼         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    INGESTION LAYER (Kafka)                               │
│     tmdb_stream ◄─── TMDB Producer    Reddit Producer ───► reddit_stream│
└─────────────────────────────────────────────────────────────────────────┘
                        │         │
                        ▼         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  PROCESSING LAYER (Spark Streaming)                      │
│     • Sentiment Analysis (VADER)                                         │
│     • TrendScore = w₁×Popularity + w₂×Mentions + w₃×Sentiment           │
│     • Windowed Aggregations                                              │
└─────────────────────────────────────────────────────────────────────────┘
           │                                          │
           ▼                                          ▼
┌──────────────────────┐              ┌────────────────────────────────────┐
│     Cassandra        │              │         RAG LAYER                  │
│   (Trend Storage)    │              │  ┌──────────────────────────────┐  │
└──────────────────────┘              │  │   Embedding Service          │  │
                                      │  │   (sentence-transformers)    │  │
                                      │  └─────────────┬────────────────┘  │
                                      │                ▼                   │
                                      │  ┌──────────────────────────────┐  │
                                      │  │       ChromaDB               │  │
                                      │  │   (Vector Database)          │  │
                                      │  └─────────────┬────────────────┘  │
                                      │                ▼                   │
                                      │  ┌──────────────────────────────┐  │
                                      │  │    Ollama + Mistral          │  │
                                      │  │   (LLM Generation)           │  │
                                      │  └──────────────────────────────┘  │
                                      └────────────────────────────────────┘
                                                       │
                                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                                  │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────┐ │
│  │   Trending Movies List      │    │      RAG Chat Interface         │ │
│  │   (ordered by TrendScore)   │    │   "Why is Mufasa trending?"     │ │
│  └─────────────────────────────┘    └─────────────────────────────────┘ │
│                         React Dashboard                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- NVIDIA GPU with drivers (for Ollama)
- TMDB API Key ([get one here](https://www.themoviedb.org/settings/api))
- Reddit API Credentials ([create app here](https://www.reddit.com/prefs/apps))

### 1. Clone & Configure

```bash
git clone https://github.com/yourusername/TrendScope-AI.git
cd TrendScope-AI

# Copy and edit environment variables
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start Infrastructure

```bash
# Start all services
docker-compose up -d

# Wait for services to be healthy (especially Cassandra)
docker-compose logs -f
```

### 3. Pull Mistral Model (First Time Only)

```bash
# Pull the Mistral model into Ollama
docker exec -it ollama ollama pull mistral
```

### 4. Start Frontend (Automatic with Docker Compose)

The frontend starts automatically with `docker-compose up`. Alternatively, run manually:

```bash
cd web-dashboard
npm install
npm run dev
```

### 5. Verify System is Running

```bash
# Check all services are healthy
docker-compose ps

# Verify data is flowing
curl http://localhost:8001/api/trending
```

### 6. Access the Application

| Service | URL |
|---------|-----|
| **Dashboard** | http://localhost:3003 |
| **API Docs** | http://localhost:8001/docs |
| **Grafana** | http://localhost:3000 (admin/admin) |
| **Prometheus** | http://localhost:9090 |
| **Spark UI** | http://localhost:8080 |

---

## 💬 Using the RAG Chat

Once the system is running with data flowing, you can ask questions like:

| Question Type | Example |
|--------------|---------|
| **Trend Analysis** | "Why is Mufasa trending right now?" |
| **Sentiment** | "What do people think about the acting in Sonic 3?" |
| **Recommendations** | "Is Nosferatu scary? Should I watch it?" |
| **Comparisons** | "How does the new Lion King compare to the original?" |
| **Specific Aspects** | "What are people saying about the CGI?" |

The chat uses RAG to:
1. Search ChromaDB for the 50 most relevant recent reviews
2. Pass them as context to Mistral
3. Generate a natural language summary

---

## 📁 Project Structure

```
TrendScope-AI/
├── backend/                 # FastAPI server + RAG endpoints
│   └── main.py
├── rag/                     # RAG Layer (NEW)
│   ├── embedding_service.py # Kafka → ChromaDB embeddings
│   ├── rag_service.py       # Query processing + LLM
│   ├── vector_store.py      # ChromaDB wrapper
│   └── config.py
├── producers/
│   ├── tmdb/               # TMDB API producer
│   └── reddit/             # Reddit API producer
├── processors/
│   └── spark_streaming_processor.py
├── ml_service/             # Online ML (River)
├── storage/                # Cassandra schemas
├── monitoring/             # Grafana, Prometheus, MLflow
├── web-dashboard/          # React frontend
│   └── src/
│       └── components/
│           └── ChatPanel.jsx  # RAG Chat UI (NEW)
└── docker-compose.yml
```

---

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# API Keys
TMDB_API_KEY=your_tmdb_api_key
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret

# Kafka Topics
KAFKA_TOPIC_TMDB=tmdb_stream
KAFKA_TOPIC_REDDIT=reddit_stream

# TrendScore Weights
W1_POPULARITY=0.4
W2_MENTIONS=0.3
W3_SENTIMENT=0.3

# Ollama
OLLAMA_MODEL=mistral
```

---

## 🔧 Services

| Service | Port | Description |
|---------|------|-------------|
| Kafka | 9092 | Message broker |
| Zookeeper | 2181 | Kafka coordination |
| ChromaDB | 8000 | Vector database for RAG |
| Ollama | 11434 | Local LLM server |
| Backend API | 8001 | FastAPI + RAG endpoints |
| Frontend | 3003 | React dashboard |
| Grafana | 3000 | Monitoring dashboards |
| Prometheus | 9090 | Metrics collection |
| Spark Master | 8080 | Spark cluster UI |
| Embedding Service | 8002 | Review embedding processor |

---

## 📊 API Endpoints

### Trending Movies
```
GET /api/trending?limit=20
GET /api/trends/movie/{title}
```

### RAG Chat
```
POST /api/chat
{
  "query": "Why is Mufasa trending?",
  "movie_title": "Mufasa",  // optional filter
  "hours_back": 24
}

GET /api/chat/movies      # Available movies in RAG
GET /api/chat/stats       # RAG system stats
GET /api/chat/health      # Health check
```

---

## 🎓 Project Submission

This project was developed for academic purposes and includes:

### 📦 Submission Materials

1. **Source Code**: Complete documented codebase
2. **Docker Deployment**: One-command setup with `docker-compose up`
3. **Documentation**: 
   - README.md (this file)
   - GETTING_STARTED.md (setup guide)
   - PROJECT_REPORT.tex (academic report)
   - SUBMISSION_GUIDE.md (submission checklist)
   - GITHUB_GUIDE.md (repository setup)
4. **Live Demo**: Fully functional system with 29,365+ indexed reviews

### ✅ Requirements Addressed

- ✅ Real-time streaming (Kafka + Spark)
- ✅ Sentiment analysis on Reddit discussions (VADER)
- ✅ Vector database for review embeddings (ChromaDB)
- ✅ RAG-powered chat with Mistral LLM
- ✅ TrendScore algorithm for ranking
- ✅ Modern React dashboard with live charts
- ✅ Comprehensive monitoring (Prometheus + Grafana)

### 📊 Project Statistics

- **Total Reviews Indexed**: 29,365+
- **Active Data Sources**: 3 (TMDB API, TMDB Reviews, Reddit)
- **Tracked Movies**: 51+ trending titles
- **Services**: 11 Docker containers
- **Lines of Code**: ~5,000+
- **RAG Iterations**: 11 documented improvements

---

## 🛠️ Troubleshooting

### Ollama Not Starting
```bash
# Check GPU availability
nvidia-smi

# Check Ollama logs
docker logs ollama
```

### ChromaDB Connection Issues
```bash
# Restart ChromaDB
docker-compose restart chromadb
```

### No Data in Dashboard
1. Check Kafka topics: `docker exec kafka kafka-topics --list --bootstrap-server localhost:9092`
2. Check producer logs: `docker logs tmdb-producer`
3. Verify API keys in `.env`

---

## 📄 License

MIT License - See [LICENSE](LICENSE)
