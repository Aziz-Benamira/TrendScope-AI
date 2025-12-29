import React, { useState } from 'react';
import { TrendingUp, MessageSquare, ThumbsUp, Star, ChevronDown, ChevronUp, Calendar, TrendingDown, Brain } from 'lucide-react';

const MovieCard = ({ movie, rank }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const getSentimentColor = (sentiment) => {
    if (sentiment > 0.3) return 'text-green-400';
    if (sentiment < -0.3) return 'text-red-400';
    return 'text-yellow-400';
  };

  const getTrendColor = (score) => {
    if (score > 200) return 'from-emerald-600 to-teal-600';
    if (score > 150) return 'from-blue-600 to-indigo-600';
    return 'from-violet-600 to-purple-600';
  };

  const formatVotes = (votes) => {
    if (!votes) return 'N/A';
    if (votes >= 1000000) return `${(votes / 1000000).toFixed(1)}M`;
    if (votes >= 1000) return `${(votes / 1000).toFixed(0)}K`;
    return votes.toString();
  };

  const getPredictionAccuracy = () => {
    if (!movie.prediction || !movie.trendScore) return null;
    const accuracy = 100 - Math.abs((movie.prediction - movie.trendScore) / movie.trendScore * 100);
    return Math.max(0, Math.min(100, accuracy)).toFixed(1);
  };

  return (
    <div className="bg-gradient-to-br from-slate-800/40 to-slate-900/40 hover:from-slate-800/60 hover:to-slate-900/60 transition-all duration-300 rounded-xl backdrop-blur-sm border border-slate-700/50 hover:border-slate-600/70 shadow-lg hover:shadow-2xl">
      {/* Main Card - Always Visible */}
      <div 
        className="p-4 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                #{rank}
              </span>
              <h3 className="text-lg font-bold text-white line-clamp-1">{movie.title}</h3>
              {isExpanded ? 
                <ChevronUp className="w-5 h-5 text-gray-400 ml-auto" /> : 
                <ChevronDown className="w-5 h-5 text-gray-400 ml-auto" />
              }
            </div>
            
            {/* Release Date */}
            {movie.releaseDate && (
              <div className="flex items-center space-x-1 mb-2 text-xs text-gray-400">
                <Calendar className="w-3 h-3" />
                <span>{new Date(movie.releaseDate).toLocaleDateString()}</span>
              </div>
            )}
            
            {/* IMDb Rating Badge */}
            {movie.imdbRating && (
              <div className="flex items-center space-x-1 mb-3 bg-yellow-500/10 border border-yellow-500/30 px-3 py-1.5 rounded-lg inline-flex">
                <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
                <span className="text-yellow-300 font-bold text-sm">{movie.imdbRating}</span>
                <span className="text-yellow-300/70 text-xs">({formatVotes(movie.imdbVotes)} votes)</span>
              </div>
            )}
            
            <div className="grid grid-cols-3 gap-3 text-sm">
              <div className="flex items-center space-x-2 bg-blue-500/10 px-2 py-1 rounded-md">
                <TrendingUp className="w-4 h-4 text-blue-400" />
                <div>
                  <div className="text-xs text-gray-400">Popularity</div>
                  <span className="text-white font-semibold">{movie.popularity.toFixed(0)}</span>
                </div>
              </div>
              <div className="flex items-center space-x-2 bg-purple-500/10 px-2 py-1 rounded-md">
                <MessageSquare className="w-4 h-4 text-purple-400" />
                <div>
                  <div className="text-xs text-gray-400">Mentions</div>
                  <span className="text-white font-semibold">{movie.mentions || 0}</span>
                </div>
              </div>
              <div className="flex items-center space-x-2 bg-green-500/10 px-2 py-1 rounded-md">
                <ThumbsUp className={`w-4 h-4 ${getSentimentColor(movie.sentiment)}`} />
                <div>
                  <div className="text-xs text-gray-400">Sentiment</div>
                  <span className={`font-semibold ${getSentimentColor(movie.sentiment)}`}>
                    {(movie.sentiment * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          </div>
          
          {/* Trend Score Badge */}
          <div className={`ml-4 bg-gradient-to-br ${getTrendColor(movie.trendScore)} px-5 py-3 rounded-xl shadow-lg`}>
            <div className="text-xs text-white/90 font-medium">Trend Score</div>
            <div className="text-2xl font-bold text-white">{movie.trendScore.toFixed(0)}</div>
          </div>
        </div>
      </div>

      {/* Expanded Content - Shows on Click */}
      {isExpanded && (
        <div className="px-4 pb-4 border-t border-slate-700/50 pt-4 space-y-4 animate-fadeIn">
          
          {/* River ML Prediction */}
          {movie.prediction && (
            <div className="bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/30 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-3">
                <Brain className="w-5 h-5 text-indigo-400" />
                <h4 className="font-bold text-white">River ML Prediction</h4>
              </div>
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div>
                  <div className="text-gray-400 text-xs mb-1">Predicted</div>
                  <div className="text-indigo-300 font-bold text-lg">{movie.prediction.toFixed(0)}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-xs mb-1">Actual</div>
                  <div className="text-purple-300 font-bold text-lg">{movie.trendScore.toFixed(0)}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-xs mb-1">Accuracy</div>
                  <div className="text-green-300 font-bold text-lg">{getPredictionAccuracy()}%</div>
                </div>
              </div>
              <div className="mt-2 text-xs text-gray-400">
                {movie.prediction > movie.trendScore ? 
                  '⚠️ Model predicted higher trend than actual' : 
                  '✅ Model predicted within range'}
              </div>
            </div>
          )}

          {/* Reddit Comments Section */}
          {movie.redditComments && movie.redditComments.length > 0 && (
            <div className="bg-orange-500/5 border border-orange-500/30 rounded-lg p-4">
              <div className="flex items-center space-x-2 mb-3">
                <MessageSquare className="w-5 h-5 text-orange-400" />
                <h4 className="font-bold text-white">Reddit Buzz</h4>
              </div>
              <div className="space-y-2">
                {movie.redditComments.slice(0, 3).map((comment, idx) => (
                  <div key={idx} className="bg-slate-800/50 rounded-md p-3 border border-slate-700/50">
                    <p className="text-gray-300 text-sm mb-2">{comment.text}</p>
                    <div className="flex items-center space-x-3 text-xs">
                      <div className="flex items-center space-x-1">
                        <ThumbsUp className="w-3 h-3 text-orange-400" />
                        <span className="text-orange-300">{comment.upvotes || 0}</span>
                      </div>
                      <div className={`px-2 py-0.5 rounded ${
                        comment.sentiment > 0.6 ? 'bg-green-500/20 text-green-300' :
                        comment.sentiment < 0.4 ? 'bg-red-500/20 text-red-300' :
                        'bg-yellow-500/20 text-yellow-300'
                      }`}>
                        {comment.sentiment > 0.6 ? '😊 Positive' : 
                         comment.sentiment < 0.4 ? '😞 Negative' : 
                         '😐 Neutral'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Movie Overview */}
          {movie.overview && (
            <div className="bg-slate-800/30 rounded-lg p-4 border border-slate-700/50">
              <h4 className="font-bold text-white mb-2 text-sm">Overview</h4>
              <p className="text-gray-400 text-sm leading-relaxed">{movie.overview}</p>
            </div>
          )}

          {/* Why This Rank? */}
          <div className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-lg p-4 border border-blue-500/30">
            <h4 className="font-bold text-white mb-2 text-sm flex items-center">
              <TrendingUp className="w-4 h-4 mr-2 text-blue-400" />
              Why This Rank?
            </h4>
            <div className="text-gray-300 text-xs space-y-1">
              <p>✓ Popularity Score: {movie.popularity.toFixed(1)}</p>
              <p>✓ Community Engagement: {movie.mentions || 0} mentions</p>
              <p>✓ Audience Sentiment: {(movie.sentiment * 100).toFixed(0)}% positive</p>
              {movie.imdbRating && <p>✓ IMDb Rating: {movie.imdbRating}/10 ({formatVotes(movie.imdbVotes)} votes)</p>}
              <p className="text-blue-300 font-semibold mt-2">
                → Combined Trend Score: {movie.trendScore.toFixed(0)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MovieCard;
