"""
Metadata Enrichment Service
Consumes TMDB movie/show data from Kafka and indexes into ChromaDB metadata collection
"""
import os
import json
import logging
import time
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from sentence_transformers import SentenceTransformer
from vector_store import VectorStore
from config import KAFKA_BOOTSTRAP_SERVERS, EMBEDDING_MODEL

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MetadataEnrichmentService:
    """Service to consume TMDB metadata and store in ChromaDB"""
    
    def __init__(self):
        self.kafka_servers = KAFKA_BOOTSTRAP_SERVERS
        self.tmdb_topic = os.getenv('KAFKA_TOPIC_TMDB', 'tmdb_stream')
        
        logger.info("🎬 Initializing Metadata Enrichment Service...")
        
        # Initialize embedding model
        logger.info(f"📦 Loading embedding model: {EMBEDDING_MODEL}")
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        
        # Initialize vector store
        self.vector_store = VectorStore()
        
        # Initialize Kafka consumer
        self._connect_kafka()
        
        logger.info("✅ Metadata Enrichment Service initialized!")
    
    def _connect_kafka(self, max_retries=10):
        """Connect to Kafka with retry logic"""
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.consumer = KafkaConsumer(
                    self.tmdb_topic,
                    bootstrap_servers=self.kafka_servers.split(','),
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='earliest',  # Process all messages including historical
                    enable_auto_commit=False,
                    consumer_timeout_ms=10000  # Wait 10s for messages, then continue
                )
                logger.info(f"✅ Connected to Kafka at {self.kafka_servers}")
                logger.info(f"📺 Subscribed to topic: {self.tmdb_topic}")
                return
            except KafkaError as e:
                retry_count += 1
                logger.warning(f"Failed to connect to Kafka (attempt {retry_count}/{max_retries}): {e}")
                time.sleep(5)
        
        raise Exception("Could not connect to Kafka after maximum retries")
    
    def _create_metadata_text(self, movie_data: dict) -> str:
        """Create searchable text from movie metadata"""
        parts = []
        
        # Title
        title = movie_data.get('title') or movie_data.get('name', '')
        parts.append(title)
        
        # Overview/plot
        if movie_data.get('overview'):
            parts.append(movie_data['overview'])
        
        # Genres
        if movie_data.get('genres'):
            genre_names = [g['name'] for g in movie_data['genres'] if isinstance(g, dict)]
            parts.append(' '.join(genre_names))
        
        # Cast (from IMDb enrichment)
        if movie_data.get('imdb_data', {}).get('cast'):
            cast = movie_data['imdb_data']['cast'][:5]  # Top 5 cast members
            parts.append(' '.join(cast))
        elif movie_data.get('credits', {}).get('cast'):
            cast = movie_data['credits']['cast'][:5]  # From TMDB credits
            parts.append(' '.join(cast))
        
        # Keywords
        if movie_data.get('keywords'):
            keywords = [k['name'] for k in movie_data['keywords'] if isinstance(k, dict)]
            parts.append(' '.join(keywords))
        
        return ' '.join(parts)
    
    def _prepare_metadata(self, movie_data: dict) -> dict:
        """Extract relevant metadata fields"""
        metadata = {
            'title': movie_data.get('title') or movie_data.get('name', ''),
            'tmdb_id': str(movie_data.get('id', '')),
            'overview': movie_data.get('overview', ''),
            'release_date': movie_data.get('release_date') or movie_data.get('first_air_date', ''),
            'vote_average': movie_data.get('vote_average', 0.0),
            'popularity': movie_data.get('popularity', 0.0),
            'media_type': movie_data.get('media_type', 'movie'),
        }
        
        # Add genres
        if movie_data.get('genres'):
            metadata['genres'] = ','.join([g['name'] for g in movie_data['genres'] if isinstance(g, dict)])
        
        # Add cast from IMDb enrichment or TMDB credits
        if movie_data.get('imdb_data', {}).get('cast'):
            metadata['cast'] = ','.join(movie_data['imdb_data']['cast'][:10])
        elif movie_data.get('credits', {}).get('cast'):
            metadata['cast'] = ','.join(movie_data['credits']['cast'][:10])
        
        # Add IMDb rating
        if movie_data.get('imdb_data', {}).get('rating'):
            metadata['imdb_rating'] = movie_data['imdb_data']['rating']
        
        # Add keywords
        if movie_data.get('keywords'):
            keywords = [k['name'] for k in movie_data['keywords'] if isinstance(k, dict)]
            metadata['keywords'] = ','.join(keywords[:10])
        
        return metadata
    
    def process_movie(self, movie_data: dict):
        """Process a single movie/show and add to metadata collection"""
        try:
            title = movie_data.get('title') or movie_data.get('name', 'Unknown')
            tmdb_id = str(movie_data.get('movie_id') or movie_data.get('id', ''))  # Support both formats
            
            if not tmdb_id or tmdb_id == '':
                logger.warning(f"Missing TMDB ID for {title}, skipping...")
                return
            
            # Create searchable text with all metadata
            searchable_text = self._create_metadata_text(movie_data)
            
            # Generate embedding
            embedding = self.embedding_model.encode(searchable_text).tolist()
            
            # Prepare metadata
            metadata = self._prepare_metadata(movie_data)
            
            # Store in ChromaDB
            movie_id = f"tmdb_{tmdb_id}"
            success = self.vector_store.add_metadata(
                movie_id=movie_id,
                title=searchable_text,
                embedding=embedding,
                metadata=metadata
            )
            
            if success:
                logger.info(f"✅ Indexed metadata: {title} (TMDB ID: {tmdb_id})")
            else:
                logger.error(f"❌ Failed to index: {title}")
                
        except Exception as e:
            logger.error(f"Error processing movie: {e}")
    
    def start(self):
        """Start consuming TMDB metadata from Kafka"""
        logger.info("🚀 Starting metadata enrichment service...")
        logger.info("Waiting for TMDB movie data...")
        
        try:
            for message in self.consumer:
                try:
                    movie_data = message.value
                    self.process_movie(movie_data)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except KeyboardInterrupt:
            logger.info("⏹️  Shutting down metadata enrichment service...")
        finally:
            self.consumer.close()


if __name__ == "__main__":
    service = MetadataEnrichmentService()
    service.start()
