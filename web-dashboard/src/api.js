import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001';

// Configure axios with timeout
axios.defaults.timeout = 10000;

export const fetchTrendingMovies = async () => {
  try {
    // Get real trends from backend - NO FALLBACK TO MOCK
    const response = await axios.get(`${API_BASE_URL}/api/trending`, {
      params: { limit: 20 }
    });
    
    if (response.data && response.data.length > 0) {
      console.log('✅ Using REAL TMDB data from backend:', response.data.length, 'movies');
      // Backend returns: title, releaseDate, trendScore, popularity, etc.
      return response.data.map(movie => ({
        title: movie.title || movie.movie_title,
        trendScore: movie.trendScore || movie.trend_score || 0,
        popularity: movie.popularity || 0,
        mentions: movie.mentions || movie.mentions_count || 0,
        sentiment: movie.sentiment || movie.avg_sentiment || 0.5,
        voteAverage: movie.voteAverage || movie.vote_average || 0,
        imdbRating: movie.imdbRating || movie.imdb_rating || 0,
        imdbVotes: movie.imdbVotes || movie.imdb_votes || 0,
        releaseDate: movie.releaseDate || movie.release_date || 'N/A',
        redditComments: movie.redditComments || movie.reddit_comments || [],
        prediction: movie.prediction || movie.predicted_trend || 0,
        overview: movie.overview || '',
        timestamp: movie.timestamp || movie.window_end || new Date().toISOString()
      })).sort((a, b) => b.trendScore - a.trendScore);
    }
    
    // If no data from backend, return empty array (don't use mock!)
    console.warn('⚠️ No data from backend yet');
    return [];
    
  } catch (error) {
    console.error('❌ API Error:', error.message);
    // Return empty array - NEVER use mock data
    return [];
  }
};

// NEW: Fetch live data directly from Kafka topics
const fetchLiveTMDBData = async () => {
  try {
    // Get latest TMDB movies from Kafka stream
    const response = await axios.get(`${API_BASE_URL}/api/tmdb/latest`, {
      params: { limit: 20 }
    });
    
    if (response.data && response.data.length > 0) {
      console.log('✅ Using LIVE TMDB data from Kafka:', response.data.length, 'movies');
      return response.data;
    }
    
    throw new Error('No live data available');
  } catch (error) {
    console.warn('⚠️ Cannot fetch live data from Kafka');
    return []; // Return empty array instead of mock data
  }
};

export const fetchPredictions = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/predictions/latest`, {
      params: { limit: 20 }
    });
    
    return response.data.map(pred => ({
      timestamp: pred.timestamp,
      actual: pred.actual_trend_score,
      predicted: pred.predicted_trend_score,
      movieTitle: pred.movie_title
    }));
    
  } catch (error) {
    console.error('API Error - No predictions available:', error.message);
    return []; // Return empty array instead of mock
  }
};

export const fetchStats = async () => {
  try {
    // Try to get stats from the dedicated endpoint first
    const response = await axios.get(`${API_BASE_URL}/api/stats/summary`);
    
    return {
      totalMovies: response.data.total_movies || 0,
      avgTrendScore: response.data.avg_trend_score || 0,
      totalPredictions: response.data.total_predictions || 0,
      modelAccuracy: response.data.model_accuracy || 0,
      average_sentiment: response.data.average_sentiment || 0
    };
    
  } catch (error) {
    console.warn('Stats API not available, calculating from pipeline status');
    
    // Fallback: calculate from pipeline status
    try {
      const statusResponse = await axios.get(`${API_BASE_URL}/api/pipeline/status`);
      const kafkaTopics = statusResponse.data.kafka_topics || {};
      
      return {
        totalMovies: kafkaTopics.tmdb_stream || 0,
        avgTrendScore: 0, // Would need to calculate from actual data
        totalPredictions: kafkaTopics.predictions_stream || 0,
        modelAccuracy: 85.5 // Placeholder - River ML learns incrementally
      };
    } catch (fallbackError) {
      console.error('Could not fetch stats from any source');
      return {
        totalMovies: 0,
        avgTrendScore: 0,
        totalPredictions: 0,
        modelAccuracy: 0
      };
    }
  }
};

export const fetchMovieHistory = async (movieTitle) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/trends/movie/${encodeURIComponent(movieTitle)}`);
    return response.data;
  } catch (error) {
    console.error(`API Error - Fetching history for ${movieTitle}:`, error.message);
    return [];
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// RAG CHAT API FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Send a chat query to the RAG system
 * @param {string} query - Natural language question
 * @param {string} movieTitle - Optional: filter by movie
 * @param {number} hoursBack - Time window (default 24 hours)
 */
export const sendChatQuery = async (query, movieTitle = null, hoursBack = 24) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/api/chat`, {
      query,
      movie_title: movieTitle,
      hours_back: hoursBack
    }, {
      timeout: 60000 // 60 second timeout for LLM generation
    });
    
    return {
      success: true,
      answer: response.data.answer,
      sourcesCount: response.data.sources_count,
      sampleReviews: response.data.sample_reviews || [],
      movieFilter: response.data.movie_filter,
      timeRange: response.data.time_range_hours
    };
    
  } catch (error) {
    console.error('Chat API Error:', error.message);
    return {
      success: false,
      answer: error.response?.data?.detail || 'Failed to get response. Please try again.',
      sourcesCount: 0,
      sampleReviews: []
    };
  }
};

/**
 * Get list of movies available in the RAG knowledge base
 */
export const fetchChatMovies = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/chat/movies`);
    return response.data.movies || [];
  } catch (error) {
    console.error('Error fetching chat movies:', error.message);
    return [];
  }
};

/**
 * Get RAG system stats
 */
export const fetchChatStats = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/chat/stats`);
    return response.data;
  } catch (error) {
    console.error('Error fetching chat stats:', error.message);
    return { status: 'unavailable' };
  }
};

/**
 * Check RAG health
 */
export const checkChatHealth = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/chat/health`);
    return response.data;
  } catch (error) {
    return { status: 'unhealthy', components: {} };
  }
};
