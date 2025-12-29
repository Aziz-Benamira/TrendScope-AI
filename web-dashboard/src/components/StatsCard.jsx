import React from 'react';

const StatsCard = ({ icon, title, value, color, loading }) => {
  const colorClasses = {
    blue: 'from-blue-500 to-cyan-500',
    purple: 'from-purple-500 to-pink-500',
    pink: 'from-pink-500 to-rose-500',
    green: 'from-green-500 to-emerald-500'
  };

  return (
    <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 shadow-2xl transform transition-all duration-300 hover:scale-105 animate-fadeIn">
      <div className={`bg-gradient-to-br ${colorClasses[color]} w-12 h-12 rounded-xl flex items-center justify-center mb-4`}>
        <div className="text-white">{icon}</div>
      </div>
      <h3 className="text-purple-200 text-sm font-semibold mb-1">{title}</h3>
      {loading ? (
        <div className="h-8 bg-white/10 rounded animate-pulse"></div>
      ) : (
        <p className="text-3xl font-bold text-white">{value}</p>
      )}
    </div>
  );
};

export default StatsCard;
