# 📊 TrendScope-AI - Architecture Deep Dive

## System Overview

TrendScope-AI implements a **Lambda Architecture** variant optimized for real-time streaming:

- **Speed Layer**: Real-time stream processing (Kafka + Spark Streaming)
- **Serving Layer**: Query interface (Cassandra)
- **ML Layer**: Online learning and prediction (River)
- **Monitoring Layer**: Observability and MLOps (Prometheus, Grafana, MLflow, Evidently)

---

## Data Flow

### 1. Ingestion Phase

```
TMDB API → TMDB Producer → Kafka (tmdb_stream)
                              ↓
                         Spark Consumer

Reddit API → Reddit Producer → Kafka (reddit_stream)
                                  ↓
                             Spark Consumer
```

**Key Design Decisions:**

- **Kafka as Message Bus**: Decouples producers from consumers, enables replay
- **Separate Topics**: Allows independent scaling and processing
- **JSON Serialization**: Human-readable, schema flexibility

### 2. Processing Phase

```
Spark Structured Streaming:
├── Parse JSON from Kafka
├── Apply transformations
│   ├── Sentiment Analysis (VADER)
│   ├── Movie mention extraction
│   └── Data cleaning
├── Windowed Aggregations
│   ├── Window: 5 minutes
│   ├── Slide: 1 minute
│   └── Watermark: 10 minutes (handle late data)
├── Stream Join
│   ├── Join key: movie_title + window
│   ├── Type: Full outer join
│   └── Handle missing data with coalesce
└── Compute TrendScore
    └── Formula: w1×Pop + w2×Mentions + w3×Sentiment
```

**Key Design Decisions:**

- **Structured Streaming**: Exactly-once semantics, fault tolerance
- **Windowed Joins**: Handle temporal alignment of data streams
- **Watermarking**: Balance latency vs completeness for late arrivals

### 3. TrendScore Formula

```
TrendScore(t) = w₁ × Popularity(t) 
              + w₂ × MentionsRate(t) × 10
              + w₃ × (Sentiment(t) + 1) × 50

Where:
- w₁ = 0.4 (TMDB popularity weight)
- w₂ = 0.3 (Reddit mentions weight)
- w₃ = 0.3 (Sentiment weight)
- Popularity: TMDB metric [0, ∞)
- MentionsRate: Count per window [0, ∞)
- Sentiment: VADER compound score [-1, 1]
```

**Normalization Strategy:**

- Mentions scaled by 10x to match popularity magnitude
- Sentiment shifted from [-1,1] to [0,100] range
- Final TrendScore typically ranges [0, 200]

### 4. ML Prediction Phase

```
River Online Learning Pipeline:
├── Feature Engineering
│   ├── Current metrics (popularity, sentiment, mentions)
│   ├── Temporal features (hour, day_of_week)
│   ├── Delta features (Δmentions, Δsentiment)
│   └── Moving averages (MA5)
├── Scaling
│   └── StandardScaler (online mean/variance estimation)
├── Model
│   └── Linear Regression (SGD optimizer, L2 regularization)
└── Metrics Tracking
    ├── MAE (Mean Absolute Error)
    ├── RMSE (Root Mean Square Error)
    └── R² (Coefficient of Determination)
```

**Key Design Decisions:**

- **Online Learning**: Model updates with every observation
- **Feature History**: Maintains per-movie circular buffer (size: 100)
- **Incremental Scaling**: No batch retraining required
- **L2 Regularization**: Prevents overfitting with coefficient penalty

---

## Storage Architecture

### Cassandra Schema Design

**movie_trends table:**
```cql
PRIMARY KEY ((movie_title), window_start)
CLUSTERING ORDER BY (window_start DESC)
```

- **Partition key**: movie_title (distributes data across nodes)
- **Clustering key**: window_start (orders data within partition)
- **Query pattern**: "Get recent trends for movie X"

**predictions table:**
```cql
PRIMARY KEY ((movie_title), timestamp)
CLUSTERING ORDER BY (timestamp DESC)
```

- **Partition key**: movie_title
- **Clustering key**: timestamp
- **Query pattern**: "Get prediction history for movie X"

**Design Rationale:**

- Wide partition strategy (movie as partition key)
- Time-series optimized (descending timestamp order)
- Efficient range queries on recent data
- No joins required (denormalized)

---

## Monitoring Architecture

### Metrics Collection

```
ML Service → Prometheus Client (Port 8000)
                ↓
            Prometheus Scraper (15s interval)
                ↓
            Prometheus TSDB
                ↓
            Grafana Queries
```

**Collected Metrics:**

- **Counters**: `ml_predictions_total`
- **Gauges**: `ml_mae`, `ml_rmse`
- **Histograms**: `ml_prediction_seconds`, `ml_update_seconds`

### MLflow Tracking

```
ML Service → MLflow Tracking Server (Port 5000)
                ↓
            SQLite Backend Store
                ↓
            MLflow UI
```

**Tracked Artifacts:**

- Parameters: learning_rate, model_version
- Metrics: MAE, RMSE, R² (logged every 100 predictions)
- Tags: model_type, experiment_name

### Drift Detection

```
Cassandra → Drift Detection Service
    ↓
Evidently Reports (HTML)
    ↓
Reference Window (24h ago) vs Current Window (1h)
```

**Detected Drifts:**

- Feature drift (popularity, sentiment, mentions distribution)
- Prediction drift (error distribution changes)
- Data quality issues (missing values, outliers)

---

## Scalability Considerations

### Horizontal Scaling

**Kafka:**
- Partition topics (e.g., 3 partitions per topic)
- Add more brokers for increased throughput

**Spark:**
- Add worker nodes
- Increase executor memory/cores
- Tune `spark.streaming.kafka.maxRatePerPartition`

**Cassandra:**
- Add nodes to cluster
- Replication factor = 3 for production
- Partition by high-cardinality keys

**ML Service:**
- Deploy multiple instances with consumer groups
- Each instance processes different partitions

### Vertical Scaling

**Memory:**
- Spark: Increase executor/driver memory
- Kafka: Increase heap size for broker
- Cassandra: Increase heap for JVM

**CPU:**
- More cores → more parallelism
- Tune Spark executor cores
- Increase Kafka threads

---

## Fault Tolerance

### Data Layer

- **Kafka**: Replication factor, ISR (In-Sync Replicas)
- **Cassandra**: Distributed, no SPOF
- **Spark**: Checkpointing for stateful operations

### Processing Layer

- **Exactly-once semantics**: Kafka + Spark idempotent writes
- **Watermarking**: Handle late data gracefully
- **Checkpoints**: Resume from last processed offset

### ML Layer

- **Model persistence**: MLflow artifacts
- **Metric recovery**: Prometheus retention
- **Consumer groups**: Automatic partition reassignment

---

## Performance Tuning

### Kafka

```env
KAFKA_NUM_PARTITIONS=3
KAFKA_REPLICATION_FACTOR=1
KAFKA_LOG_RETENTION_HOURS=24
```

### Spark

```python
spark.conf.set("spark.sql.shuffle.partitions", "10")
spark.conf.set("spark.streaming.kafka.maxRatePerPartition", "100")
spark.conf.set("spark.sql.streaming.stateStore.maintenanceInterval", "60s")
```

### Cassandra

```cql
ALTER TABLE movie_trends WITH compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_size': '1',
    'compaction_window_unit': 'DAYS'
};
```

---

## Security Considerations

### API Security

- Store credentials in environment variables
- Use OAuth2 for Reddit (more secure than password auth)
- Rotate API keys periodically

### Network Security

- Docker network isolation
- Expose only necessary ports
- Use TLS for production (not in dev setup)

### Data Security

- No PII collection from Reddit (usernames anonymizable)
- Cassandra authentication (disabled in dev)
- Grafana admin password change required

---

## Future Enhancements

1. **HDFS Integration**: Long-term storage for raw data
2. **Kubernetes Deployment**: Replace Docker Compose for production
3. **Advanced Features**: Movie embeddings, graph analysis
4. **Real-time Alerting**: Webhook notifications for trending spikes
5. **A/B Testing**: Model version comparison
6. **AutoML**: Hyperparameter tuning with Optuna

---

**For implementation details, see the source code and inline documentation.**
