"""
Reddit Live Indexer
Fetches Reddit posts/comments about movies and indexes them directly to ChromaDB
"""
import os
import time
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('RedditIndexer')

# Try to import PRAW (Reddit API)
try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("PRAW not installed. Install with: pip install praw")

# Try to import VADER for sentiment
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False
    logger.warning("VADER not installed. Install with: pip install vaderSentiment")


class RedditLiveIndexer:
    """
    Fetches Reddit posts about movies and indexes them to ChromaDB for RAG
    """
    
    def __init__(
        self,
        reddit_client_id: str,
        reddit_client_secret: str,
        reddit_user_agent: str = "TrendScope-AI/1.0",
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        collection_name: str = "movie_reviews",
        subreddits: List[str] = None
    ):
        self.reddit_client_id = reddit_client_id
        self.reddit_client_secret = reddit_client_secret
        self.reddit_user_agent = reddit_user_agent
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self.collection_name = collection_name
        self.subreddits = subreddits or ["movies", "MovieSuggestions", "TrueFilm", "horror", "scifi"]
        
        self.reddit = None
        self.chroma_client = None
        self.collection = None
        self.sentiment_analyzer = None
        self.embedding_function = DefaultEmbeddingFunction()
        
        self._running = False
        self._indexed_ids = set()  # Track indexed post/comment IDs
        
    def connect_reddit(self) -> bool:
        """Connect to Reddit API"""
        if not PRAW_AVAILABLE:
            logger.error("PRAW not available")
            return False
        
        try:
            self.reddit = praw.Reddit(
                client_id=self.reddit_client_id,
                client_secret=self.reddit_client_secret,
                user_agent=self.reddit_user_agent
            )
            # Test connection
            self.reddit.user.me()  # Will be None for read-only
            logger.info("✅ Connected to Reddit API")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Reddit: {e}")
            return False
    
    def connect_chroma(self) -> bool:
        """Connect to ChromaDB"""
        try:
            self.chroma_client = chromadb.HttpClient(
                host=self.chroma_host,
                port=self.chroma_port
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"description": "Movie reviews and discussions from Reddit"}
            )
            logger.info(f"✅ Connected to ChromaDB. Collection has {self.collection.count()} documents")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to ChromaDB: {e}")
            return False
    
    def init_sentiment_analyzer(self):
        """Initialize VADER sentiment analyzer"""
        if VADER_AVAILABLE:
            self.sentiment_analyzer = SentimentIntensityAnalyzer()
            logger.info("✅ Sentiment analyzer initialized")
    
    def analyze_sentiment(self, text: str) -> Dict:
        """Analyze sentiment of text"""
        if not self.sentiment_analyzer:
            return {"compound": 0.0, "label": "neutral"}
        
        scores = self.sentiment_analyzer.polarity_scores(text)
        compound = scores["compound"]
        
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        
        return {"compound": compound, "label": label}
    
    def extract_movie_mentions(self, text: str, title: str = "") -> List[str]:
        """Extract potential movie titles from text"""
        # Combine text and title
        full_text = f"{title} {text}"
        
        # Common movie-related patterns
        import re
        
        # Look for quoted titles
        quoted = re.findall(r'"([^"]+)"', full_text)
        quoted.extend(re.findall(r"'([^']+)'", full_text))
        
        # Look for common patterns like "Movie (Year)"
        year_pattern = re.findall(r'([A-Z][a-zA-Z\s:]+)\s*\((?:19|20)\d{2}\)', full_text)
        
        movies = list(set(quoted + year_pattern))
        
        # Filter out common false positives
        false_positives = ["I", "The", "A", "It", "This", "That", "My", "We", "They", "Just"]
        movies = [m.strip() for m in movies if m.strip() not in false_positives and len(m.strip()) > 2]
        
        return movies[:5]  # Limit to 5 mentions
    
    def generate_doc_id(self, item_id: str, source: str) -> str:
        """Generate a unique document ID"""
        content = f"{source}:{item_id}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def should_index(self, text: str, author: str = "") -> bool:
        """Determine if a post/comment should be indexed"""
        # Minimum length
        if len(text) < 100:
            return False
        
        # Skip deleted/removed
        if text in ["[deleted]", "[removed]"]:
            return False
        
        # Skip bots
        bot_keywords = ["bot", "automoderator", "auto_mod"]
        if any(kw in author.lower() for kw in bot_keywords):
            return False
        
        # Must mention movies or be movie-related
        movie_keywords = ["movie", "film", "watch", "scene", "actor", "director", 
                         "ending", "plot", "character", "recommend", "underrated",
                         "overrated", "horror", "comedy", "drama", "thriller"]
        text_lower = text.lower()
        if not any(kw in text_lower for kw in movie_keywords):
            return False
        
        return True
    
    def create_document(self, item: Dict) -> Dict:
        """Create a document for ChromaDB from Reddit item"""
        text = item.get("text", "")
        title = item.get("title", "")
        
        # Analyze sentiment
        sentiment = self.analyze_sentiment(text)
        
        # Extract movie mentions
        movies = self.extract_movie_mentions(text, title)
        movie_str = ", ".join(movies) if movies else "general discussion"
        
        # Create searchable document text
        doc_text = f"""
Reddit Discussion: {title}

{text}

Movies mentioned: {movie_str}
Sentiment: {sentiment['label']}
Subreddit: r/{item.get('subreddit', 'movies')}
        """.strip()
        
        # Metadata
        metadata = {
            "source": "reddit",
            "subreddit": item.get("subreddit", "movies"),
            "author": item.get("author", "anonymous")[:50],
            "score": int(item.get("score", 0)),
            "type": item.get("type", "post"),
            "sentiment": sentiment["compound"],
            "sentiment_label": sentiment["label"],
            "movies_mentioned": movie_str[:200],
            "created_utc": item.get("created_utc", ""),
            "indexed_at": datetime.now().isoformat()
        }
        
        # Add movie_title if we found specific movies
        if movies:
            metadata["movie_title"] = movies[0]
        
        return {
            "id": self.generate_doc_id(item.get("id", str(time.time())), "reddit"),
            "document": doc_text,
            "metadata": metadata
        }
    
    def fetch_hot_posts(self, limit: int = 25) -> List[Dict]:
        """Fetch hot posts from configured subreddits"""
        if not self.reddit:
            return []
        
        posts = []
        
        for subreddit_name in self.subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                
                for post in subreddit.hot(limit=limit):
                    if post.id in self._indexed_ids:
                        continue
                    
                    # Get post content
                    text = post.selftext if post.selftext else post.title
                    
                    if not self.should_index(text, post.author.name if post.author else ""):
                        continue
                    
                    posts.append({
                        "id": post.id,
                        "title": post.title,
                        "text": text,
                        "author": post.author.name if post.author else "anonymous",
                        "score": post.score,
                        "subreddit": subreddit_name,
                        "type": "post",
                        "created_utc": datetime.fromtimestamp(post.created_utc).isoformat(),
                        "url": post.url
                    })
                    
            except Exception as e:
                logger.error(f"Error fetching from r/{subreddit_name}: {e}")
        
        logger.info(f"Fetched {len(posts)} posts from Reddit")
        return posts
    
    def fetch_new_comments(self, limit: int = 50) -> List[Dict]:
        """Fetch new comments from configured subreddits"""
        if not self.reddit:
            return []
        
        comments = []
        
        for subreddit_name in self.subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                
                for comment in subreddit.comments(limit=limit):
                    if comment.id in self._indexed_ids:
                        continue
                    
                    if not self.should_index(comment.body, comment.author.name if comment.author else ""):
                        continue
                    
                    comments.append({
                        "id": comment.id,
                        "title": "",
                        "text": comment.body,
                        "author": comment.author.name if comment.author else "anonymous",
                        "score": comment.score,
                        "subreddit": subreddit_name,
                        "type": "comment",
                        "created_utc": datetime.fromtimestamp(comment.created_utc).isoformat(),
                        "post_id": comment.link_id
                    })
                    
            except Exception as e:
                logger.error(f"Error fetching comments from r/{subreddit_name}: {e}")
        
        logger.info(f"Fetched {len(comments)} comments from Reddit")
        return comments
    
    def index_items(self, items: List[Dict]) -> int:
        """Index Reddit items to ChromaDB"""
        if not self.collection or not items:
            return 0
        
        indexed = 0
        
        for item in items:
            try:
                doc = self.create_document(item)
                
                self.collection.upsert(
                    ids=[doc["id"]],
                    documents=[doc["document"]],
                    metadatas=[doc["metadata"]]
                )
                
                self._indexed_ids.add(item["id"])
                indexed += 1
                
            except Exception as e:
                logger.error(f"Error indexing item {item.get('id')}: {e}")
        
        logger.info(f"✅ Indexed {indexed} items to ChromaDB")
        return indexed
    
    def sync_once(self) -> int:
        """Perform a single sync - fetch and index new Reddit content"""
        total_indexed = 0
        
        # Fetch and index posts
        posts = self.fetch_hot_posts(limit=25)
        total_indexed += self.index_items(posts)
        
        # Fetch and index comments
        comments = self.fetch_new_comments(limit=50)
        total_indexed += self.index_items(comments)
        
        return total_indexed
    
    def start_live_indexing(self, interval: int = 300):
        """Start continuous live indexing"""
        self._running = True
        logger.info(f"Starting live indexing (interval: {interval}s)")
        
        while self._running:
            try:
                indexed = self.sync_once()
                logger.info(f"Sync complete. Indexed {indexed} new items. Total in ChromaDB: {self.collection.count()}")
            except Exception as e:
                logger.error(f"Sync error: {e}")
            
            time.sleep(interval)
    
    def stop(self):
        """Stop live indexing"""
        self._running = False
        logger.info("Stopped live indexing")
    
    def get_stats(self) -> Dict:
        """Get indexer statistics"""
        return {
            "reddit_connected": self.reddit is not None,
            "chroma_connected": self.collection is not None,
            "collection_count": self.collection.count() if self.collection else 0,
            "indexed_this_session": len(self._indexed_ids),
            "subreddits": self.subreddits,
            "running": self._running
        }


def main():
    """Main entry point"""
    indexer = RedditLiveIndexer(
        reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
        reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        reddit_user_agent=os.getenv("REDDIT_USER_AGENT", "TrendScope-AI/1.0"),
        chroma_host=os.getenv("CHROMA_HOST", "localhost"),
        chroma_port=int(os.getenv("CHROMA_PORT", 8000)),
        subreddits=["movies", "MovieSuggestions", "TrueFilm", "horror", "scifi"]
    )
    
    # Connect to services
    if not indexer.connect_chroma():
        logger.error("Could not connect to ChromaDB")
        return
    
    indexer.init_sentiment_analyzer()
    
    if not indexer.connect_reddit():
        logger.error("Could not connect to Reddit. Check your API credentials.")
        return
    
    # Start live indexing
    try:
        indexer.start_live_indexing(interval=300)  # Every 5 minutes
    except KeyboardInterrupt:
        indexer.stop()


if __name__ == "__main__":
    main()
