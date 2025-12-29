# TrendScope-AI Project Status

## What Has Been Done
- RAG chatbot pipeline built with FastAPI backend and React frontend
- ChromaDB vector store for semantic search of movie/TV reviews
- Reddit streaming and filtering for quality reviews
- TMDB API fallback for movies not covered on Reddit
- Debug endpoints and improved prompt engineering
- CSS and UI fixes for chat panel
- Quality filtering (min 50 chars, no bots, no spoilers)
- Relevance checking for movie queries

## Current Issues
- ChromaDB/Backend startup issues on Windows (signal handling)
- Cassandra driver not available (Python 3.12 asyncore removal)
- Kafka not running (can be ignored for RAG-only mode)

## What Needs To Be Done
- Test TMDB fallback for classic movies (e.g., Lord of the Rings)
- Expand sources (IMDB, Metacritic, etc.)
- Improve LLM honesty when data is missing
- Refactor FastAPI event handlers for deprecation warnings
- Document endpoints and pipeline for new contributors

## How To Run
1. Start ChromaDB:
   ```
   chroma run --host localhost --port 8000 --path ./chroma_data
   ```
2. Start backend:
   ```
   set CHROMA_HOST=localhost
   set OLLAMA_HOST=localhost
   python backend/main.py
   ```
3. Start frontend:
   ```
   cd web-dashboard
   npm install
   npm run dev
   ```

## Notes For AI Agent
- All code is modular and documented
- Main logic in `rag/rag_service.py` and `embedding_service.py`
- TMDB fallback logic is in `rag_service.py` (see `_search_tmdb` and `query`)
- Debug endpoints available for inspecting LLM context
- See `README.md` and `docs/ARCHITECTURE.md` for more details

---
For any questions, check the summary above or ask the AI agent for code navigation help.
