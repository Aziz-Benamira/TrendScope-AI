"""
Cassandra to ChromaDB Sync Service
Reads movie trends and Reddit data from Cassandra and indexes to ChromaDB for RAG
"""
import os
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('CassandraSync')

# Try to import cassandra driver
try:
    from cassandra.cluster import Cluster
    from cassandra.auth import PlainTextAuthProvider
    CASSANDRA_AVAILABLE = True
except ImportError:
    CASSANDRA_AVAILABLE = False
    logger.warning("Cassandra driver not installed. Install with: pip install cassandra-driver")


class CassandraChromaSync:
    """Syncs data from Cassandra to ChromaDB for RAG queries"""
    
    def __init__(
        self,
        cassandra_host: str = "localhost",
        cassandra_port: int = 9042,
        cassandra_keyspace: str = "trendscope",
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        collection_name: str = "movie_reviews",
        sync_interval: int = 60  # seconds
    ):
        self.cassandra_host = cassandra_host
        self.cassandra_port = cassandra_port
        self.cassandra_keyspace = cassandra_keyspace
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self.collection_name = collection_name
        self.sync_interval = sync_interval
        
        self.cassandra_session = None
        self.chroma_client = None
        self.collection = None
        self.embedding_function = DefaultEmbeddingFunction()
        
        self._running = False
        self._sync_thread = None
        self._last_sync_time = None
        
    def connect_cassandra(self) -> bool:
        """Connect to Cassandra cluster"""
        if not CASSANDRA_AVAILABLE:
            logger.error("Cassandra driver not available")
            return False
            
        try:
            cluster = Cluster(
                [self.cassandra_host],
                port=self.cassandra_port
            )
            self.cassandra_session = cluster.connect(self.cassandra_keyspace)
            logger.info(f"✅ Connected to Cassandra at {self.cassandra_host}:{self.cassandra_port}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Cassandra: {e}")
            return False
    
    def connect_chroma(self) -> bool:
        """Connect to ChromaDB"""
        try:
            self.chroma_client = chromadb.HttpClient(
                host=self.chroma_host,
                port=self.chroma_port
            )
            # Get or create collection
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"description": "Movie reviews and trends from Reddit/TMDB"}
            )
            logger.info(f"✅ Connected to ChromaDB at {self.chroma_host}:{self.chroma_port}")
            logger.info(f"   Collection '{self.collection_name}' has {self.collection.count()} documents")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to ChromaDB: {e}")
            return False
    
    def fetch_movie_trends(self, since: Optional[datetime] = None) -> List[Dict]:
        """Fetch movie trends from Cassandra"""
        if not self.cassandra_session:
            return []
        
        try:
            # Query movie_trends table
            if since:
                query = """
                    SELECT movie_title, window_start, window_end, movie_id, 
                           popularity, vote_average, mentions_count, 
                           avg_sentiment, trend_score, processed_time
                    FROM movie_trends
                    WHERE processed_time > %s
                    ALLOW FILTERING
                """
                rows = self.cassandra_session.execute(query, [since])
            else:
                query = """
                    SELECT movie_title, window_start, window_end, movie_id,
                           popularity, vote_average, mentions_count,
                           avg_sentiment, trend_score, processed_time
                    FROM movie_trends
                    LIMIT 1000
                """
                rows = self.cassandra_session.execute(query)
            
            trends = []
            for row in rows:
                trends.append({
                    'movie_title': row.movie_title,
                    'movie_id': row.movie_id,
                    'popularity': row.popularity,
                    'vote_average': row.vote_average,
                    'mentions_count': row.mentions_count,
                    'avg_sentiment': row.avg_sentiment,
                    'trend_score': row.trend_score,
                    'processed_time': row.processed_time,
                    'window_start': row.window_start,
                    'window_end': row.window_end
                })
            
            logger.info(f"Fetched {len(trends)} movie trends from Cassandra")
            return trends
            
        except Exception as e:
            logger.error(f"Error fetching movie trends: {e}")
            return []
    
    def fetch_reddit_posts(self, since: Optional[datetime] = None) -> List[Dict]:
        """Fetch Reddit posts/comments from Cassandra (if stored)"""
        # Note: The current schema stores aggregated trends, not raw posts
        # This can be extended if raw Reddit data is stored
        return []
    
    def create_document_text(self, trend: Dict) -> str:
        """Create a searchable text document from trend data"""
        sentiment_label = "positive" if trend.get('avg_sentiment', 0) > 0.2 else \
                         "negative" if trend.get('avg_sentiment', 0) < -0.2 else "mixed"
        
        text = f"""
Movie: {trend['movie_title']}
Trend Score: {trend.get('trend_score', 0):.2f}
Popularity: {trend.get('popularity', 0):.1f}
Rating: {trend.get('vote_average', 0):.1f}/10
Mentions: {trend.get('mentions_count', 0)} times on Reddit
Sentiment: {sentiment_label} (score: {trend.get('avg_sentiment', 0):.2f})
This movie is {'trending' if trend.get('trend_score', 0) > 50 else 'moderately discussed' if trend.get('trend_score', 0) > 20 else 'not trending much'} on social media.
        """.strip()
        
        return text
    
    def index_trends_to_chroma(self, trends: List[Dict]) -> int:
        """Index movie trends to ChromaDB"""
        if not self.collection or not trends:
            return 0
        
        indexed_count = 0
        
        for trend in trends:
            try:
                doc_id = f"trend_{trend['movie_title']}_{trend.get('processed_time', datetime.now()).isoformat()}"
                doc_id = doc_id.replace(" ", "_").replace(":", "-")[:63]  # ChromaDB ID limit
                
                document_text = self.create_document_text(trend)
                
                metadata = {
                    "movie_title": trend['movie_title'],
                    "movie_id": str(trend.get('movie_id', '')),
                    "trend_score": float(trend.get('trend_score', 0)),
                    "popularity": float(trend.get('popularity', 0)),
                    "vote_average": float(trend.get('vote_average', 0)),
                    "mentions_count": int(trend.get('mentions_count', 0)),
                    "avg_sentiment": float(trend.get('avg_sentiment', 0)),
                    "source": "cassandra_sync",
                    "indexed_at": datetime.now().isoformat()
                }
                
                # Upsert to ChromaDB
                self.collection.upsert(
                    ids=[doc_id],
                    documents=[document_text],
                    metadatas=[metadata]
                )
                indexed_count += 1
                
            except Exception as e:
                logger.error(f"Error indexing trend for {trend.get('movie_title')}: {e}")
        
        logger.info(f"✅ Indexed {indexed_count} trends to ChromaDB")
        return indexed_count
    
    def sync_once(self) -> int:
        """Perform a single sync from Cassandra to ChromaDB"""
        logger.info("Starting sync from Cassandra to ChromaDB...")
        
        # Fetch new trends since last sync
        trends = self.fetch_movie_trends(since=self._last_sync_time)
        
        if trends:
            indexed = self.index_trends_to_chroma(trends)
            self._last_sync_time = datetime.now()
            return indexed
        else:
            logger.info("No new trends to sync")
            return 0
    
    def start_continuous_sync(self):
        """Start continuous sync in background thread"""
        if self._running:
            logger.warning("Sync is already running")
            return
        
        self._running = True
        
        def sync_loop():
            while self._running:
                try:
                    self.sync_once()
                except Exception as e:
                    logger.error(f"Sync error: {e}")
                
                time.sleep(self.sync_interval)
        
        self._sync_thread = threading.Thread(target=sync_loop, daemon=True)
        self._sync_thread.start()
        logger.info(f"Started continuous sync (interval: {self.sync_interval}s)")
    
    def stop_sync(self):
        """Stop continuous sync"""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
        logger.info("Stopped continuous sync")
    
    def get_stats(self) -> Dict:
        """Get sync statistics"""
        return {
            "cassandra_connected": self.cassandra_session is not None,
            "chroma_connected": self.collection is not None,
            "collection_count": self.collection.count() if self.collection else 0,
            "last_sync": self._last_sync_time.isoformat() if self._last_sync_time else None,
            "sync_running": self._running
        }


def main():
    """Main entry point for standalone sync service"""
    sync = CassandraChromaSync(
        cassandra_host=os.getenv('CASSANDRA_HOST', 'localhost'),
        cassandra_port=int(os.getenv('CASSANDRA_PORT', 9042)),
        cassandra_keyspace=os.getenv('CASSANDRA_KEYSPACE', 'trendscope'),
        chroma_host=os.getenv('CHROMA_HOST', 'localhost'),
        chroma_port=int(os.getenv('CHROMA_PORT', 8000)),
        sync_interval=int(os.getenv('SYNC_INTERVAL', 60))
    )
    
    # Connect to services
    if not sync.connect_chroma():
        logger.error("Could not connect to ChromaDB. Exiting.")
        return
    
    if sync.connect_cassandra():
        # Start continuous sync
        sync.start_continuous_sync()
        
        try:
            while True:
                time.sleep(10)
                stats = sync.get_stats()
                logger.info(f"Sync stats: {stats}")
        except KeyboardInterrupt:
            sync.stop_sync()
    else:
        logger.warning("Running without Cassandra - using sample data only")


if __name__ == "__main__":
    main()
