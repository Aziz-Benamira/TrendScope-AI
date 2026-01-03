"""
TMDB Producer with IMDb Enrichment
Fetches trending movies from TMDB, enriches with IMDb data, and triggers targeted Reddit searches
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
import sys
import re
from bs4 import BeautifulSoup
sys.path.append('/app')
from data_loader.imdb_loader import IMDbDatasetLoader

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


class TMDBProducerEnriched:
    """Produces TMDB trending movie data enriched with IMDb to Kafka"""
    
    def __init__(self):
        self.api_key = os.getenv('TMDB_API_KEY')
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.tmdb_topic = os.getenv('KAFKA_TOPIC', 'tmdb_stream')
        self.reddit_trigger_topic = 'reddit_search_trigger'  # New topic for triggering Reddit searches
        self.fetch_interval = int(os.getenv('FETCH_INTERVAL', 300))
        
        if not self.api_key:
            raise ValueError("TMDB_API_KEY environment variable is required")
        
        self.base_url = "https://api.themoviedb.org/3"
        self.producer = None
        self.imdb_loader = None
        
        self._connect_kafka()
        self._load_imdb_data()
    
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
                logger.info(f"✓ Connected to Kafka at {self.kafka_servers}")
                return
            except KafkaError as e:
                retry_count += 1
                logger.warning(f"Failed to connect to Kafka (attempt {retry_count}/{max_retries}): {e}")
                time.sleep(5)
        
        raise Exception("Could not connect to Kafka after maximum retries")
    
    def _load_imdb_data(self):
        """Load IMDb datasets for enrichment"""
        logger.info("Loading IMDb datasets...")
        try:
            self.imdb_loader = IMDbDatasetLoader(data_dir="/data/imdb_datasets")
            self.imdb_loader.load_datasets()
            logger.info("✓ IMDb datasets loaded successfully!")
        except Exception as e:
            logger.error(f"Failed to load IMDb datasets: {e}")
            logger.warning("Continuing without IMDb enrichment...")
            self.imdb_loader = None
    
    def fetch_from_multiple_sources(self):
        """
        MULTI-SOURCE DISCOVERY: Fetch from multiple TMDB endpoints
        Combines trending movies AND TV shows for comprehensive coverage
        """
        all_content = []
        seen_ids = set()
        
        # Source 1: Trending MOVIES (updated hourly)
        try:
            url = f"{self.base_url}/trending/movie/day"
            params = {'api_key': self.api_key}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            trending = response.json().get('results', [])
            logger.info(f"  📈 Trending Movies: {len(trending)}")
            
            for item in trending:
                item_id = item.get('id')
                if item_id not in seen_ids:
                    item['discovery_source'] = 'trending_movie'
                    item['media_type'] = 'movie'
                    all_content.append(item)
                    seen_ids.add(('movie', item_id))
        except Exception as e:
            logger.warning(f"Failed to fetch trending movies: {e}")
        
        # Source 1b: Trending TV SHOWS (NEW!)
        try:
            url = f"{self.base_url}/trending/tv/day"
            params = {'api_key': self.api_key}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            trending_tv = response.json().get('results', [])
            logger.info(f"  📺 Trending TV Shows: {len(trending_tv)}")
            
            for item in trending_tv:
                item_id = item.get('id')
                if item_id not in seen_ids:
                    item['discovery_source'] = 'trending_tv'
                    item['media_type'] = 'tv'
                    # Normalize: use 'title' field for both movies and TV
                    if 'name' in item and 'title' not in item:
                        item['title'] = item['name']
                    all_content.append(item)
                    seen_ids.add(('tv', item_id))
        except Exception as e:
            logger.warning(f"Failed to fetch trending TV: {e}")
        
        # Source 2: Now Playing (most current releases)
        try:
            url = f"{self.base_url}/movie/now_playing"
            params = {'api_key': self.api_key, 'region': 'US'}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            now_playing = response.json().get('results', [])[:10]  # Top 10
            logger.info(f"  🎬 Now Playing: {len(now_playing)}")
            
            for movie in now_playing:
                movie_id = movie.get('id')
                if ('movie', movie_id) not in seen_ids:
                    movie['discovery_source'] = 'now_playing'
                    movie['media_type'] = 'movie'
                    all_content.append(movie)
                    seen_ids.add(('movie', movie_id))
        except Exception as e:
            logger.warning(f"Failed to fetch now playing: {e}")
        
        # Source 2b: Popular TV Shows (NEW!)
        try:
            url = f"{self.base_url}/tv/popular"
            params = {'api_key': self.api_key}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            popular_tv = response.json().get('results', [])[:10]  # Top 10
            logger.info(f"  📺 Popular TV: {len(popular_tv)}")
            
            for item in popular_tv:
                item_id = item.get('id')
                if ('tv', item_id) not in seen_ids:
                    item['discovery_source'] = 'popular_tv'
                    item['media_type'] = 'tv'
                    if 'name' in item and 'title' not in item:
                        item['title'] = item['name']
                    all_content.append(item)
                    seen_ids.add(('tv', item_id))
        except Exception as e:
            logger.warning(f"Failed to fetch popular TV: {e}")
        
        # Source 3: Popular Movies (high engagement)
        try:
            url = f"{self.base_url}/movie/popular"
            params = {'api_key': self.api_key}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            popular = response.json().get('results', [])[:5]  # Top 5
            logger.info(f"  ⭐ Popular Movies: {len(popular)}")
            
            for movie in popular:
                movie_id = movie.get('id')
                if ('movie', movie_id) not in seen_ids:
                    movie['discovery_source'] = 'popular'
                    movie['media_type'] = 'movie'
                    all_content.append(movie)
                    seen_ids.add(('movie', movie_id))
        except Exception as e:
            logger.warning(f"Failed to fetch popular: {e}")
        
        # Rank by freshness and relevance
        all_content = self.rank_by_freshness(all_content)
        
        logger.info(f"✓ Multi-source discovery: {len(all_content)} unique movies+TV shows")
        return all_content[:20]  # Return top 20
    
    def rank_by_freshness(self, movies):
        """Rank movies by release date and popularity"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        
        def score_movie(movie):
            # Parse release date
            release_str = movie.get('release_date', '')
            try:
                release_date = datetime.strptime(release_str, '%Y-%m-%d')
                days_old = (now - release_date).days
            except:
                days_old = 9999  # Very old if no date
            
            # Fresher movies get higher scores
            freshness_score = max(0, 100 - (days_old / 7))  # Decay over weeks
            
            # Combine with popularity
            popularity = movie.get('popularity', 0)
            
            # Bonus for "now_playing" source
            source_bonus = 20 if movie.get('discovery_source') == 'now_playing' else 0
            
            return freshness_score + (popularity * 0.5) + source_bonus
        
        # Sort by score (highest first)
        movies.sort(key=score_movie, reverse=True)
        return movies
    
    def fetch_trending_movies(self):
        """
        Fetch trending movies from TMDB API
        NOW USES MULTI-SOURCE DISCOVERY for better freshness
        """
        return self.fetch_from_multiple_sources()
    
    def fetch_movie_credits(self, movie_id, media_type='movie'):
        """Fetch cast and crew for a movie or TV show"""
        try:
            # Use correct endpoint based on media type
            url = f"{self.base_url}/{media_type}/{movie_id}/credits"
            params = {'api_key': self.api_key}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Get top 3 cast members
            cast = data.get('cast', [])[:3]
            cast_names = [person.get('name') for person in cast]
            
            # Get director (for movies) or creator (for TV)
            crew = data.get('crew', [])
            if media_type == 'movie':
                directors = [person.get('name') for person in crew if person.get('job') == 'Director']
            else:
                # For TV, get creators from the show data (not in credits)
                directors = []
            
            return {
                'cast': cast_names,
                'directors': directors
            }
        except requests.RequestException as e:
            logger.error(f"Error fetching credits for {media_type} {movie_id}: {e}")
            return {'cast': [], 'directors': []}
    
    def fetch_movie_reviews(self, movie_id, media_type='movie'):
        """Fetch TMDB reviews for a movie or TV show"""
        try:
            url = f"{self.base_url}/{media_type}/{movie_id}/reviews"
            params = {'api_key': self.api_key, 'language': 'en-US', 'page': 1}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            reviews = []
            
            # Get up to 10 reviews (TMDB reviews are longer and more detailed)
            for review in data.get('results', [])[:10]:
                reviews.append({
                    'author': review.get('author', 'Anonymous'),
                    'rating': review.get('author_details', {}).get('rating'),
                    'content': review.get('content', ''),
                    'created_at': review.get('created_at', ''),
                    'source': 'tmdb'
                })
            
            return reviews
        except requests.RequestException as e:
            logger.error(f"Error fetching reviews for {media_type} {movie_id}: {e}")
            return []
    
    def scrape_imdb_live(self, title, year):
        """
        Scrape IMDb rating live when not found in static dataset
        Falls back to TMDB rating if scraping fails
        """
        try:
            # Search IMDb for the movie
            search_url = "https://www.imdb.com/find"
            params = {'q': f"{title} {year}", 's': 'tt', 'ttype': 'ft'}
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(search_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find first result
            result = soup.find('td', class_='result_text')
            if not result or not result.find('a'):
                logger.warning(f"  ⚠ IMDb search returned no results for '{title} {year}'")
                return None
            
            # Extract IMDb ID from URL
            movie_url = result.find('a')['href']
            imdb_id_match = re.search(r'/(tt\d+)/', movie_url)
            if not imdb_id_match:
                return None
            
            imdb_id = imdb_id_match.group(1)
            
            # Fetch movie page
            movie_page_url = f"https://www.imdb.com/title/{imdb_id}/"
            response = requests.get(movie_page_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract rating
            rating_elem = soup.find('span', class_='sc-bde20123-1')
            if not rating_elem:
                return None
            
            rating = float(rating_elem.text.strip())
            
            # Extract vote count
            votes_elem = soup.find('div', class_='sc-bde20123-3')
            votes = 0
            if votes_elem:
                votes_text = votes_elem.text.strip()
                # Parse "1.2M" or "234K" format
                votes_match = re.search(r'([\d.]+)([KM])?', votes_text)
                if votes_match:
                    num = float(votes_match.group(1))
                    multiplier = votes_match.group(2)
                    if multiplier == 'K':
                        votes = int(num * 1000)
                    elif multiplier == 'M':
                        votes = int(num * 1000000)
                    else:
                        votes = int(num)
            
            logger.info(f"  🌐 Live scraped IMDb: {title} ({year}) = {rating}/10 ({votes:,} votes)")
            
            return {
                'tconst': imdb_id,
                'title': title,
                'year': int(year) if year else None,
                'imdb_rating': rating,
                'imdb_votes': votes,
                'source': 'live_scrape'
            }
            
        except Exception as e:
            logger.warning(f"  ⚠ Failed to scrape IMDb for '{title}': {e}")
            return None
    
    def enrich_with_imdb(self, movie):
        """
        Enrich TMDB movie data with IMDb information
        HYBRID APPROACH: Try static dataset first, then live scraping, finally TMDB fallback
        """
        title = movie.get('title', '')
        year = movie.get('release_date', '')[:4] if movie.get('release_date') else ''
        tmdb_rating = movie.get('vote_average', 0)
        tmdb_votes = movie.get('vote_count', 0)
        
        # STEP 1: Try static IMDb dataset (fast, comprehensive for old movies)
        if self.imdb_loader:
            imdb_data = self.imdb_loader.search_movie(title)
            
            if imdb_data:
                logger.info(f"  ✓ Found in IMDb dataset: '{title}' = {imdb_data['imdb_rating']}/10")
                return imdb_data
            
            # Try original title
            original_title = movie.get('original_title')
            if original_title and original_title != title:
                imdb_data = self.imdb_loader.search_movie(original_title)
                if imdb_data:
                    logger.info(f"  ✓ Found via original title in dataset: {imdb_data['imdb_rating']}/10")
                    return imdb_data
        
        # STEP 2: Try live IMDb scraping (for new releases)
        logger.info(f"  🔍 Movie not in static dataset, attempting live scrape: '{title}' ({year})")
        imdb_data = self.scrape_imdb_live(title, year)
        
        if imdb_data:
            return imdb_data
        
        # STEP 3: Fallback to TMDB rating (better than nothing!)
        logger.warning(f"  ⚠ Using TMDB rating as fallback for '{title}': {tmdb_rating}/10")
        return {
            'tconst': f"tmdb_{movie.get('id')}",
            'title': title,
            'year': int(year) if year else None,
            'imdb_rating': tmdb_rating,
            'imdb_votes': tmdb_votes,
            'source': 'tmdb_fallback'
        }
    
    def transform_movie_data(self, movie, imdb_data=None, credits=None):
        """Transform movie data with IMDb enrichment"""
        enriched = {
            # TMDB data
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
            'source': 'tmdb',
            
            # IMDb enrichment
            'imdb_data': imdb_data if imdb_data else {},
            
            # Credits (cast/directors)
            'credits': credits if credits else {'cast': [], 'directors': []}
        }
        
        return enriched
    
    def create_reddit_search_query(self, movie, credits):
        """Create targeted Reddit search query"""
        title = movie.get('title', '')
        year = movie.get('release_date', '')[:4] if movie.get('release_date') else ''
        
        # Build search queries
        queries = []
        
        # Primary: Title + year
        if year:
            queries.append(f"{title} {year}")
        else:
            queries.append(title)
        
        # Secondary: Title + top cast
        cast = credits.get('cast', [])[:2]  # Top 2 actors
        if cast:
            queries.append(f"{title} {' '.join(cast)}")
        
        # Tertiary: Title + director
        directors = credits.get('directors', [])
        if directors:
            queries.append(f"{title} {directors[0]}")
        
        return {
            'movie_id': movie.get('id'),
            'title': title,
            'year': year,
            'queries': queries,
            'cast': cast,
            'directors': directors,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def publish_to_kafka(self, topic, data):
        """Publish data to Kafka topic"""
        try:
            future = self.producer.send(topic, value=data)
            record_metadata = future.get(timeout=10)
            
            logger.debug(f"Published to {record_metadata.topic}")
            return True
        except KafkaError as e:
            logger.error(f"Failed to publish to Kafka: {e}")
            return False
    
    def run(self):
        """Main producer loop"""
        logger.info("=" * 60)
        logger.info("Starting TMDB Producer with IMDb Enrichment")
        logger.info(f"Fetch interval: {self.fetch_interval} seconds")
        logger.info("=" * 60)
        
        while True:
            try:
                logger.info(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching trending movies...")
                
                # Fetch trending movies
                movies = self.fetch_trending_movies()
                
                if not movies:
                    logger.warning("No movies fetched. Retrying in next cycle...")
                    time.sleep(self.fetch_interval)
                    continue
                
                # Process each movie
                published_count = 0
                reddit_triggers_sent = 0
                
                for idx, movie in enumerate(movies, 1):
                    title = movie.get('title', 'Unknown')
                    logger.info(f"\n[{idx}/{len(movies)}] Processing: {title}")
                    
                    # Get credits (cast/director) - handle both movies and TV shows
                    movie_id = movie.get('id')
                    media_type = movie.get('media_type', 'movie')  # Get media type
                    credits = self.fetch_movie_credits(movie_id, media_type) if movie_id else {'cast': [], 'directors': []}
                    
                    # Fetch TMDB reviews for this movie/show
                    reviews = self.fetch_movie_reviews(movie_id, media_type) if movie_id else []
                    if reviews:
                        logger.info(f"  📝 Found {len(reviews)} TMDB reviews")
                        # Publish each review to reddit_stream (same topic as Reddit comments)
                        for review in reviews:
                            review_message = {
                                'movie_title': title,
                                'text': review['content'],
                                'author': review['author'],
                                'score': review['rating'] or 5,  # Use rating as score (default 5/10)
                                'source': 'tmdb',
                                'created_at': review['created_at'],
                                'timestamp': datetime.utcnow().isoformat()
                            }
                            self.publish_to_kafka('reddit_stream', review_message)
                    
                    # Enrich with IMDb data
                    imdb_data = self.enrich_with_imdb(movie)
                    
                    # Transform and publish to TMDB stream
                    transformed_data = self.transform_movie_data(movie, imdb_data, credits)
                    if self.publish_to_kafka(self.tmdb_topic, transformed_data):
                        published_count += 1
                    
                    # Create and send Reddit search trigger
                    reddit_trigger = self.create_reddit_search_query(movie, credits)
                    if self.publish_to_kafka(self.reddit_trigger_topic, reddit_trigger):
                        reddit_triggers_sent += 1
                        logger.info(f"  ✓ Sent Reddit search trigger: {reddit_trigger['queries'][0]}")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                
                logger.info("\n" + "=" * 60)
                logger.info(f"✓ Batch complete!")
                logger.info(f"  • Published to TMDB stream: {published_count}/{len(movies)}")
                logger.info(f"  • Reddit search triggers sent: {reddit_triggers_sent}/{len(movies)}")
                logger.info(f"  • Next fetch in {self.fetch_interval} seconds")
                logger.info("=" * 60)
                
            except Exception as e:
                logger.error(f"Error in producer loop: {e}", exc_info=True)
            
            time.sleep(self.fetch_interval)
    
    def close(self):
        """Cleanup resources"""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("Producer closed")


if __name__ == "__main__":
    producer = TMDBProducerEnriched()
    try:
        producer.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        producer.close()
