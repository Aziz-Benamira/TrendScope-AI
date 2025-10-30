"""
Online Machine Learning Service using River
Consumes trend_stream and makes real-time predictions
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
import mlflow.pyfunc
from river import linear_model, preprocessing, compose, metrics, optim
from cassandra.cluster import Cluster
import colorlog
from prometheus_client import start_http_server, Counter, Gauge, Histogram
import numpy as np

# Configure logging
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logger = colorlog.getLogger('OnlineML')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Prometheus metrics
predictions_counter = Counter('ml_predictions_total', 'Total number of predictions made')
mae_gauge = Gauge('ml_mae', 'Current Mean Absolute Error')
rmse_gauge = Gauge('ml_rmse', 'Current Root Mean Square Error')
prediction_time = Histogram('ml_prediction_seconds', 'Time spent making predictions')
update_time = Histogram('ml_update_seconds', 'Time spent updating model')


class OnlineMLService:
    """Online Machine Learning service for trend prediction"""
    
    def __init__(self):
        # Environment variables
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.trend_topic = os.getenv('KAFKA_TOPIC_TREND', 'trend_stream')
        self.prediction_topic = os.getenv('KAFKA_TOPIC_PREDICTIONS', 'predictions_stream')
        
        self.mlflow_uri = os.getenv('MLFLOW_TRACKING_URI', 'http://localhost:5000')
        self.experiment_name = os.getenv('MLFLOW_EXPERIMENT_NAME', 'movie_trend_prediction')
        
        self.cassandra_host = os.getenv('CASSANDRA_HOST', 'localhost')
        self.cassandra_port = int(os.getenv('CASSANDRA_PORT', 9042))
        self.cassandra_keyspace = os.getenv('CASSANDRA_KEYSPACE', 'trendscope')
        
        # Model parameters
        self.model_version = "v1.0"
        self.learning_rate = 0.01
        self.window_size = 100  # Keep last N observations for metrics
        
        # Initialize components
        self.consumer = None
        self.producer = None
        self.cassandra_session = None
        self.model = None
        self.scaler = None
        
        # Metrics tracking
        self.mae_metric = metrics.MAE()
        self.rmse_metric = metrics.RMSE()
        self.r2_metric = metrics.R2()
        
        # History for trend analysis
        self.movie_history = {}  # movie_title -> deque of recent observations
        
        self._init_mlflow()
        self._init_kafka()
        self._init_cassandra()
        self._init_model()
        
        # Start Prometheus metrics server
        start_http_server(8000)
        logger.info("Prometheus metrics server started on port 8000")
    
    def _init_mlflow(self):
        """Initialize MLflow tracking"""
        mlflow.set_tracking_uri(self.mlflow_uri)
        mlflow.set_experiment(self.experiment_name)
        logger.info(f"MLflow tracking URI: {self.mlflow_uri}")
        
        # Start MLflow run
        mlflow.start_run(run_name=f"online_learning_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # Log parameters
        mlflow.log_param("model_type", "River Linear Regression")
        mlflow.log_param("learning_rate", self.learning_rate)
        mlflow.log_param("model_version", self.model_version)
    
    def _init_kafka(self):
        """Initialize Kafka consumer and producer"""
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.consumer = KafkaConsumer(
                    self.trend_topic,
                    bootstrap_servers=self.kafka_servers.split(','),
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest',
                    enable_auto_commit=True,
                    group_id='ml-service-group'
                )
                
                self.producer = KafkaProducer(
                    bootstrap_servers=self.kafka_servers.split(','),
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                
                logger.info(f"Connected to Kafka at {self.kafka_servers}")
                return
            except KafkaError as e:
                retry_count += 1
                logger.warning(f"Failed to connect to Kafka (attempt {retry_count}/{max_retries}): {e}")
                time.sleep(5)
        
        raise Exception("Could not connect to Kafka after maximum retries")
    
    def _init_cassandra(self):
        """Initialize Cassandra connection"""
        max_retries = 10
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                cluster = Cluster([self.cassandra_host], port=self.cassandra_port)
                self.cassandra_session = cluster.connect(self.cassandra_keyspace)
                logger.info(f"Connected to Cassandra at {self.cassandra_host}")
                return
            except Exception as e:
                retry_count += 1
                logger.warning(f"Failed to connect to Cassandra (attempt {retry_count}/{max_retries}): {e}")
                time.sleep(5)
        
        raise Exception("Could not connect to Cassandra after maximum retries")
    
    def _init_model(self):
        """Initialize River online learning model"""
        logger.info("Initializing River online learning model...")
        
        # Create a pipeline with scaling and linear regression
        self.model = compose.Pipeline(
            preprocessing.StandardScaler(),
            linear_model.LinearRegression(
                optimizer=optim.SGD(self.learning_rate),
                l2=0.001
            )
        )
        
        logger.info("Model initialized successfully")
    
    def extract_features(self, data, movie_title):
        """Extract features from trend data"""
        features = {
            'popularity': float(data.get('popularity', 0)),
            'mentions_count': float(data.get('mentions_count', 0)),
            'mentions_rate': float(data.get('mentions_rate', 0)),
            'avg_sentiment': float(data.get('avg_sentiment', 0)),
            'vote_average': float(data.get('vote_average', 0)),
            'avg_reddit_score': float(data.get('avg_reddit_score', 0))
        }
        
        # Add temporal features
        window_start = data.get('window_start')
        if window_start:
            try:
                dt = datetime.fromisoformat(window_start.replace('Z', '+00:00'))
                features['hour'] = float(dt.hour)
                features['day_of_week'] = float(dt.weekday())
            except:
                features['hour'] = 0.0
                features['day_of_week'] = 0.0
        
        # Add historical features if available
        if movie_title in self.movie_history and len(self.movie_history[movie_title]) > 0:
            recent = list(self.movie_history[movie_title])[-5:]  # Last 5 observations
            
            if len(recent) >= 2:
                # Delta features
                features['delta_mentions'] = features['mentions_count'] - recent[-1].get('mentions_count', 0)
                features['delta_sentiment'] = features['avg_sentiment'] - recent[-1].get('avg_sentiment', 0)
                features['delta_popularity'] = features['popularity'] - recent[-1].get('popularity', 0)
            else:
                features['delta_mentions'] = 0.0
                features['delta_sentiment'] = 0.0
                features['delta_popularity'] = 0.0
            
            # Moving averages
            avg_mentions = np.mean([r.get('mentions_count', 0) for r in recent])
            avg_sentiment = np.mean([r.get('avg_sentiment', 0) for r in recent])
            
            features['ma_mentions'] = float(avg_mentions)
            features['ma_sentiment'] = float(avg_sentiment)
        else:
            features['delta_mentions'] = 0.0
            features['delta_sentiment'] = 0.0
            features['delta_popularity'] = 0.0
            features['ma_mentions'] = features['mentions_count']
            features['ma_sentiment'] = features['avg_sentiment']
        
        return features
    
    @prediction_time.time()
    def predict(self, features):
        """Make prediction using the model"""
        try:
            prediction = self.model.predict_one(features)
            return float(prediction) if prediction else 0.0
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return 0.0
    
    @update_time.time()
    def update_model(self, features, target):
        """Update model with new observation"""
        try:
            self.model.learn_one(features, target)
            return True
        except Exception as e:
            logger.error(f"Model update error: {e}")
            return False
    
    def update_metrics(self, y_true, y_pred):
        """Update performance metrics"""
        self.mae_metric.update(y_true, y_pred)
        self.rmse_metric.update(y_true, y_pred)
        self.r2_metric.update(y_true, y_pred)
        
        # Update Prometheus metrics
        mae_gauge.set(self.mae_metric.get())
        rmse_gauge.set(self.rmse_metric.get())
        
        # Log to MLflow periodically
        if predictions_counter._value._value % 100 == 0:
            mlflow.log_metric("mae", self.mae_metric.get(), step=int(predictions_counter._value._value))
            mlflow.log_metric("rmse", self.rmse_metric.get(), step=int(predictions_counter._value._value))
            mlflow.log_metric("r2", self.r2_metric.get(), step=int(predictions_counter._value._value))
    
    def save_prediction_to_cassandra(self, prediction_data):
        """Save prediction to Cassandra"""
        try:
            query = """
                INSERT INTO predictions (
                    movie_title, timestamp, actual_trend_score, 
                    predicted_trend_score, prediction_error, 
                    model_version, features
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            self.cassandra_session.execute(query, (
                prediction_data['movie_title'],
                datetime.fromisoformat(prediction_data['timestamp'].replace('Z', '+00:00')),
                prediction_data['actual_trend_score'],
                prediction_data['predicted_trend_score'],
                prediction_data['prediction_error'],
                prediction_data['model_version'],
                prediction_data['features']
            ))
            
            return True
        except Exception as e:
            logger.error(f"Error saving to Cassandra: {e}")
            return False
    
    def publish_prediction(self, prediction_data):
        """Publish prediction to Kafka"""
        try:
            self.producer.send(self.prediction_topic, value=prediction_data)
            return True
        except KafkaError as e:
            logger.error(f"Error publishing to Kafka: {e}")
            return False
    
    def update_movie_history(self, movie_title, data):
        """Update movie history for feature engineering"""
        if movie_title not in self.movie_history:
            self.movie_history[movie_title] = deque(maxlen=self.window_size)
        
        self.movie_history[movie_title].append(data)
    
    def process_message(self, message):
        """Process a single message from Kafka"""
        try:
            data = message.value
            movie_title = data.get('movie_title')
            
            if not movie_title:
                return
            
            # Extract features
            features = self.extract_features(data, movie_title)
            
            # Make prediction
            predicted_score = self.predict(features)
            
            # Get actual score
            actual_score = float(data.get('trend_score', 0))
            
            # Calculate error
            prediction_error = abs(actual_score - predicted_score)
            
            # Update metrics
            self.update_metrics(actual_score, predicted_score)
            
            # Update model (learn from this observation)
            self.update_model(features, actual_score)
            
            # Update Prometheus counter
            predictions_counter.inc()
            
            # Prepare prediction data
            prediction_data = {
                'movie_title': movie_title,
                'timestamp': data.get('window_start', datetime.utcnow().isoformat()),
                'actual_trend_score': actual_score,
                'predicted_trend_score': predicted_score,
                'prediction_error': prediction_error,
                'model_version': self.model_version,
                'features': features,
                'mae': self.mae_metric.get(),
                'rmse': self.rmse_metric.get(),
                'r2': self.r2_metric.get()
            }
            
            # Save to Cassandra
            self.save_prediction_to_cassandra(prediction_data)
            
            # Publish to Kafka
            self.publish_prediction(prediction_data)
            
            # Update movie history
            self.update_movie_history(movie_title, data)
            
            logger.info(f"Processed {movie_title}: Actual={actual_score:.2f}, "
                       f"Predicted={predicted_score:.2f}, Error={prediction_error:.2f}, "
                       f"MAE={self.mae_metric.get():.2f}")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def run(self):
        """Main service loop"""
        logger.info("Starting Online ML Service...")
        
        try:
            for message in self.consumer:
                self.process_message(message)
        
        except KeyboardInterrupt:
            logger.info("Shutting down ML Service...")
        except Exception as e:
            logger.error(f"Unexpected error in ML service: {e}")
        finally:
            # Cleanup
            if self.consumer:
                self.consumer.close()
            if self.producer:
                self.producer.close()
            
            # End MLflow run
            mlflow.end_run()
            
            logger.info("ML Service stopped")


if __name__ == "__main__":
    service = OnlineMLService()
    service.run()
