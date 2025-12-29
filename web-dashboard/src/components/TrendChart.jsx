import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { format } from 'date-fns';

const TrendChart = ({ data, loading }) => {
  if (loading) {
    return <div className="h-64 bg-white/5 rounded-xl animate-pulse"></div>;
  }

  const chartData = data.slice(0, 5).map(movie => ({
    name: movie.title.substring(0, 15) + '...',
    score: movie.trendScore,
    popularity: movie.popularity,
    mentions: movie.mentions * 2 // Scale for visibility
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
        <XAxis 
          dataKey="name" 
          stroke="rgba(255,255,255,0.5)"
          tick={{ fill: 'rgba(255,255,255,0.7)' }}
        />
        <YAxis stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.7)' }} />
        <Tooltip 
          contentStyle={{ 
            backgroundColor: 'rgba(0,0,0,0.8)', 
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: '8px'
          }}
          labelStyle={{ color: '#fff' }}
        />
        <Legend wrapperStyle={{ color: '#fff' }} />
        <Line 
          type="monotone" 
          dataKey="score" 
          stroke="#8b5cf6" 
          strokeWidth={3}
          dot={{ fill: '#8b5cf6', r: 5 }}
          name="TrendScore"
        />
        <Line 
          type="monotone" 
          dataKey="popularity" 
          stroke="#3b82f6" 
          strokeWidth={2}
          dot={{ fill: '#3b82f6', r: 4 }}
          name="Popularity"
        />
        <Line 
          type="monotone" 
          dataKey="mentions" 
          stroke="#ec4899" 
          strokeWidth={2}
          dot={{ fill: '#ec4899', r: 4 }}
          name="Mentions (x2)"
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default TrendChart;
