import { useState, useRef, useEffect } from "react";
import {
  Send,
  Film,
  Bot,
  User,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Database,
} from "lucide-react";
import ReactMarkdown from "react-markdown";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8081";

function App() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        'Hi! I\'m TrendScope-AI, your movie review assistant. Ask me anything about movies - I\'ll search through Reddit discussions and reviews to give you insights!\n\nTry asking:\n- "What do people think about Oppenheimer?"\n- "Is Dune Part Two worth watching?"\n- "What are the criticisms of The Batman?"\n\n💡 Click "Sync Reddit" to fetch fresh movie discussions!',
      sources: [],
    },
  ]);
  const [input, setInput] = useState("");
  const [movieTitle, setMovieTitle] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState(null);
  const [healthStatus, setHealthStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Check health on mount
  useEffect(() => {
    checkHealth();
    fetchStats();
  }, []);

  const checkHealth = async () => {
    try {
      const response = await fetch(`${API_URL}/health`);
      const data = await response.json();
      setHealthStatus(data);
    } catch (err) {
      setHealthStatus({
        status: "error",
        chroma_connected: false,
        ollama_connected: false,
      });
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_URL}/stats`);
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error("Failed to fetch stats:", err);
    }
  };

  const syncReddit = async () => {
    setIsSyncing(true);
    try {
      const response = await fetch(`${API_URL}/reddit/sync`, {
        method: "POST",
      });
      const data = await response.json();

      if (response.ok) {
        // Add system message about sync
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `🔄 Reddit sync complete! Indexed ${
              data.indexed_count
            } new discussions. Total documents: ${
              data.stats?.collection_count || "N/A"
            }`,
            isSystem: true,
          },
        ]);
        fetchStats(); // Refresh stats
      } else {
        throw new Error(data.detail || "Sync failed");
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ Reddit sync failed: ${err.message}. Make sure REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are configured.`,
          isError: true,
        },
      ]);
    } finally {
      setIsSyncing(false);
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    const currentMovieTitle = movieTitle.trim() || null;

    setInput("");
    setError(null);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMessage, movieTitle: currentMovieTitle },
    ]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: userMessage,
          movie_title: currentMovieTitle,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
          sources: data.sources || [],
          movieInfo: data.movie_info,
        },
      ]);
    } catch (err) {
      setError(err.message);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Sorry, I encountered an error. Please make sure the backend server is running.",
          isError: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700 px-4 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-gradient-to-br from-blue-500 to-purple-600 p-2 rounded-lg">
              <Film className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">TrendScope-AI</h1>
              <p className="text-xs text-slate-400">Movie Review Chat</p>
            </div>
          </div>

          {/* Health Status */}
          <div className="flex items-center gap-2">
            {/* Stats Badge */}
            {stats && (
              <div className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-slate-700 text-slate-300">
                <Database className="w-3 h-3" />
                {stats.collection_count || 0} docs
              </div>
            )}

            {/* Sync Reddit Button */}
            <button
              onClick={syncReddit}
              disabled={isSyncing}
              className={`flex items-center gap-1 px-3 py-1 rounded text-xs font-medium transition-colors ${
                isSyncing
                  ? "bg-orange-900/50 text-orange-400 cursor-not-allowed"
                  : "bg-orange-600 hover:bg-orange-500 text-white"
              }`}
            >
              <RefreshCw
                className={`w-3 h-3 ${isSyncing ? "animate-spin" : ""}`}
              />
              {isSyncing ? "Syncing..." : "Sync Reddit"}
            </button>

            {healthStatus && (
              <div
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${
                  healthStatus.status === "healthy"
                    ? "bg-green-900/50 text-green-400"
                    : healthStatus.status === "degraded"
                    ? "bg-yellow-900/50 text-yellow-400"
                    : "bg-red-900/50 text-red-400"
                }`}
              >
                <div
                  className={`w-2 h-2 rounded-full ${
                    healthStatus.status === "healthy"
                      ? "bg-green-400"
                      : healthStatus.status === "degraded"
                      ? "bg-yellow-400"
                      : "bg-red-400"
                  }`}
                />
                {healthStatus.status === "healthy"
                  ? "Connected"
                  : "Check Services"}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Chat Messages */}
      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {messages.map((message, index) => (
            <MessageBubble key={index} message={message} />
          ))}

          {isLoading && (
            <div className="flex items-start gap-3">
              <div className="bg-gradient-to-br from-blue-500 to-purple-600 p-2 rounded-lg">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div className="bg-slate-800 rounded-lg px-4 py-3 flex items-center gap-2">
                <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                <span className="text-slate-400 text-sm">
                  Searching reviews...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Area */}
      <footer className="bg-slate-800 border-t border-slate-700 px-4 py-4">
        <div className="max-w-4xl mx-auto">
          {error && (
            <div className="mb-3 flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          <form onSubmit={sendMessage} className="space-y-3">
            {/* Movie Title Input */}
            <div className="flex items-center gap-2">
              <Film className="w-4 h-4 text-slate-500" />
              <input
                type="text"
                value={movieTitle}
                onChange={(e) => setMovieTitle(e.target.value)}
                placeholder="Movie title (optional - helps narrow down search)"
                className="flex-1 bg-slate-700 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-slate-500"
              />
            </div>

            {/* Message Input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about movie reviews..."
                disabled={isLoading}
                className="flex-1 bg-slate-700 text-white rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-slate-500 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white px-4 py-3 rounded-lg transition-colors"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </form>
        </div>
      </footer>
    </div>
  );
}

function MessageBubble({ message }) {
  const [showSources, setShowSources] = useState(false);
  const isUser = message.role === "user";

  return (
    <div
      className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}
    >
      {/* Avatar */}
      <div
        className={`p-2 rounded-lg ${
          isUser
            ? "bg-slate-600"
            : message.isError
            ? "bg-red-900/50"
            : "bg-gradient-to-br from-blue-500 to-purple-600"
        }`}
      >
        {isUser ? (
          <User className="w-5 h-5 text-white" />
        ) : (
          <Bot className="w-5 h-5 text-white" />
        )}
      </div>

      {/* Message Content */}
      <div className={`flex-1 max-w-[80%] ${isUser ? "text-right" : ""}`}>
        {/* Movie context badge */}
        {isUser && message.movieTitle && (
          <span className="inline-block bg-blue-900/50 text-blue-300 text-xs px-2 py-1 rounded mb-1">
            🎬 {message.movieTitle}
          </span>
        )}

        {/* Movie info for assistant */}
        {!isUser && message.movieInfo && (
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 mb-2">
            <div className="text-sm font-medium text-white">
              {message.movieInfo.title} ({message.movieInfo.year})
            </div>
            {message.movieInfo.overview && (
              <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                {message.movieInfo.overview}
              </p>
            )}
          </div>
        )}

        <div
          className={`rounded-lg px-4 py-3 ${
            isUser
              ? "bg-blue-600 text-white"
              : message.isError
              ? "bg-red-900/30 border border-red-800 text-red-300"
              : "bg-slate-800 text-slate-100"
          }`}
        >
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        </div>

        {/* Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-2">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-300"
            >
              {showSources ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
              {message.sources.length} source
              {message.sources.length > 1 ? "s" : ""}
            </button>

            {showSources && (
              <div className="mt-2 space-y-2">
                {message.sources.map((source, idx) => (
                  <div
                    key={idx}
                    className="bg-slate-800/50 border border-slate-700 rounded p-2 text-xs"
                  >
                    <div className="flex items-center gap-2 text-slate-400 mb-1">
                      <span className="font-medium">{source.author}</span>
                      {source.rating && (
                        <span className="bg-yellow-900/50 text-yellow-400 px-1.5 py-0.5 rounded">
                          ⭐ {source.rating}/10
                        </span>
                      )}
                      <span className="text-slate-500">
                        via {source.source}
                      </span>
                    </div>
                    <p className="text-slate-300">{source.text}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
