"""
Evidently Drift Detection Service
Monitors data and prediction drift
"""
import os
import time
import logging
from datetime import datetime, timedelta
import pandas as pd
from cassandra.cluster import Cluster
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, RegressionPreset
import colorlog

# Configure logging
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logger = colorlog.getLogger('DriftDetection')
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class DriftDetectionService:
    """Monitors data and prediction drift using Evidently"""
    
    def __init__(self):
        self.cassandra_host = os.getenv('CASSANDRA_HOST', 'localhost')
        self.cassandra_port = int(os.getenv('CASSANDRA_PORT', 9042))
        self.cassandra_keyspace = os.getenv('CASSANDRA_KEYSPACE', 'trendscope')
        
        self.check_interval = int(os.getenv('DRIFT_CHECK_INTERVAL', 3600))  # 1 hour
        self.reference_window_hours = 24
        self.current_window_hours = 1
        
        self.cassandra_session = None
        self._init_cassandra()
    
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
    
    def fetch_predictions(self, start_time, end_time):
        """Fetch predictions from Cassandra for a time range"""
        query = """
            SELECT movie_title, timestamp, actual_trend_score, 
                   predicted_trend_score, prediction_error, features
            FROM predictions
            WHERE timestamp >= %s AND timestamp <= %s
            ALLOW FILTERING
        """
        
        try:
            rows = self.cassandra_session.execute(query, (start_time, end_time))
            
            data = []
            for row in rows:
                record = {
                    'movie_title': row.movie_title,
                    'timestamp': row.timestamp,
                    'actual_trend_score': row.actual_trend_score,
                    'predicted_trend_score': row.predicted_trend_score,
                    'prediction_error': row.prediction_error
                }
                
                # Add features
                if row.features:
                    record.update(row.features)
                
                data.append(record)
            
            return pd.DataFrame(data)
        
        except Exception as e:
            logger.error(f"Error fetching predictions: {e}")
            return pd.DataFrame()
    
    def generate_drift_report(self, reference_data, current_data):
        """Generate Evidently drift report"""
        try:
            # Data Drift Report
            data_drift_report = Report(metrics=[DataDriftPreset()])
            data_drift_report.run(
                reference_data=reference_data,
                current_data=current_data
            )
            
            # Regression Performance Report
            regression_report = Report(metrics=[RegressionPreset()])
            regression_report.run(
                reference_data=reference_data,
                current_data=current_data,
                column_mapping={
                    'target': 'actual_trend_score',
                    'prediction': 'predicted_trend_score'
                }
            )
            
            # Save reports
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_drift_report.save_html(f'/tmp/drift_report_{timestamp}.html')
            regression_report.save_html(f'/tmp/regression_report_{timestamp}.html')
            
            logger.info(f"Drift reports generated: drift_report_{timestamp}.html, regression_report_{timestamp}.html")
            
            return True
        
        except Exception as e:
            logger.error(f"Error generating drift report: {e}")
            return False
    
    def check_drift(self):
        """Check for data and prediction drift"""
        logger.info("Checking for drift...")
        
        now = datetime.now()
        
        # Reference period (e.g., last 24 hours of yesterday)
        reference_end = now - timedelta(hours=self.current_window_hours)
        reference_start = reference_end - timedelta(hours=self.reference_window_hours)
        
        # Current period (e.g., last 1 hour)
        current_end = now
        current_start = now - timedelta(hours=self.current_window_hours)
        
        # Fetch data
        logger.info(f"Fetching reference data: {reference_start} to {reference_end}")
        reference_data = self.fetch_predictions(reference_start, reference_end)
        
        logger.info(f"Fetching current data: {current_start} to {current_end}")
        current_data = self.fetch_predictions(current_start, current_end)
        
        if reference_data.empty or current_data.empty:
            logger.warning("Insufficient data for drift detection")
            return
        
        logger.info(f"Reference data: {len(reference_data)} records")
        logger.info(f"Current data: {len(current_data)} records")
        
        # Generate drift report
        self.generate_drift_report(reference_data, current_data)
    
    def run(self):
        """Main monitoring loop"""
        logger.info(f"Starting Drift Detection Service (check interval: {self.check_interval}s)")
        
        try:
            while True:
                self.check_drift()
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            logger.info("Shutting down Drift Detection Service...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    service = DriftDetectionService()
    service.run()
