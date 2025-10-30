"""
Cassandra Schema Initialization Script
Run this to create the required keyspace and tables
"""
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def wait_for_cassandra(host, port, max_retries=30):
    """Wait for Cassandra to be ready"""
    retry_count = 0
    while retry_count < max_retries:
        try:
            cluster = Cluster([host], port=port)
            session = cluster.connect()
            session.shutdown()
            cluster.shutdown()
            logger.info("Cassandra is ready")
            return True
        except Exception as e:
            retry_count += 1
            logger.warning(f"Waiting for Cassandra... (attempt {retry_count}/{max_retries})")
            time.sleep(5)
    
    return False


def init_cassandra_schema():
    """Initialize Cassandra keyspace and tables"""
    host = os.getenv('CASSANDRA_HOST', 'localhost')
    port = int(os.getenv('CASSANDRA_PORT', 9042))
    keyspace = os.getenv('CASSANDRA_KEYSPACE', 'trendscope')
    
    logger.info(f"Connecting to Cassandra at {host}:{port}")
    
    # Wait for Cassandra to be ready
    if not wait_for_cassandra(host, port):
        raise Exception("Cassandra is not ready")
    
    cluster = Cluster([host], port=port)
    session = cluster.connect()
    
    try:
        # Create keyspace
        logger.info(f"Creating keyspace: {keyspace}")
        session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {keyspace}
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
        """)
        
        session.set_keyspace(keyspace)
        
        # Create movie_trends table
        logger.info("Creating movie_trends table")
        session.execute("""
            CREATE TABLE IF NOT EXISTS movie_trends (
                movie_title TEXT,
                window_start TIMESTAMP,
                window_end TIMESTAMP,
                movie_id INT,
                popularity FLOAT,
                vote_average FLOAT,
                mentions_count INT,
                mentions_rate FLOAT,
                avg_sentiment FLOAT,
                avg_reddit_score FLOAT,
                trend_score FLOAT,
                processed_time TIMESTAMP,
                PRIMARY KEY ((movie_title), window_start)
            ) WITH CLUSTERING ORDER BY (window_start DESC)
        """)
        
        # Create predictions table
        logger.info("Creating predictions table")
        session.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                movie_title TEXT,
                timestamp TIMESTAMP,
                actual_trend_score FLOAT,
                predicted_trend_score FLOAT,
                prediction_error FLOAT,
                model_version TEXT,
                features MAP<TEXT, FLOAT>,
                PRIMARY KEY ((movie_title), timestamp)
            ) WITH CLUSTERING ORDER BY (timestamp DESC)
        """)
        
        # Create model_metrics table
        logger.info("Creating model_metrics table")
        session.execute("""
            CREATE TABLE IF NOT EXISTS model_metrics (
                metric_id UUID,
                timestamp TIMESTAMP,
                metric_name TEXT,
                metric_value FLOAT,
                model_version TEXT,
                PRIMARY KEY (metric_id, timestamp)
            ) WITH CLUSTERING ORDER BY (timestamp DESC)
        """)
        
        logger.info("Schema initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing schema: {e}")
        raise
    finally:
        session.shutdown()
        cluster.shutdown()


if __name__ == "__main__":
    init_cassandra_schema()
