"""
RAG Service - Query processing and LLM generation using Ollama + Mistral
"""
import logging
import requests
import os
from typing import Dict, List, Optional
from sentence_transformers import SentenceTransformer
import colorlog

# Support both relative and absolute imports
try:
    from .vector_store import VectorStore
    from .config import (
        OLLAMA_BASE_URL,
        OLLAMA_MODEL,
        EMBEDDING_MODEL,
        MAX_REVIEWS_TO_RETRIEVE,
        DEFAULT_TIME_WINDOW_HOURS
    )
except ImportError:
    from vector_store import VectorStore
    from config import (
        OLLAMA_BASE_URL,
        OLLAMA_MODEL,
        EMBEDDING_MODEL,
        MAX_REVIEWS_TO_RETRIEVE,
        DEFAULT_TIME_WINDOW_HOURS
    )

# TMDB API for movie data
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Configure logging
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
))

logger = colorlog.getLogger('RAGService')
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class RAGService:
    """
    RAG (Retrieval-Augmented Generation) Service
    
    1. Embeds user query
    2. Retrieves relevant reviews from ChromaDB
    3. Falls back to TMDB for movie data when Reddit lacks coverage
    4. Generates response using Ollama + Mistral
    """
    
    def __init__(self):
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        self.vector_store = VectorStore()
        
        logger.info(f"✅ RAG Service initialized with model: {OLLAMA_MODEL}")
    
    def _search_tmdb(self, title: str) -> Optional[Dict]:
        """Search TMDB for movie information"""
        if not TMDB_API_KEY:
            return None
        
        try:
            # Search for the movie
            search_url = f"{TMDB_BASE_URL}/search/movie"
            response = requests.get(search_url, params={
                "api_key": TMDB_API_KEY,
                "query": title,
                "language": "en-US"
            }, timeout=10)
            
            if response.status_code == 200:
                results = response.json().get("results", [])
                if results:
                    movie = results[0]
                    movie_id = movie["id"]
                    
                    # Get detailed info including reviews
                    details_url = f"{TMDB_BASE_URL}/movie/{movie_id}"
                    details_resp = requests.get(details_url, params={
                        "api_key": TMDB_API_KEY,
                        "append_to_response": "reviews,credits"
                    }, timeout=10)
                    
                    if details_resp.status_code == 200:
                        details = details_resp.json()
                        return {
                            "title": details.get("title"),
                            "overview": details.get("overview"),
                            "release_date": details.get("release_date"),
                            "vote_average": details.get("vote_average"),
                            "vote_count": details.get("vote_count"),
                            "genres": [g["name"] for g in details.get("genres", [])],
                            "runtime": details.get("runtime"),
                            "reviews": details.get("reviews", {}).get("results", [])[:5],
                            "director": next((c["name"] for c in details.get("credits", {}).get("crew", []) if c["job"] == "Director"), None),
                            "cast": [c["name"] for c in details.get("credits", {}).get("cast", [])[:5]]
                        }
            return None
        except Exception as e:
            logger.error(f"TMDB search error: {e}")
            return None
    
    def _extract_movie_from_query(self, query: str) -> Optional[str]:
        """Try to extract a specific movie/show name from the query"""
        # Common patterns for asking about specific movies
        query_lower = query.lower()
        
        # Look for quoted titles
        import re
        quoted = re.findall(r'"([^"]+)"', query)
        if quoted:
            return quoted[0]
        
        # Look for patterns like "about X", "reviews of X", "what people say about X"
        patterns = [
            r'(?:about|reviews? (?:of|for)|opinions? (?:on|about)|thoughts? (?:on|about))\s+(?:the\s+)?(?:movie|film|show|series)?\s*["\']?([^"\'?]+)["\']?',
            r'(?:movie|film|show|series)\s+["\']?([^"\'?]+)["\']?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                title = match.group(1).strip()
                # Clean up common words at the end
                title = re.sub(r'\s+(is|are|was|were|like|good|bad)$', '', title)
                if len(title) > 2:
                    return title
        
        return None
    
    def _check_relevance(self, reviews: List[str], query: str, extracted_title: Optional[str]) -> tuple:
        """Check how many reviews are relevant and return relevance info"""
        if not extracted_title:
            return {"has_direct_mentions": True, "mention_count": len(reviews), "title": None}, reviews
        
        title_lower = extracted_title.lower()
        title_words = [w for w in title_lower.split() if len(w) > 3]
        
        # Count how many reviews actually mention the title or related words
        relevant_count = 0
        relevant_reviews = []
        
        for review in reviews:
            review_lower = review.lower()
            # Check if title or significant words appear in review
            if title_lower in review_lower or any(word in review_lower for word in title_words):
                relevant_count += 1
                relevant_reviews.append(review)
        
        return {
            "has_direct_mentions": relevant_count > 0,
            "mention_count": relevant_count,
            "title": extracted_title
        }, relevant_reviews if relevant_reviews else reviews
    
    def query(self, 
              user_query: str, 
              movie_title: Optional[str] = None,
              hours_back: int = DEFAULT_TIME_WINDOW_HOURS,
              max_reviews: int = MAX_REVIEWS_TO_RETRIEVE) -> Dict:
        """
        Main RAG query function
        
        Args:
            user_query: Natural language question from user
            movie_title: Optional filter by movie title
            hours_back: Only consider reviews from last N hours
            max_reviews: Maximum number of reviews to retrieve
            
        Returns:
            Dict with answer, sources_count, sample_reviews, etc.
        """
        logger.info(f"🔍 Processing query: '{user_query[:50]}...' | Movie: {movie_title or 'Any'}")
        
        # Try to extract specific movie title from query
        extracted_title = self._extract_movie_from_query(user_query)
        if extracted_title:
            logger.info(f"🎬 Detected movie query: '{extracted_title}'")
        
        # Step 1: Embed the query
        query_embedding = self.embedding_model.encode(user_query).tolist()
        
        # Step 2: Retrieve relevant reviews
        search_results = self.vector_store.search(
            query_embedding=query_embedding,
            movie_title=movie_title,
            n_results=max_reviews,
            hours_back=hours_back
        )
        
        reviews = search_results['documents'][0] if search_results['documents'] else []
        metadatas = search_results['metadatas'][0] if search_results['metadatas'] else []
        
        logger.info(f"📚 Retrieved {len(reviews)} reviews from vector store")
        
        # Step 3: Check if we have genuinely relevant Reddit discussions
        relevance_info, filtered_reviews = self._check_relevance(reviews, user_query, extracted_title)
        has_reddit_data = relevance_info["has_direct_mentions"] and relevance_info["mention_count"] >= 3
        
        # Step 4: If we don't have good Reddit data for a specific movie, get TMDB info
        tmdb_data = None
        if extracted_title and not has_reddit_data:
            logger.info(f"🎬 No Reddit discussions found for '{extracted_title}', fetching TMDB data...")
            tmdb_data = self._search_tmdb(extracted_title)
        
        # Step 5: Build context based on available data
        if has_reddit_data:
            # Good Reddit data - use it
            top_reviews = filtered_reviews[:20]
            top_metadatas = metadatas[:20]
            context = self._format_context(top_reviews, top_metadatas)
            answer = self._generate_response(user_query, context, movie_title or extracted_title, relevance_info)
            data_source = "reddit"
        elif tmdb_data:
            # No Reddit data but have TMDB - generate response from TMDB
            answer = self._generate_tmdb_response(user_query, tmdb_data)
            data_source = "tmdb"
        else:
            # No good data from either source - be honest but try to help
            top_reviews = reviews[:20] if reviews else []
            top_metadatas = metadatas[:20] if metadatas else []
            context = self._format_context(top_reviews, top_metadatas) if top_reviews else ""
            answer = self._generate_response(user_query, context, movie_title or extracted_title, relevance_info)
            data_source = "limited"
        
        # Step 6: Prepare sample reviews for transparency
        sample_reviews = []
        if has_reddit_data:
            for review, meta in zip(filtered_reviews[:5], metadatas[:5]):
                sample_reviews.append({
                    "text": review[:200] + "..." if len(review) > 200 else review,
                    "sentiment": "positive" if meta.get('sentiment', 0) > 0.1 else "negative" if meta.get('sentiment', 0) < -0.1 else "neutral",
                    "source": meta.get('subreddit', 'reddit'),
                    "score": meta.get('score', 0)
                })
        elif tmdb_data and tmdb_data.get("reviews"):
            for review in tmdb_data["reviews"][:3]:
                sample_reviews.append({
                    "text": review.get("content", "")[:200] + "..." if len(review.get("content", "")) > 200 else review.get("content", ""),
                    "sentiment": "neutral",
                    "source": "TMDB",
                    "score": 0
                })
        
        return {
            "answer": answer,
            "sources_count": relevance_info["mention_count"] if has_reddit_data else (len(tmdb_data.get("reviews", [])) if tmdb_data else 0),
            "sample_reviews": sample_reviews,
            "movie_filter": movie_title or extracted_title,
            "time_range_hours": hours_back,
            "data_source": data_source
        }
    
    def _format_context(self, reviews: List[str], metadatas: List[Dict]) -> str:
        """Format reviews into context string for LLM"""
        context_parts = []
        
        for i, (review, meta) in enumerate(zip(reviews, metadatas), 1):
            sentiment = meta.get('sentiment', 0)
            sentiment_label = "positive" if sentiment > 0.1 else "negative" if sentiment < -0.1 else "neutral"
            subreddit = meta.get('subreddit', '')
            score = meta.get('score', 0)
            
            # Truncate very long reviews
            review_text = review[:500] + "..." if len(review) > 500 else review
            
            context_parts.append(
                f"[Review {i}] ({sentiment_label}, score: {score}, from r/{subreddit})\n{review_text}"
            )
        
        return "\n\n".join(context_parts)
    
    def _generate_response(self, query: str, context: str, movie_title: Optional[str], relevance_info: dict = None) -> str:
        """Generate response using Ollama + Mistral"""
        
        # Build context-aware instructions based on relevance
        has_direct = relevance_info.get("has_direct_mentions", True) if relevance_info else True
        searched_title = relevance_info.get("title") if relevance_info else None
        mention_count = relevance_info.get("mention_count", 0) if relevance_info else 0
        
        if searched_title and not has_direct:
            # No direct mentions - be helpful but honest
            data_note = f"""NOTE: I don't have recent Reddit discussions specifically about "{searched_title}" in my database. 
The reviews below are from general movie/TV discussions that may contain related context.
Please be honest if the reviews don't directly address the question."""
        elif searched_title and mention_count < 5:
            # Few mentions - note limited data
            data_note = f"""NOTE: I found {mention_count} discussions mentioning "{searched_title}". 
Some reviews may be tangentially related. Focus on the most relevant ones."""
        else:
            data_note = ""
        
        prompt = f"""Question: "{query}"

{data_note}

Reddit discussions:
{context}

Instructions:
- Answer the question based on what's in the reviews above
- If the reviews discuss the topic directly, summarize what people are saying
- If reviews don't directly discuss the asked topic, be honest: say "While I don't have specific recent discussions about [topic], here's what people are saying about related topics..."
- Include specific opinions, plot points, or theories if mentioned
- Quote specific reviews when relevant
- Be helpful and informative even with limited data

Answer:"""

        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_predict": 500
                    },
                    "keep_alive": "10m"  # Keep model loaded for 10 minutes
                },
                timeout=120  # Longer timeout for first load
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', 'Failed to generate response')
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return f"Error generating response. Status: {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama. Is it running?")
            return "⚠️ Cannot connect to Ollama LLM service. Please ensure Ollama is running."
        except requests.exceptions.Timeout:
            logger.error("Ollama request timed out")
            return "⚠️ Request timed out. The model might be loading or processing a large context."
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return f"⚠️ Error generating response: {str(e)}"
    
    def _generate_tmdb_response(self, query: str, tmdb_data: Dict) -> str:
        """Generate response using TMDB movie database info when Reddit lacks data"""
        
        title = tmdb_data.get("title", "Unknown")
        overview = tmdb_data.get("overview", "")
        vote_avg = tmdb_data.get("vote_average", 0)
        vote_count = tmdb_data.get("vote_count", 0)
        genres = ", ".join(tmdb_data.get("genres", []))
        release_date = tmdb_data.get("release_date", "Unknown")
        runtime = tmdb_data.get("runtime", 0)
        director = tmdb_data.get("director", "Unknown")
        cast = ", ".join(tmdb_data.get("cast", [])[:5])
        reviews = tmdb_data.get("reviews", [])
        
        # Format TMDB reviews if available
        tmdb_reviews_text = ""
        if reviews:
            review_parts = []
            for i, review in enumerate(reviews[:5], 1):
                author = review.get("author", "Anonymous")
                content = review.get("content", "")[:400]
                rating = review.get("rating")
                rating_str = f" (★{rating}/10)" if rating else ""
                review_parts.append(f"[TMDB Review {i}] by {author}{rating_str}:\n{content}...")
            tmdb_reviews_text = "\n\n".join(review_parts)
        
        prompt = f"""Question: "{query}"

I don't have recent Reddit discussions about "{title}", but here's comprehensive information from TMDB (The Movie Database):

**Movie Info:**
- Title: {title}
- Release Date: {release_date}
- Runtime: {runtime} minutes
- Genres: {genres}
- Director: {director}
- Cast: {cast}
- TMDB Rating: {vote_avg}/10 ({vote_count:,} votes)

**Synopsis:**
{overview}

**TMDB User Reviews:**
{tmdb_reviews_text if tmdb_reviews_text else "No reviews available"}

Instructions:
- Answer the user's question using the movie information above
- Be informative and helpful - this is official movie database data
- If they asked about opinions/reviews, summarize what TMDB users think
- If they asked factual questions, provide the facts from the data
- Be transparent that this is from TMDB, not Reddit discussions
- For highly-rated films (>7.5), acknowledge this is a well-received movie
- Keep response conversational and helpful

Answer:"""

        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_predict": 500
                    },
                    "keep_alive": "10m"
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', 'Failed to generate response')
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return f"Error generating response. Status: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Error calling Ollama for TMDB response: {e}")
            # Fallback to a simple formatted response
            return f"""📽️ **{title}** ({release_date[:4] if release_date else 'Unknown'})

I don't have recent Reddit discussions about this film, but here's what I found from TMDB:

**Rating:** {vote_avg}/10 based on {vote_count:,} votes
**Genres:** {genres}
**Director:** {director}
**Cast:** {cast}

**Synopsis:** {overview}

{'This is a highly-rated film on TMDB!' if vote_avg >= 7.5 else ''}"""
    
    def debug_query(self, 
                    user_query: str, 
                    movie_title: Optional[str] = None,
                    hours_back: int = DEFAULT_TIME_WINDOW_HOURS,
                    max_reviews: int = MAX_REVIEWS_TO_RETRIEVE) -> Dict:
        """
        Debug version of query - returns the full context sent to LLM
        """
        logger.info(f"🔍 DEBUG Processing query: '{user_query[:50]}...'")
        
        # Step 1: Embed the query
        query_embedding = self.embedding_model.encode(user_query).tolist()
        
        # Step 2: Retrieve relevant reviews
        search_results = self.vector_store.search(
            query_embedding=query_embedding,
            movie_title=movie_title,
            n_results=max_reviews,
            hours_back=hours_back
        )
        
        reviews = search_results['documents'][0] if search_results['documents'] else []
        metadatas = search_results['metadatas'][0] if search_results['metadatas'] else []
        distances = search_results['distances'][0] if search_results['distances'] else []
        
        # Step 3: Format context
        context = self._format_context(reviews, metadatas)
        
        # Step 4: Build the full prompt (same as _generate_response)
        movie_context = f"about '{movie_title}'" if movie_title else ""
        
        full_prompt = f"""You are a movie review analyst. Your job is to answer questions about movies and TV shows based ONLY on the Reddit reviews provided below.

QUESTION: {user_query}

REDDIT REVIEWS:
{context}

IMPORTANT INSTRUCTIONS:
- Answer the specific question asked: "{user_query}"
- ONLY use information from the reviews above - do not make up information
- If the question asks about a specific movie/show (like "Stranger Things"), focus your answer on that topic
- Quote or reference specific reviews when possible (e.g., "One user said...")
- If the reviews don't contain relevant information to answer the question, say "Based on the reviews I have, I couldn't find specific discussions about [topic]"
- Keep your answer focused and concise (2-3 paragraphs)
- Do NOT give generic film criticism advice - answer the actual question

Answer:"""

        # Return debug info
        return {
            "query": user_query,
            "movie_filter": movie_title,
            "hours_back": hours_back,
            "max_reviews_requested": max_reviews,
            "reviews_found": len(reviews),
            "reviews_with_distances": [
                {
                    "text": review[:300] + "..." if len(review) > 300 else review,
                    "distance": float(dist),
                    "movie_title": meta.get("movie_title_original", "unknown"),
                    "subreddit": meta.get("subreddit", ""),
                    "sentiment": meta.get("sentiment", 0),
                    "score": meta.get("score", 0)
                }
                for review, meta, dist in zip(reviews[:20], metadatas[:20], distances[:20])  # First 20
            ],
            "full_context_length": len(context),
            "full_prompt_length": len(full_prompt),
            "full_prompt": full_prompt[:5000] + "..." if len(full_prompt) > 5000 else full_prompt  # Truncate for readability
        }
    
    def get_available_movies(self) -> List[str]:
        """Get list of movies available in the vector store"""
        return self.vector_store.get_movies_list()
    
    def get_stats(self) -> Dict:
        """Get RAG system statistics"""
        vector_stats = self.vector_store.get_stats()
        return {
            **vector_stats,
            "llm_model": OLLAMA_MODEL,
            "embedding_model": EMBEDDING_MODEL
        }
    
    def health_check(self) -> Dict:
        """Check health of all RAG components"""
        health = {
            "vector_store": False,
            "ollama": False,
            "embedding_model": True  # Already loaded if we got here
        }
        
        # Check vector store
        try:
            self.vector_store.get_stats()
            health["vector_store"] = True
        except:
            pass
        
        # Check Ollama
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            health["ollama"] = response.status_code == 200
        except:
            pass
        
        return health
