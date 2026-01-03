"""
Quick Reddit Indexer - Fetch movie discussions and index to ChromaDB
"""
import os
import sys
import time
from datetime import datetime
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.embedding_service import EmbeddingService

# Reddit API configuration
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID', '')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET', '')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'TrendScope-AI/1.0')

# Subreddits to fetch from
MOVIE_SUBREDDITS = ['movies', 'TrueFilm', 'MovieSuggestions', 'flicks', 'boxoffice']

# Quality filters
MIN_COMMENT_LENGTH = 50
MAX_COMMENT_LENGTH = 1000


class RedditIndexer:
    def __init__(self):
        self.embedding_service = EmbeddingService(skip_kafka=True)
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.access_token = None
        
    def _get_reddit_token(self):
        """Get Reddit OAuth token"""
        if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
            print("⚠️ Reddit credentials not found in .env file")
            return None
            
        auth = requests.auth.HTTPBasicAuth(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)
        data = {'grant_type': 'client_credentials'}
        headers = {'User-Agent': REDDIT_USER_AGENT}
        
        try:
            response = requests.post('https://www.reddit.com/api/v1/access_token',
                                    auth=auth, data=data, headers=headers)
            response.raise_for_status()
            self.access_token = response.json()['access_token']
            print("✅ Reddit authentication successful")
            return self.access_token
        except Exception as e:
            print(f"❌ Reddit auth failed: {e}")
            return None
    
    def _fetch_subreddit_posts(self, subreddit: str, limit: int = 50):
        """Fetch hot posts from a subreddit"""
        if not self.access_token:
            return []
        
        headers = {
            'Authorization': f'bearer {self.access_token}',
            'User-Agent': REDDIT_USER_AGENT
        }
        
        try:
            url = f'https://oauth.reddit.com/r/{subreddit}/hot'
            response = requests.get(url, headers=headers, params={'limit': limit})
            response.raise_for_status()
            
            posts = response.json()['data']['children']
            print(f"📥 Fetched {len(posts)} posts from r/{subreddit}")
            return posts
        except Exception as e:
            print(f"❌ Error fetching r/{subreddit}: {e}")
            return []
    
    def _fetch_post_comments(self, subreddit: str, post_id: str, limit: int = 20):
        """Fetch comments for a post"""
        if not self.access_token:
            return []
        
        headers = {
            'Authorization': f'bearer {self.access_token}',
            'User-Agent': REDDIT_USER_AGENT
        }
        
        try:
            url = f'https://oauth.reddit.com/r/{subreddit}/comments/{post_id}'
            response = requests.get(url, headers=headers, params={'limit': limit})
            response.raise_for_status()
            
            # Reddit returns [post, comments] array
            data = response.json()
            if len(data) > 1:
                comments = data[1]['data']['children']
                return comments
            return []
        except Exception as e:
            print(f"❌ Error fetching comments for {post_id}: {e}")
            return []
    
    def _is_quality_comment(self, comment_text: str) -> bool:
        """Check if comment meets quality standards"""
        if not comment_text or len(comment_text) < MIN_COMMENT_LENGTH:
            return False
        if len(comment_text) > MAX_COMMENT_LENGTH:
            return False
        
        # Filter out common bot patterns
        bot_indicators = ['I am a bot', '[deleted]', '[removed]', 'AutoModerator']
        if any(indicator in comment_text for indicator in bot_indicators):
            return False
        
        return True
    
    def index_reddit_data(self, max_posts_per_sub: int = 20, max_comments_per_post: int = 10):
        """Fetch Reddit data and index to ChromaDB"""
        print("🚀 Starting Reddit indexing...")
        
        # Get Reddit token
        if not self._get_reddit_token():
            print("❌ Cannot index without Reddit credentials. Add them to .env file:")
            print("   REDDIT_CLIENT_ID=your_client_id")
            print("   REDDIT_CLIENT_SECRET=your_secret")
            return
        
        total_indexed = 0
        
        for subreddit in MOVIE_SUBREDDITS:
            print(f"\n📂 Processing r/{subreddit}...")
            
            # Fetch hot posts
            posts = self._fetch_subreddit_posts(subreddit, limit=max_posts_per_sub)
            
            for post in posts:
                post_data = post['data']
                post_id = post_data['id']
                post_title = post_data['title']
                post_text = post_data.get('selftext', '')
                
                # Skip if post doesn't seem movie-related
                if not any(word in post_title.lower() for word in ['movie', 'film', 'watch', 'review']):
                    continue
                
                print(f"  📝 Post: {post_title[:60]}...")
                
                # Fetch comments
                comments = self._fetch_post_comments(subreddit, post_id, limit=max_comments_per_post)
                
                indexed_in_post = 0
                for comment in comments:
                    if comment['kind'] != 't1':  # Not a comment
                        continue
                    
                    comment_data = comment['data']
                    comment_text = comment_data.get('body', '')
                    
                    # Quality check
                    if not self._is_quality_comment(comment_text):
                        continue
                    
                    # Calculate sentiment
                    sentiment_scores = self.sentiment_analyzer.polarity_scores(comment_text)
                    
                    # Index to ChromaDB
                    metadata = {
                        'subreddit': subreddit,
                        'post_title': post_title,
                        'timestamp': datetime.utcnow().isoformat(),
                        'sentiment': sentiment_scores['compound'],
                        'score': comment_data.get('score', 0),
                        'author': comment_data.get('author', 'unknown')
                    }
                    
                    try:
                        self.embedding_service.add_review(
                            review_text=comment_text,
                            metadata=metadata
                        )
                        indexed_in_post += 1
                        total_indexed += 1
                    except Exception as e:
                        print(f"    ⚠️ Error indexing comment: {e}")
                
                if indexed_in_post > 0:
                    print(f"    ✅ Indexed {indexed_in_post} comments")
                
                # Rate limiting
                time.sleep(0.5)
        
        print(f"\n✅ Indexing complete! Total documents indexed: {total_indexed}")
        print(f"🔍 ChromaDB now has data for RAG queries")


if __name__ == "__main__":
    indexer = RedditIndexer()
    indexer.index_reddit_data(max_posts_per_sub=15, max_comments_per_post=8)
