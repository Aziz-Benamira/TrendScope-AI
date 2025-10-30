"""
TMDB Producer - Fetches trending movies from TMDB API and publishes to Kafka
"""
import os
import json
import time
import logging
import requests
from kafka import KafkaProducer
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

logger = colorlog.getLogger('TMDBProducer')
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class TMDBProducer:
    """Produces TMDB trending movie data to Kafka"""
    
    def __init__(self):
        self.api_key = os.getenv('TMDB_API_KEY')
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.topic = os.getenv('KAFKA_TOPIC', 'tmdb_stream')
        self.fetch_interval = int(os.getenv('FETCH_INTERVAL', 300))
        
        if not self.api_key:
            raise ValueError("TMDB_API_KEY environment variable is required")
        
        self.base_url = "https://api.themoviedb.org/3"
        self.producer = None
        self._connect_kafka()
    
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
    
    def fetch_trending_movies(self):
        """Fetch trending movies from TMDB API"""
        try:
            # Fetch trending movies (day)
            url = f"{self.base_url}/trending/movie/day"
            params = {'api_key': self.api_key}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            movies = data.get('results', [])
            logger.info(f"Fetched {len(movies)} trending movies")
            
            return movies
        except requests.RequestException as e:
            logger.error(f"Error fetching data from TMDB: {e}")
            return []
    
    def fetch_movie_details(self, movie_id):
        """Fetch detailed information for a specific movie"""
        try:
            url = f"{self.base_url}/movie/{movie_id}"
            params = {'api_key': self.api_key}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching movie details for ID {movie_id}: {e}")
            return None
    
    def transform_movie_data(self, movie):
        """Transform movie data into the required format"""
        return {
            'movie_id': movie.get('id'),
            'title': movie.get('title'),
            'original_title': movie.get('original_title'),
            'popularity': movie.get('popularity', 0),
            'vote_average': movie.get('vote_average', 0),
            'vote_count': movie.get('vote_count', 0),
            'release_date': movie.get('release_date', ''),
            'genre_ids': movie.get('genre_ids', []),
            'overview': movie.get('overview', ''),
            'adult': movie.get('adult', False),
            'original_language': movie.get('original_language', ''),
            'poster_path': movie.get('poster_path', ''),
            'backdrop_path': movie.get('backdrop_path', ''),
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'tmdb'
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
    
    def run(self):
        """Main producer loop"""
        logger.info(f"Starting TMDB Producer - fetching every {self.fetch_interval} seconds")
        
        while True:
            try:
                # Fetch trending movies
                movies = self.fetch_trending_movies()
                
                # Transform and publish each movie
                published_count = 0
                for movie in movies:
                    transformed_data = self.transform_movie_data(movie)
                    if self.publish_to_kafka(transformed_data):
                        published_count += 1
                
                logger.info(f"Successfully published {published_count}/{len(movies)} movies to Kafka topic '{self.topic}'")
                
                # Wait before next fetch
                time.sleep(self.fetch_interval)
                
            except KeyboardInterrupt:
                logger.info("Shutting down TMDB Producer...")
                break
            except Exception as e:
                logger.error(f"Unexpected error in producer loop: {e}")
                time.sleep(30)
        
        # Cleanup
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("Kafka producer closed")


if __name__ == "__main__":
    producer = TMDBProducer()
    producer.run()
