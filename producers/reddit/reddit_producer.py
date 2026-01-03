"""
Reddit Producer - Streams comments/posts from r/movies and publishes to Kafka
Enhanced with targeted search for TMDB trending movies
"""
import os
import json
import time
import logging
import praw
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
from datetime import datetime
import colorlog
import re
from threading import Thread

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

logger = colorlog.getLogger('RedditProducer')
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class RedditProducer:
    """Produces Reddit movie discussion data to Kafka"""
    
    def __init__(self):
        self.client_id = os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = os.getenv('REDDIT_USER_AGENT', 'TrendScope-AI/1.0')
        
        if not all([self.client_id, self.client_secret]):
            raise ValueError("Reddit API credentials are required")
        
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.topic = os.getenv('KAFKA_TOPIC', 'reddit_stream')
        # Support multiple subreddits - includes popular show subreddits
        self.subreddit_name = os.getenv('REDDIT_SUBREDDIT', 'movies+television+StrangerThings+netflix+MarvelStudios+DC_Cinematic')
        
        self.reddit = None
        self.producer = None
        self.tmdb_consumer = None
        self.trending_movies = set()  # Cache of trending movie titles
        self.last_search_time = {}  # Track when we last searched for each movie
        
        self._connect_reddit()
        self._connect_kafka()
        self._connect_tmdb_consumer()
    
    def _connect_reddit(self):
        """Initialize Reddit API client"""
        try:
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            logger.info(f"Connected to Reddit API (read-only mode)")
        except Exception as e:
            logger.error(f"Failed to connect to Reddit: {e}")
            raise
    
    def _connect_kafka(self):
        """Initialize Kafka producer with retry logic"""
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.kafka_servers.split(','),
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    acks='all',
                    retries=3,
                    max_in_flight_requests_per_connection=1
                )
                logger.info(f"Connected to Kafka at {self.kafka_servers}")
                return
            except KafkaError as e:
                retry_count += 1
                logger.warning(f"Failed to connect to Kafka (attempt {retry_count}/{max_retries}): {e}")
                time.sleep(5)
        
        raise Exception("Could not connect to Kafka after maximum retries")
    
    def _connect_tmdb_consumer(self):
        """Initialize Kafka consumer to listen for TMDB trending movies"""
        try:
            self.tmdb_consumer = KafkaConsumer(
                'tmdb_stream',
                bootstrap_servers=self.kafka_servers.split(','),
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest',  # Read all messages from beginning
                enable_auto_commit=True,
                group_id='reddit_targeted_search_v2',  # Changed group to read from start
                consumer_timeout_ms=5000  # Longer timeout
            )
            logger.info("✓ Connected to TMDB stream for targeted search")
        except Exception as e:
            logger.warning(f"Could not connect to TMDB stream: {e}. Will skip targeted search.")
            self.tmdb_consumer = None
    
    def extract_movie_mentions(self, text):
        """Extract potential movie mentions from text"""
        # Simple heuristic: capitalize words that might be movie titles
        # This is a basic implementation - can be enhanced with NLP
        words = text.split()
        potential_movies = []
        
        # Look for capitalized phrases (potential movie titles)
        i = 0
        while i < len(words):
            if words[i] and words[i][0].isupper():
                title = words[i]
                j = i + 1
                # Collect consecutive capitalized words
                while j < len(words) and words[j] and words[j][0].isupper():
                    title += " " + words[j]
                    j += 1
                if len(title.split()) >= 1:  # At least one word
                    potential_movies.append(title.strip('.,!?;:'))
                i = j
            else:
                i += 1
        
        return potential_movies
    
    def transform_comment_data(self, comment):
        """Transform Reddit comment into required format"""
        text = comment.body
        movie_mentions = self.extract_movie_mentions(text)
        
        # Get the actual subreddit name from the comment, not the multi-reddit string
        actual_subreddit = str(comment.subreddit.display_name)
        
        return {
            'comment_id': comment.id,
            'post_id': comment.submission.id,
            'post_title': comment.submission.title,
            'text': text,
            'author': str(comment.author) if comment.author else '[deleted]',
            'score': comment.score,
            'created_utc': datetime.fromtimestamp(comment.created_utc).isoformat(),
            'movie_mentions': movie_mentions,
            'subreddit': actual_subreddit,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'reddit'
        }
    
    def transform_post_data(self, post):
        """Transform Reddit post into required format"""
        text = f"{post.title} {post.selftext}"
        movie_mentions = self.extract_movie_mentions(text)
        
        # Get the actual subreddit name from the post, not the multi-reddit string
        actual_subreddit = str(post.subreddit.display_name)
        
        return {
            'post_id': post.id,
            'title': post.title,
            'text': post.selftext,
            'author': str(post.author) if post.author else '[deleted]',
            'score': post.score,
            'num_comments': post.num_comments,
            'upvote_ratio': post.upvote_ratio,
            'created_utc': datetime.fromtimestamp(post.created_utc).isoformat(),
            'movie_mentions': movie_mentions,
            'subreddit': actual_subreddit,
            'url': post.url,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'reddit',
            'type': 'post'
        }
    
    def publish_to_kafka(self, data):
        """Publish data to Kafka topic"""
        try:
            future = self.producer.send(self.topic, value=data)
            record_metadata = future.get(timeout=10)
            
            logger.debug(f"Published to {record_metadata.topic} partition {record_metadata.partition} "
                        f"offset {record_metadata.offset}")
            return True
        except KafkaError as e:
            logger.error(f"Failed to publish to Kafka: {e}")
            return False
    
    def stream_comments(self):
        """Stream comments from subreddit"""
        try:
            subreddit = self.reddit.subreddit(self.subreddit_name)
            logger.info(f"Starting to stream comments from r/{self.subreddit_name}")
            
            # Stream comments in real-time
            for comment in subreddit.stream.comments(skip_existing=True):
                try:
                    transformed_data = self.transform_comment_data(comment)
                    
                    # Only publish if there are movie mentions or significant content
                    if transformed_data['movie_mentions'] or len(transformed_data['text']) > 50:
                        if self.publish_to_kafka(transformed_data):
                            logger.info(f"Published comment {comment.id} with {len(transformed_data['movie_mentions'])} movie mentions")
                
                except Exception as e:
                    logger.error(f"Error processing comment: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error in comment stream: {e}")
            raise
    
    def fetch_hot_posts(self):
        """Fetch hot posts from subreddit periodically"""
        try:
            subreddit = self.reddit.subreddit(self.subreddit_name)
            logger.info(f"Fetching hot posts from r/{self.subreddit_name}")
            
            published_count = 0
            for post in subreddit.hot(limit=25):
                try:
                    transformed_data = self.transform_post_data(post)
                    
                    if self.publish_to_kafka(transformed_data):
                        published_count += 1
                
                except Exception as e:
                    logger.error(f"Error processing post: {e}")
                    continue
            
            logger.info(f"Published {published_count} hot posts")
            
        except Exception as e:
            logger.error(f"Error fetching hot posts: {e}")
    
    def search_reddit_for_movie(self, movie_title):
        """Search Reddit for discussions about a specific movie"""
        try:
            # Don't search too frequently for the same movie
            if movie_title in self.last_search_time:
                time_since_last = time.time() - self.last_search_time[movie_title]
                if time_since_last < 600:  # 10 minutes cooldown
                    return
            
            self.last_search_time[movie_title] = time.time()
            
            logger.info(f"🔍 Searching Reddit for: {movie_title}")
            
            # Search across all subreddits
            subreddit = self.reddit.subreddit(self.subreddit_name)
            published_count = 0
            
            # Search posts
            for post in subreddit.search(movie_title, time_filter='week', limit=10):
                try:
                    transformed_data = self.transform_post_data(post)
                    # Mark as targeted search result
                    transformed_data['targeted_search'] = True
                    transformed_data['search_query'] = movie_title
                    
                    if self.publish_to_kafka(transformed_data):
                        published_count += 1
                        
                        # Also get top comments from the post
                        post.comment_limit = 10
                        post.comments.replace_more(limit=0)
                        for comment in post.comments[:10]:
                            try:
                                comment_data = self.transform_comment_data(comment)
                                comment_data['targeted_search'] = True
                                comment_data['search_query'] = movie_title
                                if self.publish_to_kafka(comment_data):
                                    published_count += 1
                            except:
                                continue
                                
                except Exception as e:
                    logger.debug(f"Error processing search result: {e}")
                    continue
            
            if published_count > 0:
                logger.info(f"✅ Found {published_count} Reddit discussions for '{movie_title}'")
            else:
                logger.warning(f"⚠️ No Reddit discussions found for '{movie_title}'")
                
        except Exception as e:
            logger.error(f"Error searching for movie {movie_title}: {e}")
    
    def monitor_tmdb_stream(self):
        """Monitor TMDB stream and search Reddit for new trending movies"""
        if not self.tmdb_consumer:
            logger.warning("TMDB consumer not available. Skipping targeted search.")
            return
        
        logger.info("🎬 Starting TMDB stream monitoring for targeted Reddit search")
        
        while True:
            try:
                # Poll for new TMDB movies (non-blocking)
                messages = self.tmdb_consumer.poll(timeout_ms=1000)
                
                for topic_partition, records in messages.items():
                    for record in records:
                        try:
                            movie_data = record.value
                            movie_title = movie_data.get('title', '').strip()
                            
                            if movie_title and movie_title not in self.trending_movies:
                                self.trending_movies.add(movie_title)
                                logger.info(f"🎯 New trending movie detected: {movie_title}")
                                
                                # Search Reddit for this movie
                                self.search_reddit_for_movie(movie_title)
                                
                        except Exception as e:
                            logger.error(f"Error processing TMDB message: {e}")
                            continue
                
                time.sleep(1)  # Small delay between polls
                
            except Exception as e:
                logger.error(f"Error in TMDB monitor loop: {e}")
                time.sleep(5)
    
    def periodic_targeted_search(self):
        """Periodically re-search for trending movies to keep data fresh"""
        logger.info("🔄 Starting periodic targeted search thread")
        
        while True:
            try:
                time.sleep(300)  # Every 5 minutes
                
                if self.trending_movies:
                    logger.info(f"🔍 Refreshing search for {len(self.trending_movies)} trending movies")
                    for movie_title in list(self.trending_movies):
                        self.search_reddit_for_movie(movie_title)
                        time.sleep(2)  # Rate limiting
                        
            except Exception as e:
                logger.error(f"Error in periodic search: {e}")
                time.sleep(60)
    
    def run(self):
        """Main producer loop with targeted search"""
        logger.info("🚀 Starting Enhanced Reddit Producer with Targeted Search")
        
        try:
            # Initial fetch of hot posts
            self.fetch_hot_posts()
            
            # Start TMDB monitoring thread
            if self.tmdb_consumer:
                tmdb_thread = Thread(target=self.monitor_tmdb_stream, daemon=True)
                tmdb_thread.start()
                logger.info("✓ TMDB monitoring thread started")
                
                # Start periodic search thread
                search_thread = Thread(target=self.periodic_targeted_search, daemon=True)
                search_thread.start()
                logger.info("✓ Periodic search thread started")
            
            # Start streaming comments from general subreddits
            logger.info("📡 Starting comment stream...")
            self.stream_comments()
            
        except KeyboardInterrupt:
            logger.info("Shutting down Reddit Producer...")
        except Exception as e:
            logger.error(f"Unexpected error in producer loop: {e}")
        finally:
            # Cleanup
            if self.producer:
                self.producer.flush()
                self.producer.close()
                logger.info("Kafka producer closed")
            if self.tmdb_consumer:
                self.tmdb_consumer.close()
                logger.info("TMDB consumer closed")


if __name__ == "__main__":
    producer = RedditProducer()
    producer.run()
