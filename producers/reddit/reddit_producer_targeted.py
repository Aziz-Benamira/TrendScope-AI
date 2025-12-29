"""
Reddit Producer - Targeted Search
Consumes movie triggers from TMDB producer and performs targeted Reddit searches
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

logger = colorlog.getLogger('RedditTargetedSearch')
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class RedditTargetedProducer:
    """Performs targeted Reddit searches based on TMDB movie triggers"""
    
    def __init__(self):
        self.client_id = os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = os.getenv('REDDIT_USER_AGENT', 'TrendScope-AI/1.0')
        
        if not all([self.client_id, self.client_secret]):
            raise ValueError("Reddit API credentials are required")
        
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.trigger_topic = 'reddit_search_trigger'  # Input topic from TMDB producer
        self.output_topic = os.getenv('KAFKA_TOPIC', 'reddit_stream')  # Output topic
        self.subreddit_name = 'movies'
        
        self.reddit = None
        self.producer = None
        self.consumer = None
        
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
            # Test connection
            self.reddit.user.me()
            logger.info("✓ Connected to Reddit API")
        except Exception as e:
            logger.error(f"Failed to connect to Reddit: {e}")
            # Continue without authentication (read-only)
            try:
                self.reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    user_agent=self.user_agent
                )
                logger.info("✓ Connected to Reddit API (read-only)")
            except Exception as e2:
                logger.error(f"Failed to connect to Reddit in read-only mode: {e2}")
                raise
    
    def _connect_kafka(self):
        """Initialize Kafka producer and consumer"""
        max_retries = 5
        retry_count = 0
        
        # Connect producer
        while retry_count < max_retries:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.kafka_servers.split(','),
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    acks='all',
                    retries=3,
                    max_in_flight_requests_per_connection=1
                )
                logger.info(f"✓ Kafka producer connected to {self.kafka_servers}")
                break
            except KafkaError as e:
                retry_count += 1
                logger.warning(f"Failed to connect producer (attempt {retry_count}/{max_retries}): {e}")
                time.sleep(5)
        
        if retry_count >= max_retries:
            raise Exception("Could not connect Kafka producer after maximum retries")
        
        # Connect consumer
        retry_count = 0
        while retry_count < max_retries:
            try:
                self.consumer = KafkaConsumer(
                    self.trigger_topic,
                    bootstrap_servers=self.kafka_servers.split(','),
                    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                    auto_offset_reset='latest',  # Only process new triggers
                    enable_auto_commit=True,
                    group_id='reddit-targeted-search-group'
                )
                logger.info(f"✓ Kafka consumer subscribed to '{self.trigger_topic}'")
                return
            except KafkaError as e:
                retry_count += 1
                logger.warning(f"Failed to connect consumer (attempt {retry_count}/{max_retries}): {e}")
                time.sleep(5)
        
        raise Exception("Could not connect Kafka consumer after maximum retries")
    
    def search_reddit(self, query, limit=20):
        """Search Reddit for specific movie discussion"""
        try:
            subreddit = self.reddit.subreddit(self.subreddit_name)
            
            # Search using Reddit's search API
            results = []
            search_results = subreddit.search(query, limit=limit, sort='relevance', time_filter='month')
            
            for submission in search_results:
                results.append({
                    'type': 'post',
                    'post_id': submission.id,
                    'title': submission.title,
                    'text': submission.selftext,
                    'author': str(submission.author) if submission.author else '[deleted]',
                    'score': submission.score,
                    'num_comments': submission.num_comments,
                    'upvote_ratio': submission.upvote_ratio,
                    'created_utc': datetime.fromtimestamp(submission.created_utc).isoformat(),
                    'url': submission.url,
                    'permalink': f"https://reddit.com{submission.permalink}"
                })
                
                # Also get top comments from each post
                try:
                    submission.comments.replace_more(limit=0)  # Don't load "more comments"
                    for comment in submission.comments[:5]:  # Top 5 comments
                        if hasattr(comment, 'body'):
                            results.append({
                                'type': 'comment',
                                'comment_id': comment.id,
                                'post_id': submission.id,
                                'post_title': submission.title,
                                'text': comment.body,
                                'author': str(comment.author) if comment.author else '[deleted]',
                                'score': comment.score,
                                'created_utc': datetime.fromtimestamp(comment.created_utc).isoformat(),
                                'permalink': f"https://reddit.com{comment.permalink}"
                            })
                except Exception as e:
                    logger.debug(f"Could not fetch comments: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Reddit for '{query}': {e}")
            return []
    
    def transform_reddit_data(self, item, movie_info):
        """Transform Reddit search result into Kafka message"""
        return {
            # Movie context
            'movie_id': movie_info.get('movie_id'),
            'movie_title': movie_info.get('title'),
            'movie_year': movie_info.get('year'),
            'search_query': movie_info.get('search_query'),
            
            # Reddit data
            'type': item.get('type'),
            'id': item.get('post_id') if item.get('type') == 'post' else item.get('comment_id'),
            'post_id': item.get('post_id'),
            'post_title': item.get('post_title', item.get('title')),
            'text': item.get('text'),
            'author': item.get('author'),
            'score': item.get('score'),
            'created_utc': item.get('created_utc'),
            'url': item.get('url'),
            'permalink': item.get('permalink'),
            
            # Metadata
            'subreddit': self.subreddit_name,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'reddit_targeted'
        }
    
    def publish_to_kafka(self, data):
        """Publish data to Kafka topic"""
        try:
            future = self.producer.send(self.output_topic, value=data)
            future.get(timeout=10)
            return True
        except KafkaError as e:
            logger.error(f"Failed to publish to Kafka: {e}")
            return False
    
    def process_trigger(self, trigger):
        """Process a movie search trigger from TMDB producer"""
        movie_title = trigger.get('title', 'Unknown')
        queries = trigger.get('queries', [])
        
        logger.info(f"\n[TRIGGER] Processing: {movie_title}")
        logger.info(f"  Queries: {len(queries)}")
        
        all_results = []
        published_count = 0
        
        # Try each search query (primary, with cast, with director)
        for idx, query in enumerate(queries, 1):
            logger.info(f"  [{idx}/{len(queries)}] Searching: \"{query}\"")
            
            # Search Reddit
            results = self.search_reddit(query, limit=10)
            
            if results:
                logger.info(f"    ✓ Found {len(results)} results")
                
                # Publish each result to Kafka
                for result in results:
                    movie_info = {
                        'movie_id': trigger.get('movie_id'),
                        'title': movie_title,
                        'year': trigger.get('year'),
                        'search_query': query
                    }
                    
                    transformed = self.transform_reddit_data(result, movie_info)
                    if self.publish_to_kafka(transformed):
                        published_count += 1
                
                all_results.extend(results)
                
                # Stop if we found good results
                if len(results) >= 5:
                    break
            else:
                logger.info(f"    ✗ No results")
            
            # Rate limiting
            time.sleep(2)
        
        logger.info(f"  ✓ Published {published_count} Reddit posts/comments for '{movie_title}'")
        return published_count
    
    def run(self):
        """Main consumer loop - listen for movie triggers"""
        logger.info("=" * 60)
        logger.info("Reddit Targeted Search Producer")
        logger.info(f"Listening for movie triggers on: {self.trigger_topic}")
        logger.info(f"Publishing Reddit data to: {self.output_topic}")
        logger.info("=" * 60)
        
        processed_count = 0
        
        try:
            for message in self.consumer:
                try:
                    trigger = message.value
                    
                    # Process the trigger
                    published = self.process_trigger(trigger)
                    
                    if published > 0:
                        processed_count += 1
                        logger.info(f"\n[STATS] Processed {processed_count} movies, published {published} items")
                    
                except Exception as e:
                    logger.error(f"Error processing trigger: {e}", exc_info=True)
                    
        except KeyboardInterrupt:
            logger.info("\nShutting down...")
        finally:
            self.close()
    
    def close(self):
        """Cleanup resources"""
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.flush()
            self.producer.close()
        logger.info("✓ Reddit producer closed")


if __name__ == "__main__":
    producer = RedditTargetedProducer()
    try:
        producer.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        producer.close()
