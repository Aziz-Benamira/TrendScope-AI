"""
TrendScope-AI RAG Service
Retrieval-Augmented Generation for movie reviews using ChromaDB and Ollama
"""

import os
import httpx
import hashlib
from typing import Optional, List, Dict, Any
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions


class RAGService:
    """
    RAG Service for movie review question answering.
    Uses ChromaDB for vector storage and Ollama for LLM generation.
    """
    
    def __init__(
        self,
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        ollama_host: str = "localhost",
        ollama_port: int = 11434,
        tmdb_api_key: Optional[str] = None,
        collection_name: str = "movie_reviews"
    ):
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.tmdb_api_key = tmdb_api_key
        self.collection_name = collection_name
        
        # Initialize embedding function (uses ChromaDB's default)
        print("Loading embedding model...")
        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
        
        # Initialize ChromaDB client
        self.chroma_client = chromadb.HttpClient(
            host=chroma_host,
            port=chroma_port,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection with embedding function
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"description": "Movie reviews for RAG"}
        )
        
        print(f"✅ RAG Service initialized with {self.collection.count()} reviews in collection")
    
    def check_chroma_connection(self) -> bool:
        """Check if ChromaDB is accessible"""
        try:
            self.chroma_client.heartbeat()
            return True
        except Exception:
            return False
    
    def check_ollama_connection(self) -> bool:
        """Check if Ollama is accessible"""
        try:
            response = httpx.get(
                f"http://{self.ollama_host}:{self.ollama_port}/api/tags",
                timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def _generate_review_id(self, review: str, movie_title: str) -> str:
        """Generate a unique ID for a review"""
        content = f"{movie_title}:{review[:100]}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _filter_review(self, review: str, author: str = "") -> bool:
        """
        Filter out low-quality reviews.
        Returns True if review should be kept.
        """
        # Minimum length
        if len(review) < 50:
            return False
        
        # Filter bot accounts
        bot_indicators = ["bot", "auto", "moderator"]
        if any(ind in author.lower() for ind in bot_indicators):
            return False
        
        # Filter spoiler warnings (keep the review but it's marked)
        spoiler_keywords = ["spoiler", "spoilers ahead", "plot twist"]
        
        # Filter low-effort content
        low_effort = ["lol", "lmao", "same", "this", "^"]
        if review.strip().lower() in low_effort:
            return False
        
        return True
    
    async def add_review(
        self,
        review_text: str,
        movie_title: str,
        movie_id: Optional[int] = None,
        author: str = "",
        source: str = "tmdb",
        rating: Optional[float] = None
    ) -> bool:
        """Add a review to the vector store"""
        
        # Filter low-quality reviews
        if not self._filter_review(review_text, author):
            return False
        
        # Generate unique ID
        doc_id = self._generate_review_id(review_text, movie_title)
        
        # Prepare metadata
        metadata = {
            "movie_title": movie_title,
            "source": source,
            "author": author[:100] if author else "anonymous"
        }
        if movie_id:
            metadata["movie_id"] = movie_id
        if rating:
            metadata["rating"] = rating
        
        # Add to collection (ChromaDB generates embeddings automatically)
        try:
            self.collection.add(
                ids=[doc_id],
                documents=[review_text],
                metadatas=[metadata]
            )
            return True
        except Exception as e:
            # Duplicate ID - already exists
            if "already exists" in str(e).lower():
                return False
            raise
    
    async def search_similar_reviews(
        self,
        query: str,
        movie_title: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar reviews"""
        
        # Build where filter
        where_filter = None
        if movie_title:
            where_filter = {"movie_title": {"$eq": movie_title}}
        
        # Query collection (ChromaDB generates query embedding automatically)
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format results
        formatted = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                formatted.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None
                })
        
        return formatted
    
    async def _generate_with_ollama(self, prompt: str, model: str = "mistral") -> str:
        """Generate response using Ollama"""
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"http://{self.ollama_host}:{self.ollama_port}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9,
                            "num_predict": 500
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "No response generated")
                else:
                    error_text = response.text
                    print(f"Ollama error response: {error_text}")
                    raise Exception(f"Ollama error: {error_text}")
        except httpx.TimeoutException:
            raise Exception("Ollama request timed out. The model may be loading or processing is taking too long.")
        except httpx.ConnectError:
            raise Exception("Could not connect to Ollama. Make sure Ollama is running on port 11434.")
    
    async def _fetch_tmdb_reviews(self, movie_id: int) -> List[Dict]:
        """Fetch reviews from TMDB API"""
        if not self.tmdb_api_key:
            return []
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.themoviedb.org/3/movie/{movie_id}/reviews",
                params={"api_key": self.tmdb_api_key}
            )
            
            if response.status_code == 200:
                return response.json().get("results", [])
        
        return []
    
    async def _search_tmdb_movie(self, query: str) -> Optional[Dict]:
        """Search for a movie on TMDB"""
        if not self.tmdb_api_key:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.themoviedb.org/3/search/movie",
                params={
                    "api_key": self.tmdb_api_key,
                    "query": query
                }
            )
            
            if response.status_code == 200:
                results = response.json().get("results", [])
                if results:
                    return results[0]
        
        return None
    
    async def _get_tmdb_movie_details(self, movie_id: int) -> Optional[Dict]:
        """Get movie details from TMDB"""
        if not self.tmdb_api_key:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.themoviedb.org/3/movie/{movie_id}",
                params={"api_key": self.tmdb_api_key}
            )
            
            if response.status_code == 200:
                return response.json()
        
        return None
    
    async def index_movie_reviews(self, movie_id: int) -> Dict[str, Any]:
        """Index reviews for a movie from TMDB"""
        
        # Get movie details
        movie_details = await self._get_tmdb_movie_details(movie_id)
        if not movie_details:
            return {"success": False, "error": "Movie not found"}
        
        movie_title = movie_details.get("title", "Unknown")
        
        # Fetch reviews
        reviews = await self._fetch_tmdb_reviews(movie_id)
        
        indexed = 0
        for review in reviews:
            success = await self.add_review(
                review_text=review.get("content", ""),
                movie_title=movie_title,
                movie_id=movie_id,
                author=review.get("author", ""),
                source="tmdb",
                rating=review.get("author_details", {}).get("rating")
            )
            if success:
                indexed += 1
        
        return {
            "success": True,
            "movie_title": movie_title,
            "reviews_found": len(reviews),
            "reviews_indexed": indexed
        }
    
    async def search_movies(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for movies using TMDB"""
        if not self.tmdb_api_key:
            return []
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.themoviedb.org/3/search/movie",
                params={
                    "api_key": self.tmdb_api_key,
                    "query": query
                }
            )
            
            if response.status_code == 200:
                results = response.json().get("results", [])[:limit]
                return [
                    {
                        "id": m["id"],
                        "title": m["title"],
                        "year": m.get("release_date", "")[:4],
                        "overview": m.get("overview", "")[:200],
                        "poster_path": m.get("poster_path")
                    }
                    for m in results
                ]
        
        return []
    
    async def query(
        self,
        question: str,
        movie_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main RAG query method.
        Retrieves relevant reviews and generates an answer.
        """
        
        movie_info = None
        
        # If movie title provided, try to find it and index reviews
        if movie_title:
            movie = await self._search_tmdb_movie(movie_title)
            if movie:
                movie_info = {
                    "id": movie["id"],
                    "title": movie["title"],
                    "year": movie.get("release_date", "")[:4],
                    "overview": movie.get("overview", "")
                }
                # Auto-index reviews if we don't have many
                await self.index_movie_reviews(movie["id"])
        
        # Search for relevant reviews
        search_query = f"{movie_title} {question}" if movie_title else question
        similar_reviews = await self.search_similar_reviews(
            query=search_query,
            movie_title=movie_title,
            n_results=5
        )
        
        # If no reviews found, try TMDB fallback
        if not similar_reviews and movie_info:
            # Index more aggressively
            await self.index_movie_reviews(movie_info["id"])
            similar_reviews = await self.search_similar_reviews(
                query=search_query,
                movie_title=movie_title,
                n_results=5
            )
        
        # Build context from reviews
        if similar_reviews:
            context_parts = []
            for i, review in enumerate(similar_reviews, 1):
                source = review["metadata"].get("source", "unknown")
                author = review["metadata"].get("author", "anonymous")
                rating = review["metadata"].get("rating", "N/A")
                context_parts.append(
                    f"Review {i} (by {author}, rating: {rating}, source: {source}):\n{review['text'][:500]}"
                )
            context = "\n\n".join(context_parts)
        else:
            context = "No reviews found for this movie."
        
        # Build prompt
        prompt = f"""You are a helpful movie review assistant. Based on the following movie reviews, answer the user's question.
Be concise and helpful. If the reviews don't contain enough information, say so.

Movie: {movie_title or 'Not specified'}

Reviews:
{context}

User Question: {question}

Answer:"""
        
        # Generate response
        try:
            answer = await self._generate_with_ollama(prompt)
        except Exception as e:
            answer = f"I found {len(similar_reviews)} relevant reviews but couldn't generate a response. Error: {str(e)}"
        
        # Format sources
        sources = [
            {
                "text": r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"],
                "author": r["metadata"].get("author", "anonymous"),
                "source": r["metadata"].get("source", "unknown"),
                "rating": r["metadata"].get("rating")
            }
            for r in similar_reviews
        ]
        
        return {
            "answer": answer,
            "sources": sources,
            "movie_info": movie_info
        }
