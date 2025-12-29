import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, MessageCircle, Clock, Database, Sparkles } from 'lucide-react';
import { sendChatQuery, checkChatHealth } from '../api';

const ChatPanel = ({ selectedMovie = null }) => {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "👋 Hi! I'm your Movie Insight Assistant powered by RAG. Ask me anything about trending movies!\n\nTry questions like:\n• \"Why is Mufasa trending?\"\n• \"What do people think about the acting in Sonic 3?\"\n• \"Is Nosferatu scary?\"",
      sourcesCount: 0,
      timestamp: new Date()
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [ragHealth, setRagHealth] = useState({ status: 'checking' });
  const messagesEndRef = useRef(null);

  // Check RAG health on mount
  useEffect(() => {
    const checkHealth = async () => {
      const health = await checkChatHealth();
      setRagHealth(health);
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll to bottom (only within the messages container)
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  // Pre-fill input when a movie is selected
  useEffect(() => {
    if (selectedMovie) {
      setInput(`Tell me about ${selectedMovie}`);
    }
  }, [selectedMovie]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = {
      role: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const result = await sendChatQuery(input, selectedMovie, 24);
      
      const assistantMessage = {
        role: 'assistant',
        content: result.answer,
        sourcesCount: result.sourcesCount,
        sampleReviews: result.sampleReviews,
        movieFilter: result.movieFilter,
        timeRange: result.timeRange,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Sorry, I encountered an error. Please try again.',
        isError: true,
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      e.stopPropagation();
      handleSend();
    }
  };

  const suggestedQuestions = [
    "Why is this movie trending?",
    "What do critics say about it?",
    "Is it worth watching?",
    "How does it compare to similar movies?"
  ];

  return (
    <div className="flex flex-col h-full bg-white/5 backdrop-blur-lg rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-white/10 bg-gradient-to-r from-purple-500/20 to-pink-500/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-gradient-to-br from-purple-500 to-pink-500 p-2 rounded-xl">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-white font-semibold">Movie Insight Chat</h3>
              <p className="text-purple-200 text-xs">Powered by RAG + Mistral</p>
            </div>
          </div>
          <div className={`flex items-center space-x-1 px-2 py-1 rounded-full text-xs ${
            ragHealth.status === 'healthy' 
              ? 'bg-green-500/20 text-green-300' 
              : ragHealth.status === 'checking'
              ? 'bg-yellow-500/20 text-yellow-300'
              : 'bg-red-500/20 text-red-300'
          }`}>
            <div className={`w-2 h-2 rounded-full ${
              ragHealth.status === 'healthy' ? 'bg-green-400 animate-pulse' :
              ragHealth.status === 'checking' ? 'bg-yellow-400 animate-pulse' :
              'bg-red-400'
            }`} />
            <span>{ragHealth.status === 'healthy' ? 'Online' : ragHealth.status === 'checking' ? 'Checking...' : 'Offline'}</span>
          </div>
        </div>
        {selectedMovie && (
          <div className="mt-2 flex items-center space-x-2 text-purple-200 text-sm">
            <Sparkles className="w-4 h-4" />
            <span>Context: <span className="text-white font-medium">{selectedMovie}</span></span>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[85%] ${message.role === 'user' ? 'order-2' : 'order-1'}`}>
              <div className={`flex items-start space-x-2 ${message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
                <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                  message.role === 'user' 
                    ? 'bg-blue-500' 
                    : 'bg-gradient-to-br from-purple-500 to-pink-500'
                }`}>
                  {message.role === 'user' ? (
                    <User className="w-4 h-4 text-white" />
                  ) : (
                    <Bot className="w-4 h-4 text-white" />
                  )}
                </div>
                <div className={`rounded-2xl px-4 py-3 ${
                  message.role === 'user'
                    ? 'bg-blue-500 text-white'
                    : message.isError
                    ? 'bg-red-500/20 text-red-200'
                    : 'bg-white/10 text-white'
                }`}>
                  <p className="whitespace-pre-wrap text-sm">{message.content}</p>
                  
                  {/* Show sources info for assistant messages */}
                  {message.role === 'assistant' && message.sourcesCount > 0 && (
                    <div className="mt-3 pt-3 border-t border-white/10">
                      <div className="flex items-center space-x-4 text-xs text-purple-200">
                        <div className="flex items-center space-x-1">
                          <Database className="w-3 h-3" />
                          <span>{message.sourcesCount} reviews analyzed</span>
                        </div>
                        {message.timeRange && (
                          <div className="flex items-center space-x-1">
                            <Clock className="w-3 h-3" />
                            <span>Last {message.timeRange}h</span>
                          </div>
                        )}
                      </div>
                      
                      {/* Sample reviews */}
                      {message.sampleReviews && message.sampleReviews.length > 0 && (
                        <div className="mt-2 space-y-1">
                          <p className="text-xs text-purple-300 font-medium">Sample sources:</p>
                          {message.sampleReviews.slice(0, 2).map((review, i) => (
                            <div key={i} className="text-xs bg-white/5 rounded p-2">
                              <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] mr-2 ${
                                review.sentiment === 'positive' ? 'bg-green-500/30 text-green-300' :
                                review.sentiment === 'negative' ? 'bg-red-500/30 text-red-300' :
                                'bg-gray-500/30 text-gray-300'
                              }`}>
                                {review.sentiment}
                              </span>
                              <span className="text-gray-300">{review.text}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
              <p className={`text-[10px] text-gray-500 mt-1 ${message.role === 'user' ? 'text-right' : 'text-left'}`}>
                {message.timestamp.toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}
        
        {/* Loading indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="flex items-center space-x-2 bg-white/10 rounded-2xl px-4 py-3">
              <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
              <span className="text-purple-200 text-sm">Analyzing reviews...</span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested questions */}
      {messages.length <= 1 && (
        <div className="px-4 pb-2">
          <p className="text-xs text-purple-300 mb-2">Suggested questions:</p>
          <div className="flex flex-wrap gap-2">
            {suggestedQuestions.map((q, i) => (
              <button
                key={i}
                onClick={() => setInput(q)}
                className="text-xs bg-white/10 hover:bg-white/20 text-purple-200 px-3 py-1.5 rounded-full transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t border-white/10">
        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="flex items-center space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about any movie..."
            className="flex-1 bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className={`p-3 rounded-xl transition-all ${
              input.trim() && !isLoading
                ? 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white'
                : 'bg-white/10 text-gray-500 cursor-not-allowed'
            }`}
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatPanel;
