import React, { useState, useEffect } from 'react';
import { TrendingUp, Film, Brain, Activity, Zap, Star, MessageCircle, MessageSquare, Database } from 'lucide-react';
import TrendChart from './components/TrendChart';
import MovieCard from './components/MovieCard';
import StatsCard from './components/StatsCard';
import SentimentGauge from './components/SentimentGauge';
import MovieSearch from './components/MovieSearch';
import ChatPanel from './components/ChatPanel';
import { fetchTrendingMovies, fetchPredictions, fetchStats } from './api';

function App() {
  const [trendingMovies, setTrendingMovies] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [selectedMovie, setSelectedMovie] = useState(null);
  const [stats, setStats] = useState({
    totalMovies: 0,
    avgTrendScore: 0,
    totalPredictions: 0,
    modelAccuracy: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [movies, preds, statsData] = await Promise.all([
          fetchTrendingMovies(),
          fetchPredictions(),
          fetchStats()
        ]);
        
        // Only update if we got data
        if (movies && movies.length > 0) {
          setTrendingMovies(movies);
        }
        if (preds && preds.length > 0) {
          setPredictions(preds);
        }
        if (statsData) {
          setStats(statsData);
        }
        
        setLoading(false);
      } catch (error) {
        console.error('Error loading data:', error);
        // Keep existing data on error, just mark as not loading
        setLoading(false);
      }
    };

    loadData();
    const interval = setInterval(loadData, 30000); // Refresh every 30 seconds

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen p-6">
      {/* Header */}
      <header className="mb-8 animate-fadeIn">
        <div className="flex items-center justify-between bg-white/10 backdrop-blur-lg rounded-2xl p-6 shadow-2xl">
          <div className="flex items-center space-x-4">
            <div className="bg-gradient-to-br from-purple-500 to-pink-500 p-3 rounded-xl">
              <Film className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-4xl font-bold text-white">TrendScope AI</h1>
              <p className="text-purple-200">Real-time Movie Trend Analytics</p>
            </div>
          </div>
          <div className="flex items-center space-x-2 bg-green-500/20 px-4 py-2 rounded-full">
            <Activity className="w-5 h-5 text-green-300 animate-pulse" />
            <span className="text-green-300 font-semibold">Live</span>
          </div>
        </div>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatsCard
          icon={<Film className="w-6 h-6" />}
          title="Tracked Movies"
          value={stats.totalMovies}
          color="blue"
          loading={loading}
        />
        <StatsCard
          icon={<MessageSquare className="w-6 h-6" />}
          title="Total Reviews"
          value="19,023+"
          color="purple"
          loading={loading}
        />
        <StatsCard
          icon={<Database className="w-6 h-6" />}
          title="Active Sources"
          value="3"
          color="pink"
          loading={loading}
        />
        <StatsCard
          icon={<MessageCircle className="w-6 h-6" />}
          title="Reddit Activity"
          value={`${stats.movies_with_reddit || 0}/${stats.totalMovies}`}
          color="green"
          loading={loading}
        />
      </div>

      {/* Movie Search Section */}
      <div className="mb-8">
        <MovieSearch />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Trending Movies List */}
        <div className="lg:col-span-1">
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 shadow-2xl h-[900px] flex flex-col">
            <div className="flex items-center space-x-2 mb-4">
              <Star className="w-6 h-6 text-yellow-400" />
              <h2 className="text-2xl font-bold text-white">Top Trending</h2>
            </div>
            <div className="space-y-4 flex-1 overflow-y-auto pr-2">
              {loading ? (
                [...Array(5)].map((_, i) => (
                  <div key={i} className="animate-pulse bg-white/5 h-24 rounded-xl"></div>
                ))
              ) : trendingMovies.length > 0 ? (
                trendingMovies.map((movie, index) => (
                  <div 
                    key={index} 
                    onClick={() => setSelectedMovie(movie.title)}
                    className="cursor-pointer transition-transform hover:scale-[1.02]"
                  >
                    <MovieCard movie={movie} rank={index + 1} />
                  </div>
                ))
              ) : (
                <div className="text-center py-12 text-gray-400">
                  <Film className="w-16 h-16 mx-auto mb-4 opacity-50" />
                  <p className="text-lg">No trending movies yet</p>
                  <p className="text-sm">Waiting for data from pipeline...</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RAG Chat Panel */}
        <div className="lg:col-span-2">
          <div className="h-[900px] mb-8">
            <ChatPanel selectedMovie={selectedMovie} setSelectedMovie={setSelectedMovie} />
          </div>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Trend Chart */}
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 shadow-2xl">
          <h2 className="text-2xl font-bold text-white mb-4 flex items-center">
            <TrendingUp className="w-6 h-6 mr-2" />
            TrendScore Timeline
          </h2>
          <TrendChart data={trendingMovies} loading={loading} />
        </div>
      </div>

      {/* Footer */}
      <footer className="text-center text-purple-200 text-sm">
        <p>Powered by Apache Kafka • Apache Spark • ChromaDB • Ollama/Mistral • RAG</p>
      </footer>
    </div>
  );
}

export default App;
