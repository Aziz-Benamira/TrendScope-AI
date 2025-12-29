"""
RAG Configuration
"""
import os

# ChromaDB settings
CHROMA_HOST = os.getenv('CHROMA_HOST', 'chromadb')
CHROMA_PORT = int(os.getenv('CHROMA_PORT', 8000))
COLLECTION_NAME = 'movie_reviews'

# Ollama settings
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'ollama')
OLLAMA_PORT = int(os.getenv('OLLAMA_PORT', 11434))
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'mistral')
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"

# Embedding model (runs locally with sentence-transformers)
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')

# Kafka settings
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
KAFKA_REDDIT_TOPIC = os.getenv('KAFKA_TOPIC_REDDIT', 'reddit_stream')

# RAG settings
MAX_REVIEWS_TO_RETRIEVE = int(os.getenv('MAX_REVIEWS', 100))  # Increased from 50
DEFAULT_TIME_WINDOW_HOURS = int(os.getenv('TIME_WINDOW_HOURS', 168))  # 7 days instead of 24h
