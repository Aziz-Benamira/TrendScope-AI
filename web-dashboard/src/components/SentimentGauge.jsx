import React from 'react';
import { Smile, Meh, Frown } from 'lucide-react';

const SentimentGauge = ({ sentiment, loading }) => {
  if (loading) {
    return <div className="h-32 bg-white/5 rounded-xl animate-pulse"></div>;
  }

  const percentage = ((sentiment + 1) / 2) * 100; // Convert -1 to 1 range to 0-100
  
  const getColor = () => {
    if (percentage > 66) return 'bg-green-500';
    if (percentage > 33) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getIcon = () => {
    if (percentage > 66) return <Smile className="w-12 h-12 text-green-400" />;
    if (percentage > 33) return <Meh className="w-12 h-12 text-yellow-400" />;
    return <Frown className="w-12 h-12 text-red-400" />;
  };

  const getLabel = () => {
    if (percentage > 66) return 'Positive';
    if (percentage > 33) return 'Neutral';
    return 'Negative';
  };

  return (
    <div className="flex items-center justify-between">
      <div className="flex-1">
        <div className="mb-2 flex justify-between text-sm text-purple-200">
          <span>Negative</span>
          <span>Neutral</span>
          <span>Positive</span>
        </div>
        <div className="w-full bg-white/10 rounded-full h-8 overflow-hidden">
          <div 
            className={`h-full ${getColor()} transition-all duration-1000 ease-out relative`}
            style={{ width: `${percentage}%` }}
          >
            <div className="absolute inset-0 bg-gradient-to-r from-transparent to-white/20"></div>
          </div>
        </div>
        <div className="mt-2 text-center">
          <span className="text-2xl font-bold text-white">{percentage.toFixed(1)}%</span>
          <span className="text-purple-200 ml-2">{getLabel()}</span>
        </div>
      </div>
      <div className="ml-8 flex items-center justify-center">
        {getIcon()}
      </div>
    </div>
  );
};

export default SentimentGauge;
