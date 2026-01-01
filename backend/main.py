"""
TrendScope-AI Backend API
FastAPI server for RAG chatbot with movie reviews
"""

import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from rag.rag_service import RAGService

# Load environment variables
load_dotenv()

app = FastAPI(
    title="TrendScope-AI API",
    description="RAG-powered movie review chatbot",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Initialize RAG service
rag_service = None


class ChatRequest(BaseModel):
    message: str
    movie_title: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[dict] = []
    movie_info: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str
    chroma_connected: bool
    ollama_connected: bool


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global rag_service
    try:
        rag_service = RAGService(
            chroma_host=os.getenv("CHROMA_HOST", "localhost"),
            chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
            ollama_host=os.getenv("OLLAMA_HOST", "localhost"),
            ollama_port=int(os.getenv("OLLAMA_PORT", "11434")),
            tmdb_api_key=os.getenv("TMDB_API_KEY")
        )
        print("✅ RAG Service initialized successfully")
    except Exception as e:
        print(f"⚠️ RAG Service initialization warning: {e}")
        rag_service = None


@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "message": "TrendScope-AI API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    chroma_ok = False
    ollama_ok = False
    
    if rag_service:
        chroma_ok = rag_service.check_chroma_connection()
        ollama_ok = rag_service.check_ollama_connection()
    
    return HealthResponse(
        status="healthy" if (chroma_ok and ollama_ok) else "degraded",
        chroma_connected=chroma_ok,
        ollama_connected=ollama_ok
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint for movie review questions
    """
    if not rag_service:
        raise HTTPException(
            status_code=503,
            detail="RAG service not initialized. Check ChromaDB and Ollama connections."
        )
    
    try:
        result = await rag_service.query(
            question=request.message,
            movie_title=request.movie_title
        )
        
        return ChatResponse(
            response=result.get("answer", "I couldn't find an answer to your question."),
            sources=result.get("sources", []),
            movie_info=result.get("movie_info")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/movies/search")
async def search_movies(query: str, limit: int = 10):
    """Search for movies by title"""
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    try:
        results = await rag_service.search_movies(query, limit)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/movies/{movie_id}/index")
async def index_movie_reviews(movie_id: int):
    """Index reviews for a specific movie from TMDB"""
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    try:
        result = await rag_service.index_movie_reviews(movie_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Reddit Live Indexer integration
reddit_indexer = None


@app.post("/reddit/start-indexing")
async def start_reddit_indexing():
    """Start live Reddit indexing to ChromaDB"""
    global reddit_indexer
    
    from rag.reddit_indexer import RedditLiveIndexer
    
    reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
    reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    
    if not reddit_client_id or not reddit_client_secret:
        raise HTTPException(
            status_code=400,
            detail="Reddit API credentials not configured. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables."
        )
    
    if reddit_indexer and reddit_indexer._running:
        return {"status": "already_running", "stats": reddit_indexer.get_stats()}
    
    reddit_indexer = RedditLiveIndexer(
        reddit_client_id=reddit_client_id,
        reddit_client_secret=reddit_client_secret,
        chroma_host=os.getenv("CHROMA_HOST", "localhost"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8000"))
    )
    
    if not reddit_indexer.connect_chroma():
        raise HTTPException(status_code=503, detail="Could not connect to ChromaDB")
    
    reddit_indexer.init_sentiment_analyzer()
    
    if not reddit_indexer.connect_reddit():
        raise HTTPException(status_code=503, detail="Could not connect to Reddit API")
    
    # Do one sync immediately
    indexed = reddit_indexer.sync_once()
    
    return {
        "status": "started",
        "indexed_count": indexed,
        "stats": reddit_indexer.get_stats()
    }


@app.post("/reddit/sync")
async def sync_reddit():
    """Manually trigger a Reddit sync"""
    global reddit_indexer
    
    if not reddit_indexer:
        # Initialize indexer for one-time sync
        from rag.reddit_indexer import RedditLiveIndexer
        
        reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
        reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        
        if not reddit_client_id or not reddit_client_secret:
            raise HTTPException(
                status_code=400,
                detail="Reddit API credentials not configured"
            )
        
        reddit_indexer = RedditLiveIndexer(
            reddit_client_id=reddit_client_id,
            reddit_client_secret=reddit_client_secret,
            chroma_host=os.getenv("CHROMA_HOST", "localhost"),
            chroma_port=int(os.getenv("CHROMA_PORT", "8000"))
        )
        
        reddit_indexer.connect_chroma()
        reddit_indexer.init_sentiment_analyzer()
        reddit_indexer.connect_reddit()
    
    try:
        indexed = reddit_indexer.sync_once()
        return {
            "status": "synced",
            "indexed_count": indexed,
            "stats": reddit_indexer.get_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reddit/stats")
async def get_reddit_stats():
    """Get Reddit indexer statistics"""
    if not reddit_indexer:
        return {"status": "not_initialized", "stats": None}
    
    return {"status": "ok", "stats": reddit_indexer.get_stats()}


@app.get("/stats")
async def get_system_stats():
    """Get overall system statistics"""
    stats = {
        "rag_service": "initialized" if rag_service else "not_initialized",
        "chroma_connected": rag_service.check_chroma_connection() if rag_service else False,
        "ollama_connected": rag_service.check_ollama_connection() if rag_service else False,
        "collection_count": rag_service.collection.count() if rag_service else 0,
        "reddit_indexer": reddit_indexer.get_stats() if reddit_indexer else None
    }
    return stats


@app.get("/documents/browse")
async def browse_documents(
    limit: int = 20,
    offset: int = 0,
    source: Optional[str] = None,
    subreddit: Optional[str] = None
):
    """Browse indexed documents from ChromaDB"""
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    try:
        # Build where filter
        where_filter = None
        if source:
            where_filter = {"source": source}
        elif subreddit:
            where_filter = {"subreddit": subreddit}
        
        # Get documents from collection
        results = rag_service.collection.get(
            limit=limit,
            offset=offset,
            where=where_filter,
            include=["documents", "metadatas"]
        )
        
        documents = []
        if results and results.get("ids"):
            for i, doc_id in enumerate(results["ids"]):
                doc = {
                    "id": doc_id,
                    "text": results["documents"][i][:500] + "..." if len(results["documents"][i]) > 500 else results["documents"][i],
                    "metadata": results["metadatas"][i] if results["metadatas"] else {}
                }
                documents.append(doc)
        
        return {
            "total": rag_service.collection.count(),
            "returned": len(documents),
            "offset": offset,
            "limit": limit,
            "documents": documents
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/search")
async def search_documents(
    query: str,
    limit: int = 10,
    subreddit: Optional[str] = None
):
    """Search indexed documents by semantic similarity"""
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    try:
        where_filter = {"subreddit": subreddit} if subreddit else None
        
        results = rag_service.collection.query(
            query_texts=[query],
            n_results=limit,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        documents = []
        if results and results.get("ids") and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                doc = {
                    "id": doc_id,
                    "text": results["documents"][0][i][:500] + "..." if len(results["documents"][0][i]) > 500 else results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "similarity": 1 - results["distances"][0][i] if results["distances"] else None
                }
                documents.append(doc)
        
        return {
            "query": query,
            "results": documents
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import multiprocessing
    multiprocessing.freeze_support()  # Windows fix
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8081,  # Changed from 8080 (used by Spark Master)
        reload=False  # Disable reload on Windows to avoid multiprocessing issues
    )
