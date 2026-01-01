"""
Spark Structured Streaming Processor
Consumes TMDB and Reddit streams, applies sentiment analysis, computes TrendScore
"""
import os
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, window, avg, count, sum as _sum, 
    udf, current_timestamp, expr, lit, when, coalesce
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, 
    FloatType, ArrayType, BooleanType, TimestampType
)
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import colorlog

# Configure logging
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logger = colorlog.getLogger('SparkProcessor')
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class SparkStreamingProcessor:
    """Processes TMDB and Reddit streams and computes TrendScore"""
    
    def __init__(self):
        # Environment variables
        self.spark_master = os.getenv('SPARK_MASTER_URL', 'local[*]')
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.cassandra_host = os.getenv('CASSANDRA_HOST', 'localhost')
        self.cassandra_port = os.getenv('CASSANDRA_PORT', '9042')
        self.cassandra_keyspace = os.getenv('CASSANDRA_KEYSPACE', 'trendscope')
        
        # Kafka topics
        self.tmdb_topic = os.getenv('KAFKA_TOPIC_TMDB', 'tmdb_stream')
        self.reddit_topic = os.getenv('KAFKA_TOPIC_REDDIT', 'reddit_stream')
        self.trend_topic = os.getenv('KAFKA_TOPIC_TREND', 'trend_stream')
        
        # TrendScore weights
        self.w1 = float(os.getenv('W1_POPULARITY', 0.4))
        self.w2 = float(os.getenv('W2_MENTIONS', 0.3))
        self.w3 = float(os.getenv('W3_SENTIMENT', 0.3))
        
        # Window parameters
        self.window_duration = os.getenv('TREND_WINDOW_DURATION', '5 minutes')
        self.slide_duration = os.getenv('TREND_SLIDE_DURATION', '1 minute')
        
        self.spark = None
        self._init_spark()
    
    def _init_spark(self):
        """Initialize Spark session with required configurations"""
        logger.info("Initializing Spark session...")

        self.spark = (
            SparkSession.builder
            .appName("TrendScope-StreamingProcessor")
            .master(self.spark_master)

            # 🔑 CRITICAL FIX (Ivy cache location)
            .config("spark.jars.ivy", "/tmp/.ivy2")

            # Kafka + Cassandra connectors
            .config(
                "spark.jars.packages",
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
                "com.datastax.spark:spark-cassandra-connector_2.12:3.4.1"
            )

            # Cassandra config
            .config("spark.cassandra.connection.host", self.cassandra_host)
            .config("spark.cassandra.connection.port", self.cassandra_port)

            # Streaming config
            .config("spark.sql.streaming.checkpointLocation", "/tmp/spark-checkpoint")
            .config("spark.streaming.stopGracefullyOnShutdown", "true")

            .getOrCreate()
        )

        self.spark.sparkContext.setLogLevel("WARN")
        logger.info("Spark session initialized successfully")

    
    def get_tmdb_schema(self):
        """Define schema for TMDB stream"""
        return StructType([
            StructField("movie_id", IntegerType(), False),
            StructField("title", StringType(), False),
            StructField("original_title", StringType(), True),
            StructField("popularity", FloatType(), True),
            StructField("vote_average", FloatType(), True),
            StructField("vote_count", IntegerType(), True),
            StructField("release_date", StringType(), True),
            StructField("genre_ids", ArrayType(IntegerType()), True),
            StructField("overview", StringType(), True),
            StructField("adult", BooleanType(), True),
            StructField("original_language", StringType(), True),
            StructField("poster_path", StringType(), True),
            StructField("backdrop_path", StringType(), True),
            StructField("timestamp", StringType(), False),
            StructField("source", StringType(), True)
        ])
    
    def get_reddit_schema(self):
        """Define schema for Reddit stream"""
        return StructType([
            StructField("comment_id", StringType(), True),
            StructField("post_id", StringType(), False),
            StructField("post_title", StringType(), True),
            StructField("title", StringType(), True),
            StructField("text", StringType(), False),
            StructField("author", StringType(), True),
            StructField("score", IntegerType(), True),
            StructField("created_utc", StringType(), True),
            StructField("movie_mentions", ArrayType(StringType()), True),
            StructField("subreddit", StringType(), True),
            StructField("timestamp", StringType(), False),
            StructField("source", StringType(), True),
            StructField("type", StringType(), True)
        ])
    
    def create_sentiment_udf(self):
        """Create UDF for sentiment analysis using VADER"""
        analyzer = SentimentIntensityAnalyzer()
        
        def analyze_sentiment(text):
            if not text:
                return 0.0
            scores = analyzer.polarity_scores(text)
            return float(scores['compound'])
        
        return udf(analyze_sentiment, FloatType())
    
    def read_tmdb_stream(self):
        """Read TMDB stream from Kafka"""
        logger.info(f"Reading TMDB stream from topic: {self.tmdb_topic}")
        
        df = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", self.kafka_servers) \
            .option("subscribe", self.tmdb_topic) \
            .option("startingOffsets", "latest") \
            .load()
        
        # Parse JSON
        tmdb_schema = self.get_tmdb_schema()
        parsed_df = df.select(
            from_json(col("value").cast("string"), tmdb_schema).alias("data")
        ).select("data.*")
        
        # Add timestamp for windowing
        parsed_df = parsed_df.withColumn(
            "event_time",
            col("timestamp").cast(TimestampType())
        )
        
        return parsed_df
    
    def read_reddit_stream(self):
        """Read Reddit stream from Kafka"""
        logger.info(f"Reading Reddit stream from topic: {self.reddit_topic}")
        
        df = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", self.kafka_servers) \
            .option("subscribe", self.reddit_topic) \
            .option("startingOffsets", "latest") \
            .load()
        
        # Parse JSON
        reddit_schema = self.get_reddit_schema()
        parsed_df = df.select(
            from_json(col("value").cast("string"), reddit_schema).alias("data")
        ).select("data.*")
        
        # Add timestamp for windowing
        parsed_df = parsed_df.withColumn(
            "event_time",
            col("timestamp").cast(TimestampType())
        )
        
        # Apply sentiment analysis
        sentiment_udf = self.create_sentiment_udf()
        parsed_df = parsed_df.withColumn(
            "sentiment_score",
            sentiment_udf(col("text"))
        )
        
        return parsed_df
    
    def compute_reddit_aggregates(self, reddit_df):
        """Compute windowed aggregates for Reddit data"""
        logger.info("Computing Reddit aggregates...")
        
        # Explode movie mentions to get per-movie metrics
        from pyspark.sql.functions import explode, size
        
        exploded_df = reddit_df \
            .filter(size(col("movie_mentions")) > 0) \
            .select(
                explode(col("movie_mentions")).alias("movie_title"),
                col("sentiment_score"),
                col("event_time"),
                col("score").alias("reddit_score")
            )
        
        # Window aggregation
        aggregated_df = exploded_df \
            .withWatermark("event_time", "10 minutes") \
            .groupBy(
                window(col("event_time"), self.window_duration, self.slide_duration),
                col("movie_title")
            ) \
            .agg(
                count("*").alias("mentions_count"),
                avg("sentiment_score").alias("avg_sentiment"),
                avg("reddit_score").alias("avg_reddit_score")
            )
        
        # Flatten window struct
        aggregated_df = aggregated_df \
            .select(
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("movie_title"),
                col("mentions_count"),
                col("avg_sentiment"),
                col("avg_reddit_score")
            )
        
        return aggregated_df
    
    def compute_tmdb_aggregates(self, tmdb_df):
        """Compute windowed aggregates for TMDB data"""
        logger.info("Computing TMDB aggregates...")
        
        # Window aggregation
        aggregated_df = tmdb_df \
            .withWatermark("event_time", "10 minutes") \
            .groupBy(
                window(col("event_time"), self.window_duration, self.slide_duration),
                col("title"),
                col("movie_id")
            ) \
            .agg(
                avg("popularity").alias("avg_popularity"),
                avg("vote_average").alias("avg_vote"),
                avg("vote_count").alias("avg_vote_count")
            )
        
        # Flatten window struct
        aggregated_df = aggregated_df \
            .select(
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("title").alias("movie_title"),
                col("movie_id"),
                col("avg_popularity"),
                col("avg_vote"),
                col("avg_vote_count")
            )
        
        return aggregated_df
    
    def join_and_compute_trendscore(self, tmdb_agg, reddit_agg):
        """Join TMDB and Reddit aggregates and compute TrendScore"""
        logger.info("Computing TrendScore...")
        
        # Outer join to capture movies from both sources
        joined_df = tmdb_agg.alias("tmdb") \
            .join(
                reddit_agg.alias("reddit"),
                (col("tmdb.window_start") == col("reddit.window_start")) &
                (col("tmdb.movie_title") == col("reddit.movie_title")),
                "full_outer"
            )
        
        # Coalesce fields from both sides
        joined_df = joined_df.select(
            coalesce(col("tmdb.window_start"), col("reddit.window_start")).alias("window_start"),
            coalesce(col("tmdb.window_end"), col("reddit.window_end")).alias("window_end"),
            coalesce(col("tmdb.movie_title"), col("reddit.movie_title")).alias("movie_title"),
            col("tmdb.movie_id"),
            coalesce(col("tmdb.avg_popularity"), lit(0.0)).alias("popularity"),
            coalesce(col("tmdb.avg_vote"), lit(0.0)).alias("vote_average"),
            coalesce(col("reddit.mentions_count"), lit(0)).alias("mentions_count"),
            coalesce(col("reddit.avg_sentiment"), lit(0.0)).alias("avg_sentiment"),
            coalesce(col("reddit.avg_reddit_score"), lit(0.0)).alias("avg_reddit_score")
        )
        
        # Normalize mentions_count (simple min-max scaling per batch)
        # In production, you'd use a more sophisticated approach
        joined_df = joined_df.withColumn(
            "mentions_rate",
            col("mentions_count").cast(FloatType())
        )
        
        # Compute TrendScore
        joined_df = joined_df.withColumn(
            "trend_score",
            (self.w1 * col("popularity")) +
            (self.w2 * col("mentions_rate") * 10) +  # Scale mentions
            (self.w3 * (col("avg_sentiment") + 1) * 50)  # Normalize sentiment from [-1,1] to [0,100]
        )
        
        # Add metadata
        joined_df = joined_df.withColumn("processed_time", current_timestamp())
        
        return joined_df
    
    def write_to_cassandra(self, df, table_name):
        """Write streaming DataFrame to Cassandra"""
        logger.info(f"Writing to Cassandra table: {table_name}")
        
        query = df.writeStream \
            .format("org.apache.spark.sql.cassandra") \
            .option("keyspace", self.cassandra_keyspace) \
            .option("table", table_name) \
            .option("checkpointLocation", f"/tmp/spark-checkpoint/{table_name}") \
            .outputMode("append")
        
        return query
    
    def write_to_kafka(self, df, topic):
        """Write streaming DataFrame to Kafka"""
        logger.info(f"Writing to Kafka topic: {topic}")
        
        from pyspark.sql.functions import to_json, struct
        
        # Convert to JSON
        json_df = df.select(
            to_json(struct("*")).alias("value")
        )
        
        query = json_df.writeStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", self.kafka_servers) \
            .option("topic", topic) \
            .option("checkpointLocation", f"/tmp/spark-checkpoint/{topic}") \
            .outputMode("append")
        
        return query
    
    def write_to_console(self, df, query_name="console"):
        """Write streaming DataFrame to console for debugging"""
        query = df.writeStream \
            .format("console") \
            .outputMode("append") \
            .option("truncate", False) \
            .queryName(query_name)
        
        return query
    
    def run(self):
        """Main processing loop"""
        logger.info("Starting Spark Streaming Processor...")
        
        try:
            # Read streams
            tmdb_stream = self.read_tmdb_stream()
            reddit_stream = self.read_reddit_stream()
            
            # Compute aggregates
            tmdb_agg = self.compute_tmdb_aggregates(tmdb_stream)
            reddit_agg = self.compute_reddit_aggregates(reddit_stream)
            
            # Join and compute TrendScore
            trend_df = self.join_and_compute_trendscore(tmdb_agg, reddit_agg)
            
            # Write to multiple sinks
            # 1. Cassandra
            cassandra_query = self.write_to_cassandra(trend_df, "movie_trends") \
                .start()
            
            # 2. Kafka (for ML service)
            kafka_query = self.write_to_kafka(trend_df, self.trend_topic) \
                .start()
            
            # 3. Console (for debugging)
            console_query = self.write_to_console(trend_df, "TrendScore") \
                .start()
            
            # Await termination
            logger.info("Streaming queries started. Waiting for termination...")
            self.spark.streams.awaitAnyTermination()
            
        except Exception as e:
            logger.error(f"Error in streaming processor: {e}")
            raise
        finally:
            if self.spark:
                self.spark.stop()
                logger.info("Spark session stopped")


if __name__ == "__main__":
    processor = SparkStreamingProcessor()
    processor.run()
