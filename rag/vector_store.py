"""
Vector Store - ChromaDB wrapper for movie review embeddings
"""
import chromadb
from chromadb.config import Settings
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

# Support both relative and absolute imports
try:
    from .config import CHROMA_HOST, CHROMA_PORT, COLLECTION_NAME
except ImportError:
    from config import CHROMA_HOST, CHROMA_PORT, COLLECTION_NAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB wrapper for storing and retrieving movie review embeddings"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self._connect()
    
    def _connect(self, max_retries: int = 10):
        """Connect to ChromaDB with retry logic"""
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.client = chromadb.HttpClient(
                    host=CHROMA_HOST,
                    port=CHROMA_PORT,
                    settings=Settings(anonymized_telemetry=False)
                )
                
                # Get or create collection
                self.collection = self.client.get_or_create_collection(
                    name=COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"}
                )
                
                logger.info(f"✅ Connected to ChromaDB at {CHROMA_HOST}:{CHROMA_PORT}")
                logger.info(f"📚 Collection '{COLLECTION_NAME}' ready with {self.collection.count()} documents")
                return
                
            except Exception as e:
                retry_count += 1
                logger.warning(f"Failed to connect to ChromaDB (attempt {retry_count}/{max_retries}): {e}")
                time.sleep(5)
        
        raise Exception("Could not connect to ChromaDB after maximum retries")
    
    def add_review(self, 
                   review_id: str,
                   text: str, 
                   embedding: List[float],
                   movie_title: str,
                   timestamp: str,
                   sentiment: float = 0.0,
                   source: str = "reddit",
                   subreddit: str = "",
                   author: str = "",
                   score: int = 0) -> bool:
        """Add a review embedding to the collection"""
        try:
            self.collection.add(
                ids=[review_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[{
                    "movie_title": movie_title.lower(),  # Normalize for filtering
                    "movie_title_original": movie_title,  # Keep original case
                    "timestamp": timestamp,
                    "sentiment": sentiment,
                    "source": source,
                    "subreddit": subreddit,
                    "author": author,
                    "score": score
                }]
            )
            return True
        except Exception as e:
            # Handle duplicate IDs gracefully
            if "already exists" in str(e).lower():
                logger.debug(f"Review {review_id} already exists, skipping")
                return False
            logger.error(f"Error adding review: {e}")
            return False
    
    def search(self,
               query_embedding: List[float],
               movie_title: Optional[str] = None,
               n_results: int = 50,
               hours_back: int = 24) -> Dict:
        """
        Search for similar reviews
        
        Args:
            query_embedding: The embedded query vector
            movie_title: Optional filter by movie title (uses contains match)
            n_results: Number of results to return
            hours_back: Only return reviews from the last N hours
            
        Returns:
            Dict with documents, metadatas, and distances
        """
        try:
            # Build where filter - use $contains for partial matching
            where_filter = None
            if movie_title:
                # Use $contains for partial matching (e.g., "stranger things" matches "stranger things season 4")
                where_filter = {"movie_title": {"$contains": movie_title.lower()}}
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
            
            # Post-filter by time (ChromaDB doesn't support datetime filtering natively)
            filtered_results = self._filter_by_time(results, hours_back)
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
    
    def _filter_by_time(self, results: Dict, hours_back: int) -> Dict:
        """Filter results to only include reviews from the last N hours"""
        if not results['documents'] or not results['documents'][0]:
            return results
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        filtered_docs = []
        filtered_metas = []
        filtered_dists = []
        
        for doc, meta, dist in zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        ):
            try:
                review_time = datetime.fromisoformat(meta['timestamp'].replace('Z', '+00:00').replace('+00:00', ''))
                if review_time >= cutoff_time:
                    filtered_docs.append(doc)
                    filtered_metas.append(meta)
                    filtered_dists.append(dist)
            except (ValueError, KeyError):
                # If timestamp parsing fails, include the document
                filtered_docs.append(doc)
                filtered_metas.append(meta)
                filtered_dists.append(dist)
        
        return {
            "documents": [filtered_docs],
            "metadatas": [filtered_metas],
            "distances": [filtered_dists]
        }
    
    def get_stats(self) -> Dict:
        """Get collection statistics"""
        try:
            count = self.collection.count()
            return {
                "total_reviews": count,
                "collection_name": COLLECTION_NAME
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"total_reviews": 0, "collection_name": COLLECTION_NAME}
    
    def get_movies_list(self) -> List[str]:
        """Get list of all movies in the collection"""
        try:
            # Get all metadatas (limited approach for now)
            results = self.collection.get(
                limit=1000,
                include=["metadatas"]
            )
            
            movies = set()
            for meta in results.get('metadatas', []):
                if meta and 'movie_title_original' in meta:
                    movies.add(meta['movie_title_original'])
            
            return sorted(list(movies))
        except Exception as e:
            logger.error(f"Error getting movies list: {e}")
            return []
