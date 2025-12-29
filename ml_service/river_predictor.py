"""
River Online Learning Service - Enhanced with IMDb Features
Consumes trend_stream, trains incrementally, and predicts movie trending probability
"""
import os
import json
import logging
import time
from datetime import datetime
from collections import deque
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import mlflow
from river import (
    linear_model, 
    preprocessing, 
    compose, 
    metrics, 
    optim,
    ensemble,
    tree
)
from cassandra.cluster import Cluster
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

logger = colorlog.getLogger('RiverML')
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class RiverOnlineLearner:
    """River-based online learning for movie trend prediction"""
    
    def __init__(self):
        # Kafka configuration
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.input_topic = 'trend_stream'  # Input: TrendScores from Spark
        self.output_topic = 'predictions_stream'  # Output: Predictions
        
        # MLflow configuration
        self.mlflow_uri = os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow:5000')
        self.experiment_name = 'river_online_learning'
        
        # Cassandra configuration
        self.cassandra_host = os.getenv('CASSANDRA_HOST', 'cassandra')
        
        # Initialize components
        self.consumer = None
        self.producer = None
        self.cassandra_session = None
        
        # Initialize River model
        self.model = self._create_model()
        
        # Metrics
        self.mae = metrics.MAE()
        self.rmse = metrics.RMSE()
        self.samples_processed = 0
        
        # Movie history (for temporal features)
        self.movie_history = {}  # movie_title -> deque of past TrendScores
        
        self._init_kafka()
        self._init_mlflow()
        self._init_cassandra()
    
    def _create_model(self):
        """Create River online learning model with feature engineering"""
        
        # Use Linear Regression which is stable in River
        model = compose.Pipeline(
            preprocessing.StandardScaler(),
            linear_model.LinearRegression(
                optimizer=optim.SGD(0.01)
            )
        )
        
        logger.info("✓ Created River model: Linear Regression with SGD")
        return model
    
    def _init_kafka(self):
        """Initialize Kafka consumer and producer"""
        max_retries = 5
        retry_count = 0
        
        # Producer
        while retry_count < max_retries:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.kafka_servers.split(','),
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    acks='all'
                )
                logger.info(f"✓ Kafka producer connected")
                break
            except KafkaError as e:
                retry_count += 1
                logger.warning(f"Producer connection attempt {retry_count}/{max_retries}: {e}")
                time.sleep(5)
        
        # Consumer
        retry_count = 0
        while retry_count < max_retries:
            try:
                self.consumer = KafkaConsumer(
                    self.input_topic,
                    bootstrap_servers=self.kafka_servers.split(','),
                    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                    auto_offset_reset='latest',
                    enable_auto_commit=True,
                    group_id='river-ml-group'
                )
                logger.info(f"✓ Kafka consumer subscribed to '{self.input_topic}'")
                return
            except KafkaError as e:
                retry_count += 1
                logger.warning(f"Consumer connection attempt {retry_count}/{max_retries}: {e}")
                time.sleep(5)
        
        raise Exception("Could not connect to Kafka")
    
    def _init_mlflow(self):
        """Initialize MLflow tracking"""
        try:
            mlflow.set_tracking_uri(self.mlflow_uri)
            mlflow.set_experiment(self.experiment_name)
            mlflow.start_run(run_name=f"river_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            # Log model parameters
            mlflow.log_param("model_type", "AdaptiveRandomForestRegressor")
            mlflow.log_param("n_models", 10)
            mlflow.log_param("kafka_input", self.input_topic)
            mlflow.log_param("kafka_output", self.output_topic)
            
            logger.info("✓ MLflow tracking initialized")
        except Exception as e:
            logger.warning(f"MLflow initialization failed: {e}")
    
    def _init_cassandra(self):
        """Initialize Cassandra connection for prediction storage"""
        try:
            cluster = Cluster([self.cassandra_host])
            self.cassandra_session = cluster.connect()
            
            # Create keyspace and table for predictions
            self.cassandra_session.execute("""
                CREATE KEYSPACE IF NOT EXISTS ml_predictions
                WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
            """)
            
            self.cassandra_session.set_keyspace('ml_predictions')
            
            self.cassandra_session.execute("""
                CREATE TABLE IF NOT EXISTS trend_predictions (
                    movie_title TEXT,
                    timestamp TIMESTAMP,
                    predicted_trend_score DOUBLE,
                    actual_trend_score DOUBLE,
                    imdb_rating DOUBLE,
                    imdb_votes INT,
                    tmdb_popularity DOUBLE,
                    reddit_mentions INT,
                    sentiment_score DOUBLE,
                    prediction_error DOUBLE,
                    PRIMARY KEY (movie_title, timestamp)
                ) WITH CLUSTERING ORDER BY (timestamp DESC)
            """)
            
            logger.info("✓ Cassandra predictions table ready")
        except Exception as e:
            logger.warning(f"Cassandra initialization failed: {e}")
            self.cassandra_session = None
    
    def extract_features(self, trend_data):
        """Extract features from trend data for ML model"""
        
        # Get movie title for history tracking
        movie_title = trend_data.get('title', 'Unknown')
        
        # Initialize history for new movies
        if movie_title not in self.movie_history:
            self.movie_history[movie_title] = deque(maxlen=10)
        
        # Extract IMDb features
        imdb_data = trend_data.get('imdb_data', {})
        imdb_rating = imdb_data.get('imdb_rating', 0.0)
        imdb_votes = imdb_data.get('imdb_votes', 0)
        imdb_year = imdb_data.get('year', 2020)
        
        # Extract TMDB features
        popularity = trend_data.get('popularity', 0.0)
        vote_average = trend_data.get('vote_average', 0.0)
        vote_count = trend_data.get('vote_count', 0)
        
        # Extract Reddit features
        reddit_mentions = trend_data.get('reddit_mentions', 0)
        sentiment_score = trend_data.get('avg_sentiment', 0.0)
        
        # Temporal features
        history = list(self.movie_history[movie_title])
        trend_momentum = 0.0
        if len(history) >= 2:
            # Calculate momentum (change in TrendScore)
            trend_momentum = history[-1] - history[-2] if len(history) >= 2 else 0.0
        
        # Composite features
        age = 2025 - imdb_year  # Movie age in years
        engagement_rate = reddit_mentions / (imdb_votes + 1)  # Reddit engagement vs IMDb votes
        quality_score = (imdb_rating / 10.0) * (1 + (imdb_votes / 100000))  # Quality weighted by votes
        
        # Feature dictionary
        features = {
            # IMDb features
            'imdb_rating': float(imdb_rating),
            'imdb_votes': float(imdb_votes),
            'imdb_votes_log': float(np.log1p(imdb_votes)),
            'movie_age': float(age),
            
            # TMDB features
            'tmdb_popularity': float(popularity),
            'tmdb_vote_average': float(vote_average),
            'tmdb_vote_count': float(vote_count),
            'tmdb_vote_count_log': float(np.log1p(vote_count)),
            
            # Reddit features
            'reddit_mentions': float(reddit_mentions),
            'reddit_mentions_log': float(np.log1p(reddit_mentions)),
            'sentiment_score': float(sentiment_score),
            'sentiment_positive': 1.0 if sentiment_score > 0.2 else 0.0,
            
            # Composite features
            'quality_score': float(quality_score),
            'engagement_rate': float(engagement_rate),
            'trend_momentum': float(trend_momentum),
            
            # Interaction features
            'rating_popularity': float(imdb_rating * popularity / 100),
            'sentiment_mentions': float(sentiment_score * reddit_mentions)
        }
        
        return features
    
    def get_target(self, trend_data):
        """Extract target variable (TrendScore)"""
        return float(trend_data.get('trend_score', 0.0))
    
    def predict_and_learn(self, trend_data):
        """Make prediction and update model incrementally"""
        
        movie_title = trend_data.get('title', 'Unknown')
        
        # Extract features and target
        features = self.extract_features(trend_data)
        y_true = self.get_target(trend_data)
        
        # Make prediction BEFORE learning (important for online learning)
        y_pred = self.model.predict_one(features)
        
        # Update model with new observation
        self.model.learn_one(features, y_true)
        
        # Update metrics
        self.mae.update(y_true, y_pred)
        self.rmse.update(y_true, y_pred)
        
        # Update movie history
        self.movie_history[movie_title].append(y_true)
        
        # Increment counter
        self.samples_processed += 1
        
        # Log metrics to MLflow every 10 samples
        if self.samples_processed % 10 == 0:
            try:
                mlflow.log_metric("mae", self.mae.get(), step=self.samples_processed)
                mlflow.log_metric("rmse", self.rmse.get(), step=self.samples_processed)
                mlflow.log_metric("samples", self.samples_processed, step=self.samples_processed)
            except:
                pass
        
        # Create prediction result
        prediction = {
            'movie_title': movie_title,
            'timestamp': datetime.utcnow().isoformat(),
            'predicted_trend_score': float(y_pred),
            'actual_trend_score': float(y_true),
            'prediction_error': abs(float(y_true - y_pred)),
            'features': features,
            'model_mae': float(self.mae.get()),
            'model_rmse': float(self.rmse.get()),
            'samples_processed': self.samples_processed
        }
        
        return prediction
    
    def publish_prediction(self, prediction):
        """Publish prediction to Kafka"""
        try:
            self.producer.send(self.output_topic, value=prediction)
            return True
        except Exception as e:
            logger.error(f"Failed to publish prediction: {e}")
            return False
    
    def store_prediction(self, prediction):
        """Store prediction in Cassandra"""
        if not self.cassandra_session:
            return
        
        try:
            query = """
                INSERT INTO trend_predictions (
                    movie_title, timestamp, predicted_trend_score, actual_trend_score,
                    imdb_rating, imdb_votes, tmdb_popularity, reddit_mentions, 
                    sentiment_score, prediction_error
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            features = prediction['features']
            self.cassandra_session.execute(query, (
                prediction['movie_title'],
                datetime.fromisoformat(prediction['timestamp']),
                prediction['predicted_trend_score'],
                prediction['actual_trend_score'],
                features.get('imdb_rating', 0.0),
                int(features.get('imdb_votes', 0)),
                features.get('tmdb_popularity', 0.0),
                int(features.get('reddit_mentions', 0)),
                features.get('sentiment_score', 0.0),
                prediction['prediction_error']
            ))
        except Exception as e:
            logger.debug(f"Failed to store prediction: {e}")
    
    def run(self):
        """Main loop - consume trend data, predict, and learn"""
        logger.info("=" * 60)
        logger.info("River Online Learning Service - STARTED")
        logger.info(f"Input: {self.input_topic}")
        logger.info(f"Output: {self.output_topic}")
        logger.info("=" * 60)
        
        try:
            for message in self.consumer:
                try:
                    trend_data = message.value
                    
                    # Predict and learn
                    prediction = self.predict_and_learn(trend_data)
                    
                    # Publish prediction
                    self.publish_prediction(prediction)
                    
                    # Store in Cassandra
                    self.store_prediction(prediction)
                    
                    # Log progress
                    if self.samples_processed % 5 == 0:
                        logger.info(f"\n[{self.samples_processed}] {prediction['movie_title']}")
                        logger.info(f"  Predicted: {prediction['predicted_trend_score']:.2f}")
                        logger.info(f"  Actual:    {prediction['actual_trend_score']:.2f}")
                        logger.info(f"  Error:     {prediction['prediction_error']:.2f}")
                        logger.info(f"  Model MAE: {self.mae.get():.2f}, RMSE: {self.rmse.get():.2f}")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
        
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
        try:
            mlflow.end_run()
        except:
            pass
        logger.info("✓ River ML service closed")


# Numpy for log transformations
import numpy as np


if __name__ == "__main__":
    learner = RiverOnlineLearner()
    try:
        learner.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        learner.close()
