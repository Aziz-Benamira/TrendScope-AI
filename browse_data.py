"""Quick script to browse ChromaDB data"""
import chromadb

client = chromadb.HttpClient(host='localhost', port=8000)
coll = client.get_collection('movie_reviews')

print(f"📊 Total documents in ChromaDB: {coll.count()}")
print("\n" + "="*60)
print("🔍 Sample Reddit Documents:")
print("="*60)

# Get sample documents
results = coll.get(limit=10, include=['documents', 'metadatas'])

for i, doc_id in enumerate(results['ids']):
    metadata = results['metadatas'][i]
    doc = results['documents'][i]
    
    source = metadata.get('source', 'N/A')
    subreddit = metadata.get('subreddit', 'N/A')
    sentiment = metadata.get('sentiment_label', 'N/A')
    movie = metadata.get('movie_title', metadata.get('movies_mentioned', 'N/A'))
    
    print(f"\n📝 Document {i+1}")
    print(f"   Source: {source} | Subreddit: r/{subreddit}")
    print(f"   Sentiment: {sentiment} | Movie: {movie}")
    print(f"   Content: {doc[:200]}...")
    print("-"*60)

# Get stats by subreddit
print("\n\n📈 Documents by Subreddit:")
for sub in ['movies', 'horror', 'scifi', 'MovieSuggestions', 'TrueFilm']:
    try:
        sub_results = coll.get(where={"subreddit": sub}, limit=1000)
        print(f"   r/{sub}: {len(sub_results['ids'])} documents")
    except:
        pass

# Get stats by sentiment
print("\n😊 Documents by Sentiment:")
for sentiment in ['positive', 'negative', 'neutral']:
    try:
        sent_results = coll.get(where={"sentiment_label": sentiment}, limit=1000)
        print(f"   {sentiment}: {len(sent_results['ids'])} documents")
    except:
        pass
