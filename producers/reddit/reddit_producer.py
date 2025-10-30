"""
Reddit Producer - Streams comments/posts from r/movies and publishes to Kafka
"""
import os
import json
import time
import logging
import praw
from kafka import KafkaProducer
from kafka.errors import KafkaError
from datetime import datetime
import colorlog
import re

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
        self.subreddit_name = os.getenv('REDDIT_SUBREDDIT', 'movies')
        
        self.reddit = None
        self.producer = None
        
        self._connect_reddit()
        self._connect_kafka()
    
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
        
        return {
            'comment_id': comment.id,
            'post_id': comment.submission.id,
            'post_title': comment.submission.title,
            'text': text,
            'author': str(comment.author) if comment.author else '[deleted]',
            'score': comment.score,
            'created_utc': datetime.fromtimestamp(comment.created_utc).isoformat(),
            'movie_mentions': movie_mentions,
            'subreddit': self.subreddit_name,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'reddit'
        }
    
    def transform_post_data(self, post):
        """Transform Reddit post into required format"""
        text = f"{post.title} {post.selftext}"
        movie_mentions = self.extract_movie_mentions(text)
        
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
            'subreddit': self.subreddit_name,
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
    
    def run(self):
        """Main producer loop"""
        logger.info("Starting Reddit Producer")
        
        try:
            # Initial fetch of hot posts
            self.fetch_hot_posts()
            
            # Start streaming comments
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


if __name__ == "__main__":
    producer = RedditProducer()
    producer.run()
