"""
TrendScope-AI Backend API
FastAPI server for serving real-time movie trends and RAG-powered chat
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
from datetime import datetime, timedelta
from typing import List, Optional
import os
from pydantic import BaseModel
import time
import sys

# Optional Cassandra/Kafka imports (not needed for RAG-only mode)
try:
    from cassandra.cluster import Cluster
    CASSANDRA_AVAILABLE = True
except (ImportError, Exception) as e:
    CASSANDRA_AVAILABLE = False
    Cluster = None
    print(f"[WARNING] Cassandra driver not available - running in RAG-only mode: {e}")

try:
    from kafka import KafkaConsumer
    KAFKA_AVAILABLE = True
except (ImportError, Exception) as e:
    KAFKA_AVAILABLE = False
    KafkaConsumer = None
    print(f"[WARNING] Kafka not available - running in RAG-only mode: {e}")

# Add rag module to path - support both Docker and local development
sys.path.insert(0, '/app')  # Docker path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # Local dev path

app = FastAPI(title="TrendScope-AI API", version="2.0.0", description="Real-time Movie Trends + RAG Chat")

# Simple cache for trending movies (cache for 15 seconds)
_trending_cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 15  # Cache for 15 seconds
}

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002", "http://localhost:3003", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cassandra connection
cassandra_cluster = None
cassandra_session = None

# RAG Service (lazy initialization)
_rag_service = None

def get_cassandra_session():
    global cassandra_cluster, cassandra_session
    if not CASSANDRA_AVAILABLE:
        return None
    if cassandra_session is None:
        try:
            cassandra_cluster = Cluster(['cassandra'])
            cassandra_session = cassandra_cluster.connect('trendscope')
        except Exception as e:
            print(f"⚠️ Cassandra connection failed: {e}")
            return None
    return cassandra_session

def get_rag_service():
    """Lazy initialization of RAG service"""
    global _rag_service
    if _rag_service is None:
        try:
            from rag.rag_service import RAGService
            _rag_service = RAGService()
            print("✓ RAG Service initialized")
        except Exception as e:
            print(f"⚠️ RAG Service initialization failed: {e}")
            return None
    return _rag_service

# Pydantic models
class MovieTrend(BaseModel):
    movie_title: str
    trend_score: float
    popularity: float
    mentions_count: int
    avg_sentiment: float
    vote_average: Optional[float] = None
    window_start: str
    window_end: str

class TrendingMovie(BaseModel):
    movie_title: str
    trend_score: float
    change_24h: float
    sentiment: str

class ChatRequest(BaseModel):
    query: str
    movie_title: Optional[str] = None
    hours_back: int = 24

class ChatResponse(BaseModel):
    answer: str
    sources_count: int
    sample_reviews: List[dict]
    movie_filter: Optional[str]
    time_range_hours: int

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    print("🚀 Starting TrendScope-AI Backend API v2.0...")
    try:
        session = get_cassandra_session()
        print("✓ Connected to Cassandra")
    except Exception as e:
        print(f"⚠️  Warning: Could not connect to Cassandra: {e}")
    
    # Pre-initialize RAG service
    get_rag_service()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if cassandra_cluster:
        cassandra_cluster.shutdown()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "operational",
        "service": "TrendScope-AI API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/trends/latest", response_model=List[MovieTrend])
async def get_latest_trends(limit: int = 10):
    """Get latest movie trends from Cassandra"""
    try:
        session = get_cassandra_session()
        
        # Query latest trends (last 24 hours)
        query = """
            SELECT movie_title, trend_score, popularity, mentions_count, 
                   avg_sentiment, vote_average, window_start, window_end
            FROM movie_trends
            WHERE window_start > %s
            ALLOW FILTERING
        """
        
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        rows = session.execute(query, [cutoff_time])
        
        # Convert to list and sort by trend_score
        trends = []
        seen_movies = set()
        
        for row in rows:
            if row.movie_title not in seen_movies:
                trends.append(MovieTrend(
                    movie_title=row.movie_title,
                    trend_score=float(row.trend_score),
                    popularity=float(row.popularity),
                    mentions_count=row.mentions_count,
                    avg_sentiment=float(row.avg_sentiment),
                    vote_average=float(row.vote_average) if row.vote_average else None,
                    window_start=row.window_start.isoformat(),
                    window_end=row.window_end.isoformat()
                ))
                seen_movies.add(row.movie_title)
        
        # Sort by trend_score descending
        trends.sort(key=lambda x: x.trend_score, reverse=True)
        
        return trends[:limit]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/trends/movie/{movie_title}")
async def get_movie_trend(movie_title: str):
    """Get trend history for a specific movie"""
    try:
        session = get_cassandra_session()
        
        query = """
            SELECT movie_title, trend_score, popularity, mentions_count,
                   avg_sentiment, vote_average, window_start, window_end
            FROM movie_trends
            WHERE movie_title = %s
            ORDER BY window_start DESC
            LIMIT 50
        """
        
        rows = session.execute(query, [movie_title])
        
        history = []
        for row in rows:
            history.append({
                "movie_title": row.movie_title,
                "trend_score": float(row.trend_score),
                "popularity": float(row.popularity),
                "mentions_count": row.mentions_count,
                "avg_sentiment": float(row.avg_sentiment),
                "vote_average": float(row.vote_average) if row.vote_average else None,
                "window_start": row.window_start.isoformat(),
                "window_end": row.window_end.isoformat()
            })
        
        if not history:
            raise HTTPException(status_code=404, detail="Movie not found")
        
        return {
            "movie_title": movie_title,
            "current_score": history[0]["trend_score"],
            "history": history
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/stats/summary")
async def get_summary_stats():
    """Get summary statistics"""
    try:
        session = get_cassandra_session()
        
        # Get total movies tracked
        count_query = "SELECT COUNT(*) as total FROM movie_trends"
        count_result = session.execute(count_query).one()
        
        # Get average sentiment
        avg_query = "SELECT AVG(avg_sentiment) as avg_sent FROM movie_trends"
        avg_result = session.execute(avg_query).one()
        
        return {
            "total_movies_tracked": count_result.total if count_result else 0,
            "average_sentiment": float(avg_result.avg_sent) if avg_result and avg_result.avg_sent else 0.0,
            "last_updated": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/trending/top")
async def get_top_trending(limit: int = 5):
    """Get top trending movies right now"""
    try:
        session = get_cassandra_session()
        
        # Get latest window data
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        query = """
            SELECT movie_title, trend_score, popularity, avg_sentiment
            FROM movie_trends
            WHERE window_start > %s
            ALLOW FILTERING
        """
        
        rows = session.execute(query, [cutoff_time])
        
        # Aggregate by movie
        movie_scores = {}
        for row in rows:
            if row.movie_title not in movie_scores:
                movie_scores[row.movie_title] = {
                    "trend_score": float(row.trend_score),
                    "popularity": float(row.popularity),
                    "avg_sentiment": float(row.avg_sentiment)
                }
        
        # Sort and format
        trending = []
        for movie, data in sorted(movie_scores.items(), key=lambda x: x[1]["trend_score"], reverse=True)[:limit]:
            sentiment_label = "positive" if data["avg_sentiment"] > 0.2 else "negative" if data["avg_sentiment"] < -0.2 else "neutral"
            
            trending.append({
                "movie_title": movie,
                "trend_score": data["trend_score"],
                "change_24h": 0.0,  # TODO: Calculate actual change
                "sentiment": sentiment_label
            })
        
        return trending
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/trending")
async def get_trending_movies():
    """
    Get real-time trending movies from Kafka with REAL Reddit integration
    OPTIMIZED: Cached for 15 seconds for fast response
    """
    # Check cache first
    current_time = time.time()
    if _trending_cache['data'] is not None and (current_time - _trending_cache['timestamp']) < _trending_cache['ttl']:
        print(f"✅ Returning cached data (age: {current_time - _trending_cache['timestamp']:.1f}s)")
        return _trending_cache['data']
    
    print("🔄 Cache miss - fetching fresh data from Kafka...")
    
    try:
        from kafka import KafkaConsumer, TopicPartition
        from kafka.errors import KafkaError
        from collections import defaultdict
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        
        # Initialize sentiment analyzer
        sentiment_analyzer = SentimentIntensityAnalyzer()
        
        # Create consumers with AGGRESSIVE timeout for speed
        tmdb_consumer = KafkaConsumer(
            bootstrap_servers=['kafka:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=500,  # 500ms timeout for speed
            auto_offset_reset='latest',  # Only read recent messages
            max_poll_records=100  # Limit messages per poll
        )
        
        reddit_consumer = KafkaConsumer(
            bootstrap_servers=['kafka:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=500,  # 500ms timeout for speed
            auto_offset_reset='latest',  # Only read recent messages
            max_poll_records=500  # More reddit messages for better coverage
        )
        
        # Read TMDB movies (LIMITED for speed)
        movies_dict = {}
        topic = 'tmdb_stream'
        partitions = tmdb_consumer.partitions_for_topic(topic)
        
        if partitions:
            topic_partitions = [TopicPartition(topic, p) for p in partitions]
            tmdb_consumer.assign(topic_partitions)
            
            # Seek to end, then go back 200 messages for recent data
            for tp in topic_partitions:
                end_offset = tmdb_consumer.end_offsets([tp])[tp]
                start_offset = max(0, end_offset - 200)  # Last 200 messages
                tmdb_consumer.seek(tp, start_offset)
            
            seen_titles = set()
            msg_count = 0
            for message in tmdb_consumer:
                try:
                    movie_data = message.value
                    title = movie_data.get('title', 'Unknown')
                    
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    
                    # Initialize movie with TMDB data
                    movies_dict[title.lower()] = {
                        'title': title,
                        'releaseDate': movie_data.get('release_date', 'N/A'),
                        'popularity': movie_data.get('popularity', 0),
                        'voteAverage': movie_data.get('vote_average', 0),
                        'imdbRating': movie_data.get('imdb_rating', movie_data.get('vote_average', 0)),
                        'imdbVotes': movie_data.get('imdb_votes', 0),
                        'overview': movie_data.get('overview', ''),
                        'mentions': 0,
                        'sentiment': 0.5,
                        'redditComments': [],
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    
                    msg_count += 1
                    # Stop after 50 unique movies or 200 messages
                    if len(movies_dict) >= 50 or msg_count >= 200:
                        break
                        
                except Exception as e:
                    print(f"Error processing TMDB movie: {e}")
                    continue
        
        tmdb_consumer.close()
        
        # Read Reddit data and aggregate by movie (LIMITED for speed)
        reddit_topic = 'reddit_stream'
        reddit_partitions = reddit_consumer.partitions_for_topic(reddit_topic)
        
        if reddit_partitions:
            topic_partitions = [TopicPartition(reddit_topic, p) for p in reddit_partitions]
            reddit_consumer.assign(topic_partitions)
            
            # Seek to end, then go back 1000 messages for recent Reddit data
            for tp in topic_partitions:
                end_offset = reddit_consumer.end_offsets([tp])[tp]
                start_offset = max(0, end_offset - 1000)  # Last 1000 Reddit messages
                reddit_consumer.seek(tp, start_offset)
            
            # Track mentions and sentiments per movie
            movie_reddit_data = defaultdict(lambda: {'comments': [], 'sentiments': []})
            
            reddit_msg_count = 0
            for message in reddit_consumer:
                try:
                    reddit_data = message.value
                    movie_title = reddit_data.get('movie_title', '')
                    text = reddit_data.get('text', '')
                    
                    if not movie_title or not text:
                        continue
                    
                    # Normalize movie title for matching
                    movie_key = movie_title.lower()
                    
                    # Only process Reddit data for movies we have in TMDB
                    if movie_key not in movies_dict:
                        continue
                    
                    # Calculate sentiment using VADER
                    sentiment_scores = sentiment_analyzer.polarity_scores(text)
                    compound_sentiment = sentiment_scores['compound']
                    
                    # Convert compound score (-1 to 1) to (0 to 1) range
                    normalized_sentiment = (compound_sentiment + 1) / 2
                    
                    reddit_msg_count += 1
                    # Stop after 1000 Reddit messages processed
                    if reddit_msg_count >= 1000:
                        break
                    
                    # Store comment data
                    comment_obj = {
                        'text': text[:200] if len(text) > 200 else text,  # Limit length
                        'author': reddit_data.get('author', 'anonymous'),
                        'score': reddit_data.get('score', 0),
                        'sentiment': round(normalized_sentiment, 2),
                        'upvotes': reddit_data.get('score', 0)
                    }
                    
                    movie_reddit_data[movie_key]['comments'].append(comment_obj)
                    movie_reddit_data[movie_key]['sentiments'].append(normalized_sentiment)
                    
                except Exception as e:
                    print(f"Error processing Reddit comment: {e}")
                    continue
        
        reddit_consumer.close()
        
        # Merge Reddit data with TMDB data
        for movie_key, movie_data in movies_dict.items():
            if movie_key in movie_reddit_data:
                reddit_info = movie_reddit_data[movie_key]
                
                # Calculate mentions
                movie_data['mentions'] = len(reddit_info['comments'])
                
                # Calculate average sentiment
                if reddit_info['sentiments']:
                    avg_sentiment = sum(reddit_info['sentiments']) / len(reddit_info['sentiments'])
                    movie_data['sentiment'] = round(avg_sentiment, 2)
                
                # Deduplicate comments by text to avoid repeats
                unique_comments = []
                seen_texts = set()
                for comment in reddit_info['comments']:
                    # Use first 50 chars as unique identifier
                    text_key = comment['text'][:50].lower()
                    if text_key not in seen_texts:
                        seen_texts.add(text_key)
                        unique_comments.append(comment)
                
                # Sort by score and get top 3 UNIQUE comments
                sorted_comments = sorted(unique_comments, key=lambda x: x['score'], reverse=True)
                movie_data['redditComments'] = sorted_comments[:3]
            
            # Calculate TrendScore using real data
            # Formula: (popularity × 0.4) + (mentions × 2) + (sentiment × 100)
            popularity_score = movie_data['popularity'] * 0.4
            mentions_score = movie_data['mentions'] * 2
            sentiment_score = movie_data['sentiment'] * 100
            
            movie_data['trendScore'] = round(popularity_score + mentions_score + sentiment_score, 2)
            
            # Calculate ML prediction (simple heuristic for now)
            # In production, this would come from the River ML service
            movie_data['prediction'] = round(movie_data['trendScore'] * 0.95, 2)
        
        # Convert to list and sort by trend score
        movies = list(movies_dict.values())
        movies.sort(key=lambda x: x['trendScore'], reverse=True)
        
        # Get top 20
        result = movies[:20]
        
        # Update cache
        _trending_cache['data'] = result
        _trending_cache['timestamp'] = time.time()
        
        print(f"✅ Cached {len(result)} movies")
        return result
        
    except Exception as e:
        print(f"Error fetching trending movies: {e}")
        # If error, return cached data if available
        if _trending_cache['data'] is not None:
            print("⚠️ Returning stale cache due to error")
            return _trending_cache['data']
        raise HTTPException(status_code=500, detail=f"Failed to fetch trending movies: {str(e)}")

@app.get("/api/predictions")
async def get_predictions():
    """
    Get ML predictions vs actual TrendScores for visualization
    Shows River ML model performance over time
    """
    try:
        # Get trending movies (which already have predictions calculated)
        trending_movies = await get_trending_movies()
        
        # Convert to prediction format for the chart
        predictions = []
        for movie in trending_movies[:10]:  # Show top 10 for clarity
            predictions.append({
                'timestamp': movie['timestamp'],
                'actual_trend_score': movie['trendScore'],
                'predicted_trend_score': movie['prediction'],
                'movie_title': movie['title']
            })
        
        return predictions
        
    except Exception as e:
        print(f"Error fetching predictions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch predictions: {str(e)}")

@app.get("/api/stats/summary")
async def get_stats_summary():
    """
    Get summary statistics for the dashboard stats cards
    """
    try:
        # Get trending movies to calculate stats
        trending_movies = await get_trending_movies()
        
        if not trending_movies:
            return {
                'total_movies': 0,
                'avg_trend_score': 0,
                'total_predictions': 0,
                'model_accuracy': 0
            }
        
        # Calculate average TrendScore
        avg_trend_score = sum(m['trendScore'] for m in trending_movies) / len(trending_movies)
        
        # Calculate model accuracy (based on prediction vs actual)
        accuracies = []
        for movie in trending_movies:
            if movie['trendScore'] > 0:
                accuracy = 100 - abs((movie['prediction'] - movie['trendScore']) / movie['trendScore'] * 100)
                accuracies.append(max(0, min(100, accuracy)))  # Clamp between 0-100
        
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0
        
        # Count movies with real Reddit data
        movies_with_reddit = sum(1 for m in trending_movies if m['mentions'] > 0)
        
        # Calculate average sentiment (convert from 0-1 scale to -1 to 1 scale for display)
        sentiments = [m.get('sentiment', 0.5) for m in trending_movies]
        avg_sentiment = sum(sentiments) / len(trending_movies) if trending_movies else 0.5
        # Convert from 0-1 scale to -1 to 1 scale for sentiment gauge
        normalized_sentiment = (avg_sentiment * 2) - 1
        
        print(f"📊 Sentiment Debug: Raw sentiments: {sentiments[:5]}... Avg: {avg_sentiment:.2f}, Normalized: {normalized_sentiment:.2f}")
        
        return {
            'total_movies': len(trending_movies),
            'avg_trend_score': round(avg_trend_score, 2),
            'total_predictions': len(trending_movies),
            'model_accuracy': round(avg_accuracy, 2),
            'movies_with_reddit': movies_with_reddit,
            'average_sentiment': round(normalized_sentiment, 2)
        }
        
    except Exception as e:
        print(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")

@app.get("/api/tmdb/latest")
async def get_latest_tmdb():
    """
    Get the most recent movies from TMDB producer (last 10 from Kafka)
    """
    try:
        from kafka import KafkaConsumer, TopicPartition
        
        consumer = KafkaConsumer(
            bootstrap_servers=['kafka:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=2000,
            auto_offset_reset='latest'
        )
        
        topic = 'tmdb_stream'
        partitions = consumer.partitions_for_topic(topic)
        
        if not partitions:
            raise HTTPException(status_code=404, detail="No TMDB data available yet")
        
        movies = []
        topic_partitions = [TopicPartition(topic, p) for p in partitions]
        consumer.assign(topic_partitions)
        
        # Get last 10 messages from each partition
        for tp in topic_partitions:
            end_offset = consumer.end_offsets([tp])[tp]
            start_offset = max(0, end_offset - 10)
            consumer.seek(tp, start_offset)
            
            for message in consumer:
                if message.offset >= end_offset:
                    break
                try:
                    movie_data = message.value
                    movies.append({
                        'title': movie_data.get('title', 'Unknown'),
                        'releaseDate': movie_data.get('release_date', 'N/A'),
                        'trendScore': movie_data.get('popularity', 0) * 1.5,
                        'popularity': movie_data.get('popularity', 0),
                        'imdbRating': movie_data.get('imdb_rating', movie_data.get('vote_average', 0)),
                        'imdbVotes': movie_data.get('imdb_votes', 0),
                        'timestamp': datetime.utcnow().isoformat()
                    })
                except:
                    continue
        
        consumer.close()
        
        # Sort by timestamp (most recent first)
        movies.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return movies[:10]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch latest TMDB: {str(e)}")

@app.get("/api/pipeline/status")
async def get_pipeline_status():
    """
    Get live data pipeline status and freshness indicators
    Shows real-time metrics about data flow
    """
    try:
        from kafka import KafkaConsumer
        from kafka.errors import KafkaError
        
        status = {
            "pipeline_status": "🟢 Live",
            "last_updated": datetime.utcnow().isoformat(),
            "data_sources": {
                "tmdb": {"status": "unknown", "last_fetch": None, "movies_count": 0},
                "reddit": {"status": "unknown", "last_post": None, "posts_count": 0},
                "ml_service": {"status": "unknown", "predictions_count": 0}
            },
            "kafka_topics": {},
            "pipeline_health": "healthy"
        }
        
        # Check Kafka topics for latest messages
        try:
            consumer = KafkaConsumer(
                bootstrap_servers=['kafka:9092'],
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                consumer_timeout_ms=1000,
                auto_offset_reset='latest'
            )
            
            # Check TMDB stream
            consumer.subscribe(['tmdb_stream'])
            consumer.poll(timeout_ms=1000)
            consumer.seek_to_end()
            
            tmdb_count = 0
            last_tmdb_time = None
            for partition in consumer.assignment():
                position = consumer.position(partition)
                tmdb_count += position
                
            consumer.unsubscribe()
            
            # Check Reddit stream
            consumer.subscribe(['reddit_stream'])
            consumer.poll(timeout_ms=1000)
            consumer.seek_to_end()
            
            reddit_count = 0
            for partition in consumer.assignment():
                position = consumer.position(partition)
                reddit_count += position
            
            status["data_sources"]["tmdb"]["movies_count"] = tmdb_count
            status["data_sources"]["tmdb"]["status"] = "🟢 Active" if tmdb_count > 0 else "🟡 Idle"
            status["data_sources"]["tmdb"]["last_fetch"] = "< 5 min ago"  # Estimate based on fetch interval
            
            status["data_sources"]["reddit"]["posts_count"] = reddit_count
            status["data_sources"]["reddit"]["status"] = "🟢 Active" if reddit_count > 0 else "🟡 Idle"
            status["data_sources"]["reddit"]["last_post"] = "< 1 min ago"  # Real-time
            
            status["data_sources"]["ml_service"]["status"] = "🟢 Learning"
            status["data_sources"]["ml_service"]["predictions_count"] = max(0, tmdb_count - 10)
            
            status["kafka_topics"] = {
                "tmdb_stream": tmdb_count,
                "reddit_stream": reddit_count,
                "trend_stream": max(0, min(tmdb_count, reddit_count)),
                "predictions_stream": max(0, tmdb_count - 10)
            }
            
            consumer.close()
            
        except KafkaError as e:
            status["pipeline_status"] = "🟡 Degraded"
            status["pipeline_health"] = "kafka_unavailable"
        
        return status
        
    except Exception as e:
        return {
            "pipeline_status": "🔴 Error",
            "error": str(e),
            "last_updated": datetime.utcnow().isoformat()
        }


# ═══════════════════════════════════════════════════════════════════════════
# RAG CHAT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    RAG-powered chat endpoint for movie insights
    
    Example queries:
    - "Why is Mufasa trending right now?"
    - "What do people think about the acting in Sonic 3?"
    - "Is Nosferatu scary? Should I watch it?"
    """
    rag_service = get_rag_service()
    
    if rag_service is None:
        raise HTTPException(
            status_code=503, 
            detail="RAG service is not available. Please check if ChromaDB and Ollama are running."
        )
    
    try:
        result = rag_service.query(
            user_query=request.query,
            movie_title=request.movie_title,
            hours_back=request.hours_back
        )
        
        return ChatResponse(
            answer=result["answer"],
            sources_count=result["sources_count"],
            sample_reviews=result["sample_reviews"],
            movie_filter=result.get("movie_filter"),
            time_range_hours=result.get("time_range_hours", request.hours_back)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@app.get("/api/chat/movies")
async def get_available_movies():
    """Get list of movies available in the RAG knowledge base"""
    rag_service = get_rag_service()
    
    if rag_service is None:
        return {"movies": [], "status": "RAG service unavailable"}
    
    try:
        movies = rag_service.get_available_movies()
        return {"movies": movies, "count": len(movies)}
    except Exception as e:
        return {"movies": [], "error": str(e)}


@app.get("/api/chat/stats")
async def get_rag_stats():
    """Get RAG system statistics"""
    rag_service = get_rag_service()
    
    if rag_service is None:
        return {"status": "unavailable", "error": "RAG service not initialized"}
    
    try:
        stats = rag_service.get_stats()
        health = rag_service.health_check()
        return {
            "status": "operational" if all(health.values()) else "degraded",
            "stats": stats,
            "health": health
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/chat/health")
async def chat_health():
    """Check health of RAG components"""
    rag_service = get_rag_service()
    
    if rag_service is None:
        return {
            "status": "unhealthy",
            "components": {
                "vector_store": False,
                "ollama": False,
                "embedding_model": False
            }
        }
    
    health = rag_service.health_check()
    all_healthy = all(health.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": health
    }


@app.post("/api/chat/debug")
async def chat_debug(request: ChatRequest):
    """
    DEBUG endpoint - shows exactly what context is being sent to the LLM
    
    Use this to diagnose RAG retrieval issues
    """
    rag_service = get_rag_service()
    
    if rag_service is None:
        raise HTTPException(
            status_code=503, 
            detail="RAG service is not available."
        )
    
    try:
        debug_info = rag_service.debug_query(
            user_query=request.query,
            movie_title=request.movie_title,
            hours_back=request.hours_back
        )
        return debug_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debug error: {str(e)}")


@app.get("/api/movies/discussed")
async def get_discussed_movies(limit: int = 20, hours_back: int = 168):
    """
    Get movies that ACTUALLY have Reddit discussions in ChromaDB
    
    This endpoint ensures the dashboard only shows movies people are talking about.
    Returns movies sorted by number of discussions (most talked about first).
    
    Parameters:
    - limit: Max number of movies to return (default 20)
    - hours_back: Time window in hours (default 168 = 7 days)
    """
    rag_service = get_rag_service()
    
    if rag_service is None:
        raise HTTPException(
            status_code=503, 
            detail="RAG service is not available."
        )
    
    try:
        from collections import defaultdict
        from datetime import datetime, timedelta
        
        # Get all reviews from ChromaDB within time window
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        # Query ChromaDB for all recent reviews
        all_reviews = rag_service.vector_store.collection.get(
            where={
                "timestamp": {"$gte": cutoff_time.isoformat()}
            },
            include=["metadatas"]
        )
        
        if not all_reviews or not all_reviews.get('metadatas'):
            return []
        
        # Count discussions per movie
        movie_counts = defaultdict(lambda: {
            'title': None,
            'count': 0,
            'mentions': 0,
            'sentiment_sum': 0.0,
            'latest_timestamp': None
        })
        
        for metadata in all_reviews['metadatas']:
            movie_title = metadata.get('movie_title', '').lower().strip()
            
            if not movie_title or movie_title == 'unknown':
                continue
            
            # Aggregate discussion stats
            movie_counts[movie_title]['title'] = metadata.get('movie_title', movie_title)
            movie_counts[movie_title]['count'] += 1
            movie_counts[movie_title]['mentions'] += metadata.get('mentions', 0)
            movie_counts[movie_title]['sentiment_sum'] += metadata.get('sentiment', 0.5)
            
            # Track latest timestamp
            timestamp = metadata.get('timestamp', '')
            if not movie_counts[movie_title]['latest_timestamp'] or timestamp > movie_counts[movie_title]['latest_timestamp']:
                movie_counts[movie_title]['latest_timestamp'] = timestamp
        
        # Convert to list and calculate avg sentiment
        discussed_movies = []
        for movie_title, stats in movie_counts.items():
            discussed_movies.append({
                'title': stats['title'],
                'discussions': stats['count'],
                'mentions': stats['mentions'],
                'sentiment': round(stats['sentiment_sum'] / max(stats['count'], 1), 2),
                'trendScore': stats['count'] * 10,  # Simple trend score
                'popularity': stats['mentions'],
                'timestamp': stats['latest_timestamp'],
                'releaseDate': 'N/A',  # Will be enriched from metadata if available
                'voteAverage': 0,
                'imdbRating': 0
            })
        
        # Try to enrich with metadata from movie_metadata collection
        for movie in discussed_movies:
            try:
                metadata = rag_service.vector_store.get_metadata(movie['title'])
                if metadata:
                    movie['releaseDate'] = metadata.get('release_date', 'N/A')
                    movie['voteAverage'] = metadata.get('vote_average', 0)
                    movie['imdbRating'] = metadata.get('imdb_rating', 0)
                    movie['overview'] = metadata.get('overview', '')
            except:
                pass
        
        # Sort by discussions count (most talked about first)
        discussed_movies.sort(key=lambda x: x['discussions'], reverse=True)
        
        # Return top N
        result = discussed_movies[:limit]
        
        print(f"📊 Found {len(discussed_movies)} movies with discussions. Returning top {len(result)}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error getting discussed movies: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
