import React, { useState } from 'react';
import { Search, Loader, Film, TrendingUp, MessageSquare, Star, Calendar, BarChart3 } from 'lucide-react';
import axios from 'axios';

const MovieSearch = () => {
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const searchMovie = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setSearching(true);
    setError(null);
    setResult(null);

    try {
      // Search for the movie in our trending data first
      const trendingResponse = await axios.get(`http://localhost:8000/api/trending`);
      const found = trendingResponse.data.find(
        m => m.title.toLowerCase().includes(query.toLowerCase())
      );

      if (found) {
        setResult(found);
      } else {
        // If not in trending, search TMDB API directly
        const tmdbResponse = await axios.get(
          `https://api.themoviedb.org/3/search/multi?api_key=YOUR_TMDB_API_KEY&query=${encodeURIComponent(query)}`
        );
        
        if (tmdbResponse.data.results && tmdbResponse.data.results.length > 0) {
          const movie = tmdbResponse.data.results[0];
          setResult({
            title: movie.title || movie.name,
            releaseDate: movie.release_date || movie.first_air_date,
            overview: movie.overview,
            popularity: movie.popularity || 0,
            voteAverage: movie.vote_average || 0,
            trendScore: movie.popularity * 1.5 || 0,
            mentions: 0,
            sentiment: 0.5,
            redditComments: [],
            fromSearch: true
          });
        } else {
          setError('Movie not found. Try a different title.');
        }
      }
    } catch (err) {
      console.error('Search error:', err);
      setError('Search failed. Please try again.');
    } finally {
      setSearching(false);
    }
  };

  const formatVotes = (votes) => {
    if (!votes) return 'N/A';
    if (votes >= 1000000) return `${(votes / 1000000).toFixed(1)}M`;
    if (votes >= 1000) return `${(votes / 1000).toFixed(0)}K`;
    return votes.toString();
  };

  return (
    <div className="bg-gradient-to-br from-slate-800/60 to-slate-900/60 backdrop-blur-lg rounded-2xl p-6 shadow-2xl border border-slate-700/50">
      <div className="flex items-center space-x-2 mb-4">
        <Search className="w-6 h-6 text-blue-400" />
        <h2 className="text-2xl font-bold text-white">Search Movie</h2>
      </div>

      {/* Search Form */}
      <form onSubmit={searchMovie} className="mb-6">
        <div className="flex space-x-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter movie or series name..."
            className="flex-1 bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition"
          />
          <button
            type="submit"
            disabled={searching || !query.trim()}
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-600 disabled:to-gray-700 text-white px-6 py-3 rounded-lg font-semibold flex items-center space-x-2 transition shadow-lg hover:shadow-xl disabled:cursor-not-allowed"
          >
            {searching ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                <span>Searching...</span>
              </>
            ) : (
              <>
                <Search className="w-5 h-5" />
                <span>Search</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* Error Message */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-4">
          <p className="text-red-300 text-sm">{error}</p>
        </div>
      )}

      {/* Search Result */}
      {result && (
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/80 border border-slate-700/50 rounded-xl p-6 space-y-4 animate-fadeIn">
          {/* Title and Release Date */}
          <div>
            <div className="flex items-center space-x-2 mb-2">
              <Film className="w-6 h-6 text-blue-400" />
              <h3 className="text-2xl font-bold text-white">{result.title}</h3>
              {result.fromSearch && (
                <span className="bg-yellow-500/20 border border-yellow-500/30 text-yellow-300 text-xs px-2 py-1 rounded">
                  From TMDB Search
                </span>
              )}
            </div>
            {result.releaseDate && (
              <div className="flex items-center space-x-1 text-sm text-gray-400">
                <Calendar className="w-4 h-4" />
                <span>{new Date(result.releaseDate).toLocaleDateString()}</span>
              </div>
            )}
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
              <div className="flex items-center space-x-2 mb-1">
                <BarChart3 className="w-4 h-4 text-blue-400" />
                <span className="text-xs text-gray-400">TrendScore</span>
              </div>
              <div className="text-xl font-bold text-blue-300">{result.trendScore?.toFixed(0) || 0}</div>
            </div>

            <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-3">
              <div className="flex items-center space-x-2 mb-1">
                <TrendingUp className="w-4 h-4 text-purple-400" />
                <span className="text-xs text-gray-400">Popularity</span>
              </div>
              <div className="text-xl font-bold text-purple-300">{result.popularity?.toFixed(0) || 0}</div>
            </div>

            <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
              <div className="flex items-center space-x-2 mb-1">
                <Star className="w-4 h-4 text-yellow-400" />
                <span className="text-xs text-gray-400">Rating</span>
              </div>
              <div className="text-xl font-bold text-yellow-300">
                {result.voteAverage?.toFixed(1) || result.imdbRating?.toFixed(1) || 'N/A'}
              </div>
            </div>

            <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-3">
              <div className="flex items-center space-x-2 mb-1">
                <MessageSquare className="w-4 h-4 text-orange-400" />
                <span className="text-xs text-gray-400">Mentions</span>
              </div>
              <div className="text-xl font-bold text-orange-300">{result.mentions || 0}</div>
            </div>
          </div>

          {/* Overview */}
          {result.overview && (
            <div className="bg-slate-900/50 border border-slate-700/50 rounded-lg p-4">
              <h4 className="font-bold text-white mb-2 text-sm">Overview</h4>
              <p className="text-gray-400 text-sm leading-relaxed">{result.overview}</p>
            </div>
          )}

          {/* Reddit Comments if available */}
          {result.redditComments && result.redditComments.length > 0 && (
            <div className="bg-orange-500/5 border border-orange-500/30 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-3">
                <MessageSquare className="w-5 h-5 text-orange-400" />
                <h4 className="font-bold text-white">Reddit Buzz</h4>
              </div>
              <div className="space-y-2">
                {result.redditComments.slice(0, 3).map((comment, idx) => (
                  <div key={idx} className="bg-slate-800/50 rounded-md p-3 border border-slate-700/50">
                    <p className="text-gray-300 text-sm">{comment.text}</p>
                    <div className="flex items-center space-x-2 mt-2 text-xs text-gray-400">
                      <span>👍 {comment.upvotes || 0}</span>
                      <span className={`px-2 py-0.5 rounded ${
                        comment.sentiment > 0.6 ? 'bg-green-500/20 text-green-300' :
                        comment.sentiment < 0.4 ? 'bg-red-500/20 text-red-300' :
                        'bg-yellow-500/20 text-yellow-300'
                      }`}>
                        {comment.sentiment > 0.6 ? '😊 Positive' : 
                         comment.sentiment < 0.4 ? '😞 Negative' : 
                         '😐 Neutral'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Prediction if available */}
          {result.prediction && (
            <div className="bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/30 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-2">
                <BarChart3 className="w-5 h-5 text-indigo-400" />
                <h4 className="font-bold text-white">River ML Prediction</h4>
              </div>
              <div className="flex items-center space-x-4">
                <div>
                  <div className="text-xs text-gray-400">Predicted TrendScore</div>
                  <div className="text-2xl font-bold text-indigo-300">{result.prediction.toFixed(0)}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-400">Actual TrendScore</div>
                  <div className="text-2xl font-bold text-purple-300">{result.trendScore?.toFixed(0) || 0}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MovieSearch;
