import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Area, AreaChart } from 'recharts';
import { Brain, TrendingUp, Target } from 'lucide-react';

const PredictionChart = ({ data, loading }) => {
  if (loading) {
    return <div className="h-64 bg-white/5 rounded-xl animate-pulse"></div>;
  }

  // Prepare data for timeline chart showing both predicted vs actual
  const chartData = data.map((d, i) => ({
    index: i + 1,
    actual: d.actual,
    predicted: d.predicted,
    movieTitle: d.movieTitle,
    accuracy: 100 - Math.abs(((d.predicted - d.actual) / d.actual) * 100)
  }));

  // Calculate overall accuracy
  const avgAccuracy = chartData.length > 0
    ? chartData.reduce((sum, d) => sum + Math.max(0, d.accuracy), 0) / chartData.length
    : 0;

  const avgError = chartData.length > 0
    ? chartData.reduce((sum, d) => sum + Math.abs(d.predicted - d.actual), 0) / chartData.length
    : 0;

  return (
    <div className="space-y-4">
      {/* Stats Banner */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-lg p-3">
          <div className="flex items-center space-x-2 mb-1">
            <Brain className="w-4 h-4 text-indigo-400" />
            <span className="text-xs text-gray-400">Model Accuracy</span>
          </div>
          <div className="text-2xl font-bold text-indigo-300">{avgAccuracy.toFixed(1)}%</div>
        </div>
        
        <div className="bg-gradient-to-br from-blue-500/20 to-cyan-500/20 border border-blue-500/30 rounded-lg p-3">
          <div className="flex items-center space-x-2 mb-1">
            <Target className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-gray-400">Avg Error (MAE)</span>
          </div>
          <div className="text-2xl font-bold text-blue-300">{avgError.toFixed(1)}</div>
        </div>
        
        <div className="bg-gradient-to-br from-green-500/20 to-emerald-500/20 border border-green-500/30 rounded-lg p-3">
          <div className="flex items-center space-x-2 mb-1">
            <TrendingUp className="w-4 h-4 text-green-400" />
            <span className="text-xs text-gray-400">Predictions</span>
          </div>
          <div className="text-2xl font-bold text-green-300">{chartData.length}</div>
        </div>
      </div>

      {/* Timeline Chart - Predicted vs Actual */}
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
          <XAxis 
            dataKey="index" 
            stroke="rgba(255,255,255,0.5)"
            tick={{ fill: 'rgba(255,255,255,0.7)' }}
            label={{ value: 'Prediction Timeline →', position: 'bottom', fill: 'rgba(255,255,255,0.7)', offset: -5 }}
          />
          <YAxis 
            stroke="rgba(255,255,255,0.5)"
            tick={{ fill: 'rgba(255,255,255,0.7)' }}
            label={{ value: 'TrendScore', angle: -90, position: 'left', fill: 'rgba(255,255,255,0.7)' }}
          />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: 'rgba(15, 23, 42, 0.95)', 
              border: '1px solid rgba(99, 102, 241, 0.3)',
              borderRadius: '8px',
              boxShadow: '0 4px 6px rgba(0,0,0,0.3)'
            }}
            labelStyle={{ color: '#fff', fontWeight: 'bold' }}
            formatter={(value, name) => {
              if (name === 'Actual') return [value.toFixed(1), '🎯 Actual TrendScore'];
              if (name === 'Predicted') return [value.toFixed(1), '🤖 River ML Prediction'];
              return [value, name];
            }}
          />
          <Legend 
            wrapperStyle={{ color: '#fff', paddingTop: '10px' }}
            iconType="line"
          />
          
          {/* Actual TrendScore Line */}
          <Line 
            type="monotone" 
            dataKey="actual" 
            name="Actual"
            stroke="#10b981"
            strokeWidth={3}
            dot={{ fill: '#10b981', r: 4 }}
            activeDot={{ r: 6, fill: '#34d399' }}
          />
          
          {/* Predicted TrendScore Line */}
          <Line 
            type="monotone" 
            dataKey="predicted" 
            name="Predicted"
            stroke="#6366f1"
            strokeWidth={3}
            strokeDasharray="5 5"
            dot={{ fill: '#6366f1', r: 4 }}
            activeDot={{ r: 6, fill: '#818cf8' }}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Learning Explanation */}
      <div className="bg-gradient-to-r from-violet-500/10 to-purple-500/10 border border-violet-500/30 rounded-lg p-3">
        <div className="flex items-start space-x-2">
          <Brain className="w-5 h-5 text-violet-400 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-bold text-violet-300 mb-1">🧠 River ML Online Learning</h4>
            <p className="text-xs text-gray-400 leading-relaxed">
              The model learns incrementally from each movie's actual trend score. 
              <span className="text-green-300"> Green line</span> = actual results, 
              <span className="text-indigo-300"> dashed line</span> = ML predictions. 
              As more data flows through the pipeline, the model adapts and improves! 📈
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PredictionChart;
