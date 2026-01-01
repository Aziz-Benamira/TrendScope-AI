# SETUP GUIDE FOR NEW COLLABORATORS

## 🚀 Quick Start (RAG Chatbot Mode)

The easiest way to run TrendScope-AI is using the RAG chatbot, which only requires:

- Python 3.11+
- Node.js 18+
- Ollama with Mistral
- ChromaDB

---

## 1. Prerequisites to Install

### Python 3.11 or 3.12

The project uses Python 3.12, but 3.11 works too.

### Node.js & npm

For the React frontend dashboard. Version 18+ recommended.

### Ollama + Mistral Model

1. Download Ollama from https://ollama.ai
2. After installing, pull Mistral:
   ```bash
   ollama pull mistral
   ```
   This is the LLM used for generating answers in the RAG chatbot.

### ChromaDB

Vector database for storing movie review embeddings.

```bash
pip install chromadb
```

---

## 2. API Keys Required

Create a `.env` file in the project root (copy from `.env.example`):

### TMDB API Key (Required for RAG chatbot)

- Get from: https://www.themoviedb.org/settings/api
- Free account required
- Used for movie metadata and reviews

### Reddit API Credentials (Optional - only if using full pipeline)

- Get from: https://www.reddit.com/prefs/apps
- Click "Create App" → choose "script"
- You'll need: Client ID, Client Secret, User Agent

**Example `.env` file:**

```env
TMDB_API_KEY=your_actual_tmdb_key_here

# For RAG chatbot
CHROMA_HOST=localhost
CHROMA_PORT=8000
OLLAMA_HOST=localhost
OLLAMA_PORT=11434

# Optional - for full pipeline only
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_secret
REDDIT_USER_AGENT=TrendScope-AI/1.0
```

---

## 3. Installation Steps

```bash
# 1. Clone the repo (you've done this already)
cd TrendScope-AI

# 2. Install Python dependencies
pip install -r backend/requirements.txt
pip install -r rag/requirements.txt

# 3. Install frontend dependencies
cd web-dashboard
npm install
cd ..

# 4. Make sure Ollama is running with Mistral
ollama serve
# In another terminal:
ollama pull mistral
```

---

## 4. Running the Project (RAG Chatbot Mode)

You need 4 terminal windows:

### Terminal 1 - Start Ollama (if not already running)

```bash
ollama serve
```

### Terminal 2 - Start ChromaDB

```bash
chroma run --host localhost --port 8000 --path ./chroma_data
```

### Terminal 3 - Start Backend

```bash
# Windows
set CHROMA_HOST=localhost
set OLLAMA_HOST=localhost
python backend/main.py

# Linux/Mac
CHROMA_HOST=localhost OLLAMA_HOST=localhost python backend/main.py
```

### Terminal 4 - Start Frontend

```bash
cd web-dashboard
npm run dev
```

### Open in Browser

Navigate to: http://localhost:5173

---

## 5. Project Structure

```
TrendScope-AI/
├── backend/                 # FastAPI backend server
│   ├── main.py             # API endpoints
│   └── requirements.txt
├── rag/                     # RAG service module
│   ├── rag_service.py      # Core RAG logic (ChromaDB + Ollama)
│   └── requirements.txt
├── web-dashboard/           # React frontend
│   ├── src/
│   │   ├── App.jsx         # Main chat component
│   │   └── ...
│   ├── package.json
│   └── vite.config.js
├── processors/              # (Full pipeline) Spark streaming
├── producers/               # (Full pipeline) Data producers
│   ├── reddit/
│   └── tmdb/
├── storage/                 # (Full pipeline) Cassandra storage
└── monitoring/              # (Full pipeline) Prometheus/Grafana
```

---

## 6. What's Included

### ✅ RAG Chatbot (fully working)

- ChromaDB vector store for review embeddings
- Ollama + Mistral for LLM generation
- TMDB API for movie data and reviews
- Quality filtering (no bots, no spoilers, min 50 chars)
- React chat interface with source citations

### ⚠️ Full Pipeline (needs Kafka/Cassandra - optional)

- Reddit/TMDB streaming producers
- Spark processing
- Cassandra storage
- **NOT required to run the RAG chatbot**

---

## 7. Key Technologies

| Component  | Technology                               | Purpose                           |
| ---------- | ---------------------------------------- | --------------------------------- |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Convert reviews to vectors        |
| Vector DB  | ChromaDB                                 | Store and search embeddings       |
| LLM        | Ollama + Mistral                         | Generate natural language answers |
| Backend    | FastAPI                                  | Python API server                 |
| Frontend   | React + Vite + TailwindCSS               | Chat UI                           |
| Movie Data | TMDB API                                 | Metadata and reviews              |

---

## 8. Troubleshooting

| Problem                   | Solution                                             |
| ------------------------- | ---------------------------------------------------- |
| ChromaDB connection error | Make sure ChromaDB is running on port 8000           |
| Ollama not found          | Ensure `ollama serve` is running                     |
| No TMDB data              | Check API key is valid in .env                       |
| Empty responses           | Ollama/Mistral might be slow first time (warming up) |
| Frontend not connecting   | Check backend is on port 8080, CORS is enabled       |

### Common Commands

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Check if ChromaDB is running
curl http://localhost:8000/api/v1/heartbeat

# Check backend health
curl http://localhost:8080/health
```

---

## 9. Files NOT in Git (you'll generate these)

- `node_modules/` - Run `npm install` in web-dashboard/
- `chroma_data/` - Generated when ChromaDB runs
- `.env` - Create from `.env.example`
- `__pycache__/` - Python cache files

---

## 10. Quick Test

After everything is running, try these queries in the chat:

1. "What do people think about Oppenheimer?"
2. "Is Dune Part Two worth watching?"
3. "What are common criticisms of recent Marvel movies?"

The system will:

1. Search TMDB for the movie
2. Fetch and index reviews
3. Find relevant reviews using semantic search
4. Generate a natural language answer using Mistral
