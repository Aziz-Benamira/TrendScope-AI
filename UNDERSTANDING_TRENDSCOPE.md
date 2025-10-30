# 🎓 Understanding TrendScope-AI: A Complete Walkthrough

**Created by GitHub Copilot for Aziz Benamira**  
**Date: October 30, 2025**

---

## 📚 Table of Contents

1. [Project Overview - What Is This?](#1-project-overview)
2. [The Big Picture - How It All Works](#2-the-big-picture)
3. [Layer 1: Data Ingestion (The Collectors)](#3-layer-1-data-ingestion)
4. [Layer 2: Stream Processing (The Processor)](#4-layer-2-stream-processing)
5. [Layer 3: Online Machine Learning (The Predictor)](#5-layer-3-online-machine-learning)
6. [Layer 4: Storage (The Memory)](#6-layer-4-storage)
7. [Layer 5: Monitoring (The Dashboard)](#7-layer-5-monitoring)
8. [How Everything Connects](#8-how-everything-connects)
9. [What Happens When You Start It](#9-what-happens-when-you-start)
10. [Understanding the Code](#10-understanding-the-code)

---

## 1. Project Overview - What Is This? 🎬

### **The Simple Explanation:**

TrendScope-AI is like a **real-time news feed for movie popularity**. It:

1. **Watches** TMDB (movie database) and Reddit discussions
2. **Analyzes** what people are saying about movies
3. **Predicts** which movies will trend next
4. **Shows** everything on live dashboards

### **Why This Matters:**

- Studios can see audience reactions in real-time
- You can predict box office trends before they happen
- It demonstrates modern Big Data & AI skills

### **Technologies Used:**

```
Data Sources:  TMDB API + Reddit API
Message Bus:   Apache Kafka (handles streaming data)
Processing:    Apache Spark (analyzes data in real-time)
ML Model:      River (learns and predicts continuously)
Storage:       Cassandra (stores results)
Monitoring:    Grafana + Prometheus + MLflow
```

---

## 2. The Big Picture - How It All Works 🏗️

### **The Data Journey:**

```
┌─────────────┐
│  TMDB API   │  "Avengers has 1000 votes, 8.5 rating"
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Kafka    │  ← Message broker (like a smart mailbox)
│  Topic 1    │
└──────┬──────┘
       │
       ▼              ┌─────────────┐
                      │ Reddit API  │  "People love Avengers!"
                      └──────┬──────┘
                             │
                             ▼
                      ┌─────────────┐
                      │    Kafka    │
                      │  Topic 2    │
                      └──────┬──────┘
                             │
       ┌─────────────────────┴─────────────────────┐
       ▼                                           ▼
┌─────────────────────────────────────────────────────┐
│            Apache Spark                             │
│  • Combines TMDB + Reddit data                      │
│  • Analyzes sentiment (is comment positive?)        │
│  • Calculates TrendScore                            │
└──────────────────┬──────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
┌─────────────┐         ┌─────────────┐
│  Cassandra  │         │    Kafka    │
│  Database   │         │  Topic 3    │
└─────────────┘         └──────┬──────┘
                               │
                               ▼
                        ┌─────────────┐
                        │ ML Service  │
                        │ (River)     │
                        │ Predicts!   │
                        └──────┬──────┘
                               │
                   ┌───────────┴────────────┐
                   ▼                        ▼
            ┌─────────────┐         ┌─────────────┐
            │  Cassandra  │         │   Grafana   │
            │ Predictions │         │  Dashboard  │
            └─────────────┘         └─────────────┘
```

### **Key Concept: Why Kafka?**

Think of Kafka as a **smart delivery service**:
- TMDB Producer puts movie data in mailbox #1
- Reddit Producer puts comments in mailbox #2
- Spark reads from both mailboxes
- ML Service reads from Spark's mailbox
- If something crashes, data is still safe in the mailbox!

---

## 3. Layer 1: Data Ingestion (The Collectors) 📥

### **3.1 TMDB Producer - Movie Data Collector**

**Location:** `producers/tmdb/tmdb_producer.py`

**What It Does:**
Every 5 minutes, it asks TMDB: "What movies are trending today?"

**The Code Explained:**

```python
def fetch_trending_movies(self):
    """Fetch trending movies from TMDB API"""
    
    # Build the URL with your API key
    url = f"{self.base_url}/trending/movie/day"
    params = {'api_key': self.api_key}
    
    # Make the HTTP request
    response = requests.get(url, params=params, timeout=10)
    
    # Get the JSON data
    data = response.json()
    movies = data.get('results', [])  # List of trending movies
    
    return movies
```

**Example Data It Gets:**

```json
{
  "id": 12345,
  "title": "Avengers: Endgame",
  "popularity": 156.789,
  "vote_average": 8.5,
  "vote_count": 25000,
  "overview": "The epic conclusion..."
}
```

**What It Does Next:**

```python
def publish_to_kafka(self, data):
    """Send the movie data to Kafka"""
    
    # Kafka producer sends data to 'tmdb_stream' topic
    self.producer.send(self.topic, value=data)
    
    # Now Spark can read this data!
```

### **3.2 Reddit Producer - Comment Collector**

**Location:** `producers/reddit/reddit_producer.py`

**What It Does:**
Watches r/movies subreddit 24/7, capturing every comment about movies.

**The Code Explained:**

```python
def stream_comments(self):
    """Stream comments from r/movies in real-time"""
    
    subreddit = self.reddit.subreddit('movies')
    
    # This runs forever, watching for new comments
    for comment in subreddit.stream.comments(skip_existing=True):
        
        # Extract text
        text = comment.body
        
        # Find movie mentions (e.g., "I loved Avengers!")
        movie_mentions = self.extract_movie_mentions(text)
        
        # Package the data
        data = {
            'text': text,
            'movie_mentions': movie_mentions,
            'score': comment.score,  # Upvotes
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Send to Kafka
        self.publish_to_kafka(data)
```

**Example Comment Data:**

```json
{
  "text": "Just watched Avengers Endgame. Best movie ever!",
  "movie_mentions": ["Avengers Endgame"],
  "score": 42,
  "timestamp": "2025-10-30T14:30:00Z"
}
```

---

## 4. Layer 2: Stream Processing (The Processor) ⚙️

### **4.1 Spark Streaming - The Brain**

**Location:** `processors/spark_streaming_processor.py`

**What It Does:**
1. Reads data from both Kafka topics (TMDB + Reddit)
2. Analyzes sentiment of comments
3. Combines data by movie title
4. Calculates TrendScore

**The Sentiment Analysis Code:**

```python
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

def create_sentiment_udf(self):
    """Analyze if comment is positive, negative, or neutral"""
    
    analyzer = SentimentIntensityAnalyzer()
    
    def analyze_sentiment(text):
        # VADER gives scores: negative, neutral, positive, compound
        scores = analyzer.polarity_scores(text)
        
        # Compound score: -1 (very negative) to +1 (very positive)
        return float(scores['compound'])
    
    return udf(analyze_sentiment, FloatType())
```

**Example:**
```
Text: "Best movie ever!"        → Sentiment: +0.85 (very positive)
Text: "Terrible waste of time"  → Sentiment: -0.75 (very negative)
Text: "It was okay"             → Sentiment: +0.10 (slightly positive)
```

### **4.2 The TrendScore Formula**

**This is the heart of the system!**

```python
# TrendScore combines 3 signals:
TrendScore = (w1 × Popularity) + (w2 × Mentions × 10) + (w3 × (Sentiment + 1) × 50)

# Where:
w1 = 0.4  # Weight for TMDB popularity (40% importance)
w2 = 0.3  # Weight for Reddit mentions (30% importance)
w3 = 0.3  # Weight for sentiment (30% importance)
```

**Example Calculation:**

```python
Movie: "Avengers Endgame"
├── Popularity (TMDB):     156.78
├── Mentions (Reddit):     50 comments
└── Sentiment (Reddit):    +0.65 (positive)

TrendScore = (0.4 × 156.78) + (0.3 × 50 × 10) + (0.3 × (0.65 + 1) × 50)
           = 62.71 + 150 + 24.75
           = 237.46  ← High trend score! 🔥
```

### **4.3 Windowed Aggregation - Time Windows**

```python
# Instead of processing ALL data at once, we use windows
aggregated_df = df.groupBy(
    window(col("event_time"), "5 minutes", "1 minute"),  # 5-min windows, sliding every 1 min
    col("movie_title")
).agg(
    count("*").alias("mentions_count"),          # How many mentions?
    avg("sentiment_score").alias("avg_sentiment") # Average sentiment?
)
```

**Visual Example:**

```
Time:    14:00  14:01  14:02  14:03  14:04  14:05  14:06
         ├──────┴──────┴──────┴──────┴──────┤
         Window 1: 14:00-14:05 (50 mentions)
                ├──────┴──────┴──────┴──────┴──────┤
                Window 2: 14:01-14:06 (48 mentions)
```

This allows us to see **trends over time**, not just snapshots!

---

## 5. Layer 3: Online Machine Learning (The Predictor) 🤖

### **5.1 River ML Service - Continuous Learning**

**Location:** `ml_service/online_ml_service.py`

**What Is "Online Learning"?**

Traditional ML:
```
1. Collect 1 million records
2. Train model (takes hours)
3. Deploy model
4. Model is now frozen
```

Online ML (River):
```
1. Process record #1 → Make prediction → Learn from it
2. Process record #2 → Make prediction → Learn from it
3. Process record #3 → Make prediction → Learn from it
   (Continues forever, always improving!)
```

**The Model Code:**

```python
from river import linear_model, preprocessing, compose

# Create a pipeline (like a factory assembly line)
self.model = compose.Pipeline(
    # Step 1: Normalize features (make all numbers similar scale)
    preprocessing.StandardScaler(),
    
    # Step 2: Linear regression (find relationship between features and trend)
    linear_model.LinearRegression(
        optimizer=optim.SGD(0.01),  # Learning rate
        l2=0.001                     # Regularization (prevent overfitting)
    )
)
```

### **5.2 Feature Engineering - Making Predictions Smart**

```python
def extract_features(self, data, movie_title):
    """Convert raw data into features the model can use"""
    
    features = {
        # Current metrics
        'popularity': data.get('popularity'),
        'mentions_count': data.get('mentions_count'),
        'avg_sentiment': data.get('avg_sentiment'),
        
        # Time features (patterns differ by hour/day)
        'hour': datetime.now().hour,              # 0-23
        'day_of_week': datetime.now().weekday(),  # 0=Monday, 6=Sunday
        
        # Change features (is it growing or declining?)
        'delta_mentions': current_mentions - previous_mentions,
        'delta_sentiment': current_sentiment - previous_sentiment,
        
        # Moving averages (smooth out noise)
        'ma_mentions': average_of_last_5_windows
    }
    
    return features
```

**Example Features for "Avengers":**

```python
{
    'popularity': 156.78,
    'mentions_count': 50,
    'avg_sentiment': 0.65,
    'hour': 14,              # 2 PM
    'day_of_week': 5,        # Saturday
    'delta_mentions': +10,   # 10 more mentions than last window
    'delta_sentiment': +0.2, # Sentiment improved
    'ma_mentions': 45.5      # Average of last 5 windows
}
```

### **5.3 The Prediction Process**

```python
# Step 1: Get current TrendScore
current_trend_score = 237.46

# Step 2: Extract features
features = extract_features(data, "Avengers")

# Step 3: Predict NEXT window's TrendScore
predicted_score = self.model.predict_one(features)
# Result: 245.12 (predicting it will go up!)

# Step 4: Calculate error (when next window arrives)
actual_score = 242.50  # What actually happened
error = abs(predicted_score - actual_score)
# Error: 2.62

# Step 5: Learn from this error
self.model.learn_one(features, actual_score)
# Model now knows: "I was a bit too optimistic, adjust weights"
```

---

## 6. Layer 4: Storage (The Memory) 💾

### **6.1 Cassandra Database - Why Cassandra?**

**Traditional Database (MySQL):**
```
Good for: Bank accounts, user profiles
Bad for: Billions of time-series records
```

**Cassandra:**
```
Good for: Time-series data, high-write volume, distributed
Perfect for: Movie trends over time!
```

### **6.2 The Schema**

**Table 1: movie_trends**

```cql
CREATE TABLE movie_trends (
    movie_title TEXT,           -- Partition key (distributes data)
    window_start TIMESTAMP,     -- Clustering key (sorts data)
    window_end TIMESTAMP,
    popularity FLOAT,
    mentions_count INT,
    avg_sentiment FLOAT,
    trend_score FLOAT,
    PRIMARY KEY ((movie_title), window_start)
) WITH CLUSTERING ORDER BY (window_start DESC);
```

**Why This Design?**

```
Query: "Show me Avengers trends from last 24 hours"

Cassandra:
1. Finds partition "Avengers" (fast - uses hash)
2. Reads timestamps in DESC order (already sorted!)
3. Returns results instantly

Traditional DB would scan entire table - SLOW!
```

**Example Data:**

```
movie_title    | window_start        | trend_score | mentions | sentiment
---------------|---------------------|-------------|----------|----------
Avengers       | 2025-10-30 14:05:00 | 237.46     | 50       | 0.65
Avengers       | 2025-10-30 14:00:00 | 225.30     | 40       | 0.58
Avengers       | 2025-10-30 13:55:00 | 220.15     | 38       | 0.60
```

**Table 2: predictions**

```cql
CREATE TABLE predictions (
    movie_title TEXT,
    timestamp TIMESTAMP,
    actual_trend_score FLOAT,
    predicted_trend_score FLOAT,
    prediction_error FLOAT,
    model_version TEXT,
    PRIMARY KEY ((movie_title), timestamp)
);
```

This stores every prediction to track model performance!

---

## 7. Layer 5: Monitoring (The Dashboard) 📊

### **7.1 Prometheus - Metrics Collector**

**What It Does:**
Every 15 seconds, Prometheus asks services: "How are you doing?"

**Metrics Exposed by ML Service:**

```python
from prometheus_client import Counter, Gauge, Histogram

# Counter: Only goes up (total predictions made)
predictions_counter = Counter('ml_predictions_total', 'Total predictions')

# Gauge: Goes up/down (current error rate)
mae_gauge = Gauge('ml_mae', 'Mean Absolute Error')

# Histogram: Tracks distribution (how long predictions take)
prediction_time = Histogram('ml_prediction_seconds', 'Prediction time')
```

**In the Code:**

```python
# Increment counter
predictions_counter.inc()

# Update gauge
mae_gauge.set(5.23)  # Current MAE is 5.23

# Time an operation
with prediction_time.time():
    prediction = model.predict(features)
```

### **7.2 Grafana - Visualization**

**What It Does:**
Queries Prometheus and creates beautiful dashboards.

**Example Query:**

```promql
# Show prediction rate per minute
rate(ml_predictions_total[1m])

# Show average MAE over 5 minutes
avg_over_time(ml_mae[5m])

# Show 95th percentile of prediction latency
histogram_quantile(0.95, ml_prediction_seconds_bucket)
```

### **7.3 MLflow - Experiment Tracking**

**What It Does:**
Records every experiment so you can compare models.

```python
import mlflow

# Start tracking
mlflow.start_run(run_name="online_learning_v1")

# Log parameters
mlflow.log_param("learning_rate", 0.01)
mlflow.log_param("model_type", "Linear Regression")

# Log metrics (every 100 predictions)
mlflow.log_metric("mae", 5.23, step=100)
mlflow.log_metric("rmse", 7.45, step=100)

# Later: Compare this run vs others in MLflow UI!
```

---

## 8. How Everything Connects 🔗

### **8.1 Docker Compose - The Orchestrator**

**What Is Docker Compose?**

Think of it as a **recipe book for services**:

```yaml
# docker-compose.yml (simplified)

services:
  # Service 1: Kafka message broker
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
  
  # Service 2: TMDB Producer
  tmdb-producer:
    build: ./producers/tmdb
    depends_on:
      - kafka  # Wait for Kafka to start first!
    environment:
      TMDB_API_KEY: ${TMDB_API_KEY}  # From .env file
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
  
  # Service 3: Spark Processor
  spark-processor:
    build: ./processors
    depends_on:
      - kafka
      - cassandra
    environment:
      SPARK_MASTER_URL: spark://spark-master:7077
```

**When you run `docker-compose up -d`:**

1. Docker reads this file
2. Creates virtual network for all services
3. Starts services in correct order (dependencies first)
4. Each service can talk to others by name (e.g., `kafka:9092`)

### **8.2 Environment Variables - Configuration**

**The .env File:**

```env
# API Keys
TMDB_API_KEY=your_key_here
REDDIT_CLIENT_ID=your_id_here

# Kafka Topics
KAFKA_TOPIC_TMDB=tmdb_stream
KAFKA_TOPIC_REDDIT=reddit_stream

# TrendScore Weights
W1_POPULARITY=0.4
W2_MENTIONS=0.3
W3_SENTIMENT=0.3
```

**How Services Read It:**

```python
import os

# Get API key from environment
api_key = os.getenv('TMDB_API_KEY')

# Get TrendScore weights
w1 = float(os.getenv('W1_POPULARITY', 0.4))  # Default: 0.4
w2 = float(os.getenv('W2_MENTIONS', 0.3))
w3 = float(os.getenv('W3_SENTIMENT', 0.3))
```

**Why This Is Good:**
- ✅ Keep secrets out of code
- ✅ Change settings without editing code
- ✅ Different settings for dev/production

---

## 9. What Happens When You Start It 🚀

### **Minute-by-Minute Breakdown:**

**Minute 0-1: Infrastructure Startup**

```bash
$ docker-compose up -d

Starting zookeeper ... done
Starting kafka ... done
Starting cassandra ... done
```

**Minute 1-2: Schema Initialization**

```bash
# Cassandra creates tables
CREATE KEYSPACE trendscope;
CREATE TABLE movie_trends (...);
CREATE TABLE predictions (...);
```

**Minute 2-3: Supporting Services**

```bash
Starting spark-master ... done
Starting spark-worker ... done
Starting mlflow ... done
Starting prometheus ... done
Starting grafana ... done
```

**Minute 3-5: Data Producers Start**

```bash
Starting tmdb-producer ... done
Starting reddit-producer ... done

# TMDB Producer logs:
✅ Connected to Kafka at kafka:9092
✅ Fetched 20 trending movies
✅ Published to topic 'tmdb_stream'

# Reddit Producer logs:
✅ Connected to Reddit API
✅ Streaming comments from r/movies
```

**Minute 5-10: Processing Begins**

```bash
Starting spark-processor ... done

# Spark logs:
✅ Reading from tmdb_stream
✅ Reading from reddit_stream
✅ Computed TrendScore for 'Avengers': 237.46
✅ Written to Cassandra
✅ Published to trend_stream
```

**Minute 10+: ML Predictions**

```bash
Starting ml-service ... done

# ML Service logs:
✅ Consumed trend_stream
✅ Extracted 12 features
✅ Predicted TrendScore: 245.12
✅ Actual TrendScore: 242.50
✅ Error: 2.62, MAE: 5.23
✅ Model updated
```

**Minute 15+: Dashboards Live**

```
Grafana:     http://localhost:3000
└── Shows: Predictions/min, MAE trend, top movies

MLflow:      http://localhost:5000
└── Shows: Experiment runs, metrics over time

Prometheus:  http://localhost:9090
└── Shows: Raw metrics, service health
```

---

## 10. Understanding the Code 💻

### **10.1 Common Patterns**

**Pattern 1: Retry Logic**

```python
def _connect_kafka(self):
    """Connect to Kafka with automatic retries"""
    
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            self.producer = KafkaProducer(...)
            logger.info("✅ Connected to Kafka")
            return  # Success!
            
        except KafkaError as e:
            retry_count += 1
            logger.warning(f"⚠️ Retry {retry_count}/{max_retries}")
            time.sleep(5)  # Wait before retry
    
    # All retries failed
    raise Exception("Could not connect after 5 tries")
```

**Why?** Services start at different times. Retries handle the race condition.

**Pattern 2: Structured Logging**

```python
import colorlog

# Configure colored logging
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(levelname)s - %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
    }
))

logger = colorlog.getLogger('MyService')
logger.addHandler(handler)

# Use it
logger.info("✅ Service started")      # Green
logger.warning("⚠️ Rate limit hit")    # Yellow
logger.error("❌ Connection failed")   # Red
```

**Why?** Easy to spot problems in logs!

**Pattern 3: Context Managers**

```python
# Bad way:
start = time.time()
result = model.predict(features)
duration = time.time() - start
prediction_time.observe(duration)

# Good way (with context manager):
with prediction_time.time():
    result = model.predict(features)
    # Automatically measures time!
```

### **10.2 Key Files Explained**

**File: `docker-compose.yml`**
- **What**: Recipe for all 12 services
- **Key Parts**: Service definitions, dependencies, ports, environment variables
- **When Changed**: When adding new services or changing ports

**File: `requirements.txt`**
- **What**: List of Python libraries needed
- **Key Parts**: `kafka-python`, `pyspark`, `river`, `mlflow`
- **When Changed**: When adding new Python dependencies

**File: `.env`**
- **What**: Configuration and secrets
- **Key Parts**: API keys, TrendScore weights, intervals
- **When Changed**: When adjusting system behavior

**File: `producers/tmdb/tmdb_producer.py`**
- **What**: Fetches movie data from TMDB
- **Key Parts**: API calls, Kafka publishing, retry logic
- **When Changed**: To add more movie metadata

**File: `processors/spark_streaming_processor.py`**
- **What**: Processes streams and computes TrendScore
- **Key Parts**: Stream joins, sentiment analysis, TrendScore formula
- **When Changed**: To adjust TrendScore weights or add features

**File: `ml_service/online_ml_service.py`**
- **What**: Makes predictions using online learning
- **Key Parts**: Feature engineering, model updates, metrics tracking
- **When Changed**: To add new features or change ML algorithm

---

## 🎯 Summary: The 5-Minute Explanation

**What TrendScope Does:**

1. **Collects** movie data (TMDB) and discussions (Reddit)
2. **Streams** data through Kafka (message broker)
3. **Analyzes** sentiment and computes TrendScore (Spark)
4. **Predicts** future trends (River ML)
5. **Stores** results (Cassandra)
6. **Visualizes** everything (Grafana dashboards)

**The Data Flow:**

```
APIs → Kafka → Spark → Cassandra
                 ↓
              Kafka → ML Service → Cassandra → Grafana
                                      ↓
                                  Prometheus
```

**Why Each Technology:**

- **Kafka**: Handle millions of messages, never lose data
- **Spark**: Process streams in real-time, parallel computing
- **Cassandra**: Store time-series data efficiently
- **River**: Learn continuously without retraining
- **Docker**: Package everything, run anywhere

**The Magic:**

Instead of analyzing movies once a day (batch), we analyze **every second**. Instead of training a model once a month, we **learn from every data point**. This is **real-time Big Data and MLOps** in action!

---

## 🚀 Ready to Launch?

Now that you understand how it all works:

1. ✅ API keys tested
2. ✅ Architecture understood
3. ✅ Code explained
4. ⏳ Ready to launch!

**Next Command:**

```powershell
docker-compose up -d
```

**Then watch the magic happen:**

```powershell
# See services start
docker-compose ps

# Watch the logs
docker-compose logs -f

# Open dashboards
# Grafana: http://localhost:3000
```

---

**Questions?** Check:
- `README.md` - Overview and quick start
- `docs/ARCHITECTURE.md` - Deep technical details
- `GETTING_STARTED.md` - Step-by-step launch guide

**You're ready! 🎬🚀**

---

*This guide was created to help you understand every piece before launching. Take your time, re-read sections, and experiment!*
