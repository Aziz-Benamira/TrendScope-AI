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
    
    def _fetch_tmdb_metadata_realtime(self, title: str) -> Optional[Dict]:
        """
        FALLBACK: Fetch metadata from TMDB API in real-time when not in ChromaDB
        This provides comprehensive movie/TV database coverage without storing everything
        """
        if not TMDB_API_KEY:
            return None
        
        try:
            # Use TMDB multi-search (searches both movies AND TV shows)
            search_url = f"{TMDB_BASE_URL}/search/multi"
            response = requests.get(search_url, params={
                "api_key": TMDB_API_KEY,
                "query": title,
                "language": "en-US"
            }, timeout=10)
            
            if response.status_code != 200:
                return None
            
            results = response.json().get("results", [])
            if not results:
                return None
            
            # Get first result (best match)
            item = results[0]
            media_type = item.get("media_type")  # "movie" or "tv"
            item_id = item.get("id")
            
            if not item_id:
                return None
            
            # Fetch detailed info based on media type
            if media_type == "movie":
                details_url = f"{TMDB_BASE_URL}/movie/{item_id}"
            elif media_type == "tv":
                details_url = f"{TMDB_BASE_URL}/tv/{item_id}"
            else:
                return None
            
            details_resp = requests.get(details_url, params={
                "api_key": TMDB_API_KEY,
                "append_to_response": "credits"
            }, timeout=10)
            
            if details_resp.status_code != 200:
                return None
            
            details = details_resp.json()
            
            # Normalize data structure (movies and TV shows have different fields)
            title_normalized = details.get("title") or details.get("name")
            release_date = details.get("release_date") or details.get("first_air_date")
            
            # Extract cast
            cast_list = []
            credits = details.get("credits", {})
            for actor in credits.get("cast", [])[:5]:
                cast_list.append(actor.get("name"))
            
            # Extract genres
            genres = ",".join([g["name"] for g in details.get("genres", [])])
            
            return {
                "title": title_normalized,
                "overview": details.get("overview", ""),
                "release_date": release_date,
                "genres": genres,
                "cast": ",".join(cast_list),
                "imdb_rating": details.get("vote_average", 0),
                "media_type": media_type
            }
            
        except Exception as e:
            logger.error(f"TMDB real-time fetch error for '{title}': {e}")
            return None
    
    def _extract_movie_from_query(self, query: str) -> Optional[str]:
        """Extract movie/show title from query - remove filler words"""
        query_lower = query.lower().strip()
        
        # Remove common question patterns first (most specific to most general)
        filler_patterns = [
            # Full question phrases
            r'^what\s+(?:do\s+|did\s+|are\s+)?people\s+(?:think|say|saying)\s+about\s+(?:the\s+)?',
            r'^what\s+(?:is|are|was)\s+(?:the\s+)?consensus\s+(?:on|about)\s+(?:the\s+)?',
            r'^tell\s+me\s+about\s+(?:the\s+)?',
            r'^give\s+me\s+(?:the\s+)?reviews?\s+(?:of|for|on)\s+(?:the\s+)?',
            # Specific phrases about actors/performances
            r'\b(?:the\s+)?(?:lead\s+)?actor(?:\'?s)?\s+performance\s+in\s+(?:the\s+)?',
            r'\bperformance\s+(?:in|of)\s+(?:the\s+)?',
            # Media type words
            r'\b(?:the\s+)?(?:movie|film|show|series|serie)\b',
            r'\b(?:netflix|hbo|disney\+|amazon\s+prime|streaming)\b',
            # Time references
            r'\bfrom\s+(?:the\s+)?last\s+\d+\s+hours?\b',
            r'\bbased\s+on\s+reviews?\b',
            r'\?+$'  # Remove trailing question marks
        ]
        
        import re
        title = query_lower
        for pattern in filler_patterns:
            title = re.sub(pattern, '', title)
        
        # Clean up multiple spaces and strip
        title = re.sub(r'\s+', ' ', title).strip()
        
        # If it's too short or empty, return None
        if len(title) < 3:
            return None
        
        return title if title else None
    
    def _check_relevance(self, reviews: List[str], metadatas: List[Dict], query: str, extracted_title: Optional[str]) -> tuple:
        """Smart relevance check - strict for popular content, semantic for new/rare content"""
        if not extracted_title:
            # General query - return all reviews
            return {"has_direct_mentions": True, "mention_count": len(reviews), "title": None}, reviews, metadatas
        
        # For specific movie/show queries, try STRICT first
        title_lower = extracted_title.lower().strip()
        
        # Generate title variants for better matching
        title_variants = [title_lower]
        
        # Handle "dune 2", "dune part 2", "dune: part two", "dune ii"
        if any(x in title_lower for x in [' 2', ' part 2', ' part two', ' ii', ' part ii']):
            # Get base title without sequel markers
            import re
            base = re.sub(r'\s*(?:2|part\s+(?:2|two|ii)|ii)\s*$', '', title_lower).strip()
            if base:
                title_variants.extend([
                    base,
                    f"{base} 2",
                    f"{base} part 2",
                    f"{base} part two",
                    f"{base}: part two",
                    f"{base} ii"
                ])
        
        # Handle "stranger things season 5" -> match "stranger things" alone too
        if 'season' in title_lower:
            import re
            parts = re.split(r'\s+season\s+', title_lower)
            if len(parts) == 2:
                base = parts[0].strip()
                season_num = parts[1].strip()
                title_variants.extend([
                    base,  # "stranger things"
                    f"{base} season {season_num}",  # "stranger things season 5"
                    f"{base} s{season_num}",  # "stranger things s5"
                ])
        
        # Handle "avatar: fire and ash" -> also match just "avatar"
        if ':' in title_lower or ' and ' in title_lower:
            import re
            # Get base franchise name before colon or subtitle
            base = re.split(r':|(?:\s+(?:and|the|of)\s+)', title_lower)[0].strip()
            if base and len(base) > 3:
                title_variants.append(base)
        
        # Remove duplicates while preserving order
        seen = set()
        title_variants = [x for x in title_variants if not (x in seen or seen.add(x))]
        
        # STEP 1: Try STRICT matching
        strict_reviews = []
        strict_metas = []
        
        for review, meta in zip(reviews, metadatas):
            review_lower = review.lower()
            
            # Check if ANY variant appears in the review
            found_match = any(variant in review_lower for variant in title_variants)
            
            if found_match:
                strict_reviews.append(review)
                strict_metas.append(meta)
        
        # STEP 2: Decide strategy based on results
        MIN_REVIEWS_THRESHOLD = 10
        
        if len(strict_reviews) >= MIN_REVIEWS_THRESHOLD:
            # Enough strict matches - use them
            logger.info(f"   Using strict filtering: {len(strict_reviews)} exact matches")
            return {
                "has_direct_mentions": True,
                "mention_count": len(strict_reviews),
                "title": extracted_title
            }, strict_reviews, strict_metas
        else:
            # Too few strict matches - use semantic similarity (top vector search results)
            # These are already ranked by similarity from vector search
            semantic_count = min(25, len(reviews))  # Use top 25 semantic matches
            logger.info(f"   Using semantic similarity: {len(strict_reviews)} exact + {semantic_count-len(strict_reviews)} semantic matches")
            
            return {
                "has_direct_mentions": len(strict_reviews) > 0,
                "mention_count": semantic_count,
                "title": extracted_title,
                "strategy": "semantic"
            }, reviews[:semantic_count], metadatas[:semantic_count]
    
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
        
        # Step 1: HYBRID RAG - Lookup metadata for query enhancement
        metadata_context = None
        enhanced_query = user_query
        
        if extracted_title:
            # Search metadata collection for this movie/show
            query_embedding_for_metadata = self.embedding_model.encode(extracted_title).tolist()
            metadata_context = self.vector_store.search_metadata(query_embedding_for_metadata, n_results=1)
            
            if metadata_context:
                logger.info(f"🎭 Found metadata for '{extracted_title}'")
                
                # Enhance query with cast, genres, keywords from metadata
                enhancement_parts = [user_query]
                
                if metadata_context.get('cast'):
                    cast_names = metadata_context['cast'].split(',')[:3]  # Top 3 actors
                    enhancement_parts.extend(cast_names)
                    logger.info(f"   Cast: {', '.join(cast_names)}")
                
                if metadata_context.get('genres'):
                    genres = metadata_context['genres'].split(',')
                    enhancement_parts.extend(genres)
                
                if metadata_context.get('keywords'):
                    keywords = metadata_context['keywords'].split(',')[:3]
                    enhancement_parts.extend(keywords)
                
                enhanced_query = ' '.join(enhancement_parts)
                logger.info(f"🔍 Enhanced query with metadata keywords")
            else:
                # FALLBACK: Metadata not in ChromaDB - fetch from TMDB API dynamically
                logger.info(f"⚡ Metadata not in ChromaDB - fetching from TMDB API for '{extracted_title}'")
                metadata_context = self._fetch_tmdb_metadata_realtime(extracted_title)
                
                if metadata_context:
                    logger.info(f"✅ Fetched real-time metadata from TMDB for '{extracted_title}'")
                    # Enhance query same way
                    enhancement_parts = [user_query]
                    if metadata_context.get('cast'):
                        cast_names = metadata_context['cast'].split(',')[:3]
                        enhancement_parts.extend(cast_names)
                    if metadata_context.get('genres'):
                        enhancement_parts.extend(metadata_context['genres'].split(','))
                    enhanced_query = ' '.join(enhancement_parts)
                else:
                    logger.warning(f"⚠️ No metadata found for '{extracted_title}' (not in ChromaDB or TMDB)")
        
        # Step 2: Embed the enhanced query
        query_embedding = self.embedding_model.encode(enhanced_query).tolist()
        
        # Step 3: Retrieve relevant reviews using enhanced embedding
        search_results = self.vector_store.search(
            query_embedding=query_embedding,
            movie_title=movie_title,
            n_results=max_reviews,
            hours_back=hours_back
        )
        
        reviews = search_results['documents'][0] if search_results['documents'] else []
        metadatas = search_results['metadatas'][0] if search_results['metadatas'] else []
        
        logger.info(f"📚 Retrieved {len(reviews)} reviews from vector store (last {hours_back} hours)")
        
        # Step 4: STRICT relevance check - only keep reviews that actually mention the movie/show
        relevance_info, filtered_reviews, filtered_metas = self._check_relevance(reviews, metadatas, user_query, extracted_title)
        has_reddit_data = len(filtered_reviews) >= 1  # Need at least 1 relevant review
        
        if extracted_title:
            logger.info(f"🎯 Filtered to {len(filtered_reviews)} reviews that actually mention '{extracted_title}'")
        
        # Step 5: Build response ONLY from Reddit data
        # NO TMDB fallback - project requires real-time streaming data only
        if has_reddit_data:
            # We have recent Reddit data - use it
            top_reviews = filtered_reviews[:50]  # Project requirement: retrieve up to 50 reviews
            top_metadatas = filtered_metas[:50]
            context = self._format_context(top_reviews, top_metadatas)
            answer = self._generate_response(user_query, context, movie_title or extracted_title, relevance_info, hours_back, metadata_context)
            data_source = "reddit"
        else:
            # NO DATA - Be honest, don't hallucinate
            movie_name = extracted_title or movie_title or "this movie/show"
            answer = f"⚠️ No recent Reddit discussions found about '{movie_name}' in the last {hours_back} hours.\n\n"
            answer += "This RAG system only uses real-time streaming data from Reddit. "
            answer += f"Try asking about more popular or recently discussed movies, or increase the time window.\n\n"
            answer += f"Currently monitoring subreddits: r/movies, r/television, r/StrangerThings, r/netflix, r/MarvelStudios, r/DC_Cinematic"
            data_source = "none"
            logger.warning(f"⚠️ No Reddit data found for '{movie_name}' in last {hours_back} hours")
        
        # Step 5: Prepare sample reviews for transparency
        sample_reviews = []
        if has_reddit_data:
            for review, meta in zip(filtered_reviews[:5], metadatas[:5]):
                # Determine the source icon and label
                source_type = meta.get('source', 'reddit')
                if source_type == 'tmdb':
                    source_label = f"TMDB Review"
                    source_icon = "📝"
                else:
                    source_label = meta.get('subreddit', 'reddit')
                    source_icon = "💬"
                
                sample_reviews.append({
                    "text": review[:200] + "..." if len(review) > 200 else review,
                    "sentiment": "positive" if meta.get('sentiment', 0) > 0.1 else "negative" if meta.get('sentiment', 0) < -0.1 else "neutral",
                    "source": source_label,
                    "source_type": source_type,
                    "source_icon": source_icon,
                    "score": meta.get('score', 0),
                    "timestamp": meta.get('timestamp', '')
                })
        
        return {
            "answer": answer,
            "sources_count": len(filtered_reviews) if has_reddit_data else 0,
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
    
    def _generate_response(self, query: str, context: str, movie_title: Optional[str], relevance_info: dict = None, hours_back: int = 24, metadata_context: dict = None) -> str:
        """Generate response using Ollama + Mistral - HYBRID RAG with metadata enrichment"""
        
        # Build context-aware instructions based on relevance
        searched_title = relevance_info.get("title") if relevance_info else None
        mention_count = relevance_info.get("mention_count", 0) if relevance_info else 0
        
        # Emphasize temporal awareness - this is REAL-TIME data
        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")
        time_context = f"These are REAL-TIME Reddit discussions from the last {hours_back} hours (current date: {current_date})."
        
        # Build PROMINENT movie background section - this goes BEFORE Reddit discussions
        movie_background = ""
        release_status_note = ""
        
        if metadata_context:
            movie_background = f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            movie_background += f"🎬 MOVIE/SHOW BACKGROUND KNOWLEDGE\n"
            movie_background += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            if metadata_context.get('title'):
                movie_background += f"\nTitle: {metadata_context['title']}"
            
            if metadata_context.get('overview'):
                movie_background += f"\n\nPlot Summary:\n{metadata_context['overview']}"
            
            if metadata_context.get('genres'):
                movie_background += f"\n\nGenres: {metadata_context['genres']}"
            
            if metadata_context.get('cast'):
                cast_list = metadata_context['cast'].split(',')[:5]
                movie_background += f"\nMain Cast: {', '.join(cast_list)}"
            
            if metadata_context.get('release_date'):
                release_date = metadata_context['release_date']
                movie_background += f"\nRelease Date: {release_date}"
                
                # Determine release status
                try:
                    from datetime import datetime
                    rel_date = datetime.strptime(release_date, "%Y-%m-%d")
                    current = datetime.now()
                    if rel_date > current:
                        movie_background += f"\nStatus: ⚠️ NOT YET RELEASED (upcoming)"
                        release_status_note = "\n\n⚠️ CRITICAL: This content has NOT been released yet. Reddit discussions are about ANTICIPATION, TRAILERS, THEORIES, and EXPECTATIONS - NOT actual viewing experiences. Users are discussing what they HOPE to see, not what they've seen."
                    else:
                        days_since = (current - rel_date).days
                        if days_since <= 7:
                            movie_background += f"\nStatus: ✅ Just Released ({days_since} days ago)"
                            release_status_note = f"\n\n✅ Recently released content ({days_since} days ago). Discussions mix EARLY REACTIONS with initial reviews."
                        else:
                            movie_background += f"\nStatus: ✅ Released ({days_since} days ago)"
                            release_status_note = f"\n\n✅ Discussions are viewer reactions and reviews from people who've watched it."
                except:
                    pass
            
            if metadata_context.get('imdb_rating'):
                movie_background += f"\nIMDb Rating: {metadata_context['imdb_rating']}/10"
            
            movie_background += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            movie_background += f"\nℹ️ Use this background to interpret vague Reddit comments.\n"
            movie_background += f"When users say 'loved it', 'great visuals', 'disappointing', etc.,\n"
            movie_background += f"understand they're referring to THIS specific movie/show.\n"
            movie_background += release_status_note
        
        data_note = f"Analyzing recent Reddit discussions about \"{searched_title or 'movies/shows'}\".\n"
        data_note += f"Found {mention_count} relevant mentions.\n"
        data_note += time_context
        
        prompt = f"""You are analyzing REAL-TIME streaming data from Reddit for a RAG system.

Question: "{query}"
{movie_background}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 REDDIT DISCUSSIONS ({mention_count} sources, last {hours_back} hours)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 CRITICAL INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✅ Use the Movie Background section to understand WHAT movie users are discussing
2. ✅ When comments are vague ("loved it", "disappointing"), interpret them in context of the plot/genre
3. ✅ Base your answer STRICTLY on the Reddit discussions above
4. ❌ DO NOT mention movies NOT in the discussions (no "Dark Knight", "Joker" unless actually mentioned)
5. ✅ Summarize ONLY what ACTUAL Reddit users said
6. ✅ If discussing "{searched_title or 'the content'}", use ONLY opinions from reviews that mention it
7. ✅ If context is limited, acknowledge: "Based on the few recent discussions..."
8. ✅ Pay attention to release status - distinguish anticipation vs actual viewing
9. ✅ Structure your response clearly: opening summary → specific opinions → conclusion
10. ✅ Reference specific aspects from the plot when users discuss them
11. ❌ NEVER hallucinate or invent information not in the context

Current date: {current_date}

Generate a well-structured, informative response based ONLY on the context provided:"""

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
