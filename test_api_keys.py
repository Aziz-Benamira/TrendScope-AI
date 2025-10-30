"""
API Keys Test Script
Tests TMDB and Reddit API credentials
"""
import os
import sys

print("🔍 Testing API Keys...\n")
print("=" * 60)

# Load environment variables
TMDB_API_KEY = "fe5d91bce4689101d187221fa15dadef"
REDDIT_CLIENT_ID = "tWtme35lXpV_18HuiYCVKg"
REDDIT_CLIENT_SECRET = "PPwVuXzujOyv2Im9XyUcaCnjgC9YAw"
REDDIT_USER_AGENT = "TrendScope-AI/1.0"

# Test 1: TMDB API
print("\n1️⃣  Testing TMDB API...")
print("-" * 60)

try:
    import requests
    
    url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}"
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        movies = data.get('results', [])
        print(f"✅ TMDB API: SUCCESS!")
        print(f"   Status Code: {response.status_code}")
        print(f"   Movies Found: {len(movies)}")
        if movies:
            print(f"   Sample Movie: '{movies[0].get('title')}' (Popularity: {movies[0].get('popularity')})")
    elif response.status_code == 401:
        print(f"❌ TMDB API: FAILED - Invalid API Key")
        print(f"   Status Code: {response.status_code}")
        print(f"   Message: {response.json().get('status_message')}")
    else:
        print(f"❌ TMDB API: FAILED")
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.text}")
        
except ImportError:
    print("⚠️  'requests' library not installed. Installing...")
    os.system(f"{sys.executable} -m pip install requests")
    print("   Please run this script again.")
except Exception as e:
    print(f"❌ TMDB API: ERROR - {e}")

# Test 2: Reddit API
print("\n2️⃣  Testing Reddit API...")
print("-" * 60)

try:
    import praw
    
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )
    
    # Test by fetching hot posts from r/movies
    subreddit = reddit.subreddit('movies')
    hot_posts = list(subreddit.hot(limit=5))
    
    print(f"✅ Reddit API: SUCCESS!")
    print(f"   Authenticated: {reddit.read_only}")
    print(f"   Posts Retrieved: {len(hot_posts)}")
    if hot_posts:
        print(f"   Sample Post: '{hot_posts[0].title[:50]}...'")
        print(f"   Post Score: {hot_posts[0].score}")
    
except ImportError:
    print("⚠️  'praw' library not installed. Installing...")
    os.system(f"{sys.executable} -m pip install praw")
    print("   Please run this script again.")
except Exception as e:
    print(f"❌ Reddit API: ERROR - {e}")
    if "401" in str(e) or "invalid" in str(e).lower():
        print("   This likely means your Client ID or Secret is incorrect.")
    elif "429" in str(e):
        print("   Rate limit exceeded. Wait a moment and try again.")

# Summary
print("\n" + "=" * 60)
print("📊 Test Summary")
print("=" * 60)
print("\n✅ = API is working correctly")
print("❌ = API failed - check your credentials")
print("⚠️  = Missing dependencies - install and retry")
print("\nIf both tests passed, you're ready to start TrendScope-AI! 🚀")
print("\nNext steps:")
print("  1. Copy your keys to .env file (not .env.example)")
print("  2. Run: docker-compose up -d")
print("\n")
