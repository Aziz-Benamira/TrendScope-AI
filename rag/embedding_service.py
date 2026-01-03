"""
Embedding Service - Consumes Reddit reviews from Kafka and stores embeddings in ChromaDB
"""
import os
import json
import logging
import time
from datetime import datetime
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from sentence_transformers import SentenceTransformer
import colorlog

# Support both relative and absolute imports
try:
    from .vector_store import VectorStore
    from .config import (
        KAFKA_BOOTSTRAP_SERVERS, 
        KAFKA_REDDIT_TOPIC,
        EMBEDDING_MODEL
    )
except ImportError:
    from vector_store import VectorStore
    from config import (
        KAFKA_BOOTSTRAP_SERVERS, 
        KAFKA_REDDIT_TOPIC,
        EMBEDDING_MODEL
    )

# Configure logging
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
))

logger = colorlog.getLogger('EmbeddingService')
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class EmbeddingService:
    """
    Kafka consumer that:
    1. Consumes Reddit review messages
    2. Generates embeddings using sentence-transformers
    3. Stores embeddings in ChromaDB for RAG retrieval
    """
    
    def __init__(self, skip_kafka=False):
        self.consumer = None
        self.vector_store = None
        self.embedding_model = None
        
        self._init_embedding_model()
        if not skip_kafka:
            self._init_kafka()
        self._init_vector_store()
        
        self.processed_count = 0
    
    def _init_embedding_model(self):
        """Initialize sentence-transformers model"""
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("✅ Embedding model loaded successfully")
    
    def _init_kafka(self, max_retries: int = 10):
        """Initialize Kafka consumer"""
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.consumer = KafkaConsumer(
                    KAFKA_REDDIT_TOPIC,
                    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(','),
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest',
                    enable_auto_commit=True,
                    group_id='embedding-service-group',
                    consumer_timeout_ms=1000  # 1 second timeout for polling
                )
                logger.info(f"✅ Connected to Kafka at {KAFKA_BOOTSTRAP_SERVERS}")
                logger.info(f"📡 Subscribed to topic: {KAFKA_REDDIT_TOPIC}")
                return
            except KafkaError as e:
                retry_count += 1
                logger.warning(f"Failed to connect to Kafka (attempt {retry_count}/{max_retries}): {e}")
                time.sleep(5)
        
        raise Exception("Could not connect to Kafka after maximum retries")
    
    def _init_vector_store(self):
        """Initialize ChromaDB vector store"""
        self.vector_store = VectorStore()
        logger.info("✅ Vector store initialized")
    
    def _extract_movie_title(self, message: dict) -> str:
        """Extract movie title from the message"""
        # If source is TMDB, movie_title is already provided
        if message.get('source') == 'tmdb':
            return message.get('movie_title', 'Unknown')
        
        # Map specific subreddits to show/movie names
        SUBREDDIT_TO_TITLE = {
            'strangerthings': 'Stranger Things',
            'netflix': 'Netflix',
            'marvelstudios': 'Marvel',
            'dc_cinematic': 'DC',
            'thelastofus': 'The Last of Us',
            'gameofthrones': 'Game of Thrones',
            'houseofthedragon': 'House of the Dragon',
            'wandavision': 'WandaVision',
            'themandalorian': 'The Mandalorian',
            'starwars': 'Star Wars',
        }
        
        # Use subreddit name first (if from a specific show subreddit)
        subreddit = message.get('subreddit', '').lower()
        if subreddit in SUBREDDIT_TO_TITLE:
            return SUBREDDIT_TO_TITLE[subreddit]
        
        # Try movie_mentions second - but filter garbage
        movie_mentions = message.get('movie_mentions', [])
        if movie_mentions:
            # Filter out common words that aren't movie titles
            common_words = {'I', 'A', 'The', 'It', 'This', 'That', 'What', 'Who', 'When', 'Where', 
                           'Why', 'How', 'My', 'Your', 'He', 'She', 'They', 'We', 'Is', 'Are',
                           'Was', 'Were', 'Been', 'Being', 'Have', 'Has', 'Had', 'Do', 'Does',
                           'Did', 'Will', 'Would', 'Could', 'Should', 'May', 'Might', 'Must',
                           'Original', 'Terrible', 'Great', 'Good', 'Bad', 'Best', 'Worst',
                           'First', 'Last', 'New', 'Old', 'People', 'Saw', 'Just', 'Really',
                           'Actually', 'Probably', 'Maybe', 'Definitely', 'Absolutely',
                           'OP', 'Commenters', 'Edit', 'Update', 'Spoilers', 'Spoiler',
                           'Discussion', 'Official', 'Thread', 'Post', 'Reddit', 'Sub',
                           'One', 'Two', 'Three', 'Realistically', 'Honestly', 'Seriously',
                           'Vampire:', 'Night', 'Netflix', 'Whatever', 'Slackers.', 'Super'}
            for mention in movie_mentions:
                # Skip if it's a common word, too short, or ends with special chars
                cleaned = mention.strip('.,!?;:"\'')
                if cleaned not in common_words and len(cleaned) > 3 and not cleaned.endswith(':'):
                    return cleaned
        
        # Fallback to general
        return "general"
    
    def _process_message(self, message: dict) -> bool:
        """Process a single message and store its embedding"""
        try:
            # Extract text content
            text = message.get('text', '')
            
            # Skip very short texts (less than 50 chars = not informative)
            if not text or len(text.strip()) < 50:
                return False
            
            # Skip AutoModerator and bot posts
            author = message.get('author', '')
            if author.lower() in ['automoderator', '[deleted]', 'bot', 'moderator']:
                return False
            
            # Skip posts that are just mod announcements
            if 'please make sure there are no spoilers' in text.lower():
                return False
            if 'this post has been removed' in text.lower():
                return False
            
            # Extract metadata
            review_id = message.get('comment_id') or message.get('post_id') or str(datetime.now().timestamp())
            movie_title = self._extract_movie_title(message)
            timestamp = message.get('timestamp', datetime.utcnow().isoformat())
            sentiment = message.get('sentiment_score', 0.0)
            source = message.get('source', 'reddit')
            subreddit = message.get('subreddit', '')
            score = message.get('score', 0)
            
            # Generate embedding
            embedding = self.embedding_model.encode(text).tolist()
            
            # Store in vector database
            success = self.vector_store.add_review(
                review_id=review_id,
                text=text,
                embedding=embedding,
                movie_title=movie_title,
                timestamp=timestamp,
                sentiment=sentiment,
                source=source,
                subreddit=subreddit,
                author=author,
                score=score
            )
            
            if success:
                self.processed_count += 1
                if self.processed_count % 10 == 0:
                    logger.info(f"📊 Processed {self.processed_count} reviews | Latest: {movie_title[:30]}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return False
    
    def run(self):
        """Main loop - consume messages and generate embeddings"""
        logger.info("🚀 Embedding Service started - consuming from Kafka...")
        
        try:
            while True:
                # Poll for messages (with timeout)
                try:
                    for message in self.consumer:
                        self._process_message(message.value)
                except StopIteration:
                    # No messages, continue polling
                    pass
                
                # Small sleep to prevent CPU spinning
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown signal received")
        finally:
            if self.consumer:
                self.consumer.close()
            logger.info(f"📈 Final stats: {self.processed_count} reviews processed")


def main():
    """Entry point"""
    service = EmbeddingService()
    service.run()


if __name__ == "__main__":
    main()
