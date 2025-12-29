"""
IMDb Dataset Loader
Loads and processes IMDb TSV files for feature enrichment
Reference: https://datasets.imdbws.com/

Dataset Structure:
1. title.basics.tsv - Core movie metadata (tconst, title, year, genres, runtime)
2. title.ratings.tsv - Ratings and vote counts (tconst, averageRating, numVotes)
3. title.principals.tsv - Cast and crew (tconst, nconst, category, characters)
4. name.basics.tsv - Person information (nconst, name, birthYear, profession)
5. title.akas.tsv - Alternative titles (titleId, region, language, title)
6. title.crew.tsv - Directors and writers
7. title.episode.tsv - TV episode information

Usage for TrendScope-AI:
- Enrich TMDB movies with IMDb ratings
- Provide historical context (release year, runtime)
- Add cast/director information for better search
- Use as features for River online learning model
"""

import pandas as pd
import os
from typing import Dict, Optional, List
import logging
from cassandra.cluster import Cluster
from cassandra.query import BatchStatement, SimpleStatement
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IMDbDatasetLoader:
    """Load and index IMDb datasets for fast lookups"""
    
    def __init__(self, data_dir: str = "/app/data/imdb"):
        self.data_dir = data_dir
        self.title_basics = None
        self.title_ratings = None
        self.title_principals = None
        self.name_basics = None
        self.title_akas = None
        
        # Create indices for fast lookups
        self.title_index = {}  # primaryTitle -> tconst mapping
        self.tconst_index = {}  # tconst -> full movie data
        
    def load_datasets(self):
        """Load all IMDb TSV files into memory"""
        logger.info("Loading IMDb datasets...")
        
        try:
            # 1. Load title basics (core metadata)
            logger.info("Loading title.basics.tsv...")
            self.title_basics = pd.read_csv(
                f"{self.data_dir}/title.basics.tsv",
                sep='\t',
                na_values='\\N',
                dtype={
                    'tconst': str,
                    'titleType': str,
                    'primaryTitle': str,
                    'isAdult': str,
                    'startYear': str,
                    'runtimeMinutes': str,
                    'genres': str
                }
            )
            
            # Filter to only movies (exclude TV series, episodes, etc.)
            self.title_basics = self.title_basics[
                self.title_basics['titleType'].isin(['movie', 'tvMovie'])
            ]
            logger.info(f"Loaded {len(self.title_basics)} movies")
            
            # 2. Load ratings
            logger.info("Loading title.ratings.tsv...")
            self.title_ratings = pd.read_csv(
                f"{self.data_dir}/title.ratings.tsv",
                sep='\t',
                dtype={
                    'tconst': str,
                    'averageRating': float,
                    'numVotes': int
                }
            )
            logger.info(f"Loaded {len(self.title_ratings)} ratings")
            
            # 3. Load principals (cast/crew) - sample only for memory
            logger.info("Loading title.principals.tsv (sampling)...")
            self.title_principals = pd.read_csv(
                f"{self.data_dir}/title.principals.tsv",
                sep='\t',
                na_values='\\N',
                nrows=1000000,  # Limit to save memory
                dtype={
                    'tconst': str,
                    'nconst': str,
                    'category': str
                }
            )
            logger.info(f"Loaded {len(self.title_principals)} principal records")
            
            # 4. Load name basics (actors/directors)
            logger.info("Loading name.basics.tsv (sampling)...")
            self.name_basics = pd.read_csv(
                f"{self.data_dir}/name.basics.tsv",
                sep='\t',
                na_values='\\N',
                nrows=500000,  # Limit to save memory
                dtype={
                    'nconst': str,
                    'primaryName': str,
                    'primaryProfession': str
                }
            )
            logger.info(f"Loaded {len(self.name_basics)} names")
            
            # 5. Build search indices
            self._build_indices()
            
            logger.info("✓ All IMDb datasets loaded successfully!")
            
        except Exception as e:
            logger.error(f"Error loading IMDb datasets: {e}")
            raise
    
    def _build_indices(self):
        """Build search indices for fast lookups"""
        logger.info("Building search indices...")
        
        # Merge basics with ratings
        enriched = self.title_basics.merge(
            self.title_ratings,
            on='tconst',
            how='left'
        )
        
        # Create title -> tconst index (for searching by movie name)
        for _, row in enriched.iterrows():
            # Skip rows with missing titles
            if pd.isna(row['primaryTitle']):
                continue
                
            title = str(row['primaryTitle']).lower().strip()
            self.title_index[title] = row['tconst']
            
            # Store full movie data by tconst
            self.tconst_index[row['tconst']] = {
                'tconst': row['tconst'],
                'title': row['primaryTitle'],
                'original_title': row.get('originalTitle'),
                'year': int(row['startYear']) if pd.notna(row['startYear']) else None,
                'runtime': int(row['runtimeMinutes']) if pd.notna(row['runtimeMinutes']) else None,
                'genres': row['genres'].split(',') if pd.notna(row['genres']) else [],
                'imdb_rating': float(row['averageRating']) if pd.notna(row['averageRating']) else None,
                'imdb_votes': int(row['numVotes']) if pd.notna(row['numVotes']) else None
            }
        
        logger.info(f"Indexed {len(self.title_index)} movie titles")
    
    def search_movie(self, title: str) -> Optional[Dict]:
        """Search for a movie by title and return enriched metadata"""
        title_lower = title.lower().strip()
        
        # Try exact match first
        if title_lower in self.title_index:
            tconst = self.title_index[title_lower]
            return self.tconst_index.get(tconst)
        
        # Try partial match
        for indexed_title, tconst in self.title_index.items():
            if title_lower in indexed_title or indexed_title in title_lower:
                return self.tconst_index.get(tconst)
        
        return None
    
    def enrich_tmdb_movie(self, tmdb_title: str, tmdb_data: Dict) -> Dict:
        """Enrich TMDB movie data with IMDb metadata"""
        imdb_data = self.search_movie(tmdb_title)
        
        if imdb_data:
            # Merge TMDB and IMDb data
            enriched = tmdb_data.copy()
            enriched['imdb_rating'] = imdb_data['imdb_rating']
            enriched['imdb_votes'] = imdb_data['imdb_votes']
            enriched['imdb_tconst'] = imdb_data['tconst']
            enriched['genres_imdb'] = imdb_data['genres']
            enriched['year'] = imdb_data['year']
            enriched['runtime'] = imdb_data['runtime']
            
            # Calculate composite score (TMDB + IMDb)
            if imdb_data['imdb_rating'] and tmdb_data.get('vote_average'):
                enriched['composite_rating'] = (
                    0.5 * float(tmdb_data['vote_average']) +
                    0.5 * float(imdb_data['imdb_rating'])
                )
            
            logger.debug(f"Enriched '{tmdb_title}' with IMDb data")
            return enriched
        
        logger.debug(f"No IMDb match found for '{tmdb_title}'")
        return tmdb_data
    
    def get_cast_and_crew(self, tconst: str, limit: int = 5) -> Dict:
        """Get cast and crew for a movie"""
        if self.title_principals is None or self.name_basics is None:
            return {}
        
        # Get principals for this movie
        principals = self.title_principals[
            self.title_principals['tconst'] == tconst
        ].head(limit)
        
        cast_crew = {
            'actors': [],
            'directors': [],
            'writers': []
        }
        
        for _, principal in principals.iterrows():
            nconst = principal['nconst']
            category = principal['category']
            
            # Get person name
            person = self.name_basics[self.name_basics['nconst'] == nconst]
            if not person.empty:
                name = person.iloc[0]['primaryName']
                
                if category == 'actor' or category == 'actress':
                    cast_crew['actors'].append(name)
                elif category == 'director':
                    cast_crew['directors'].append(name)
                elif category == 'writer':
                    cast_crew['writers'].append(name)
        
        return cast_crew
    
    def get_top_rated_movies(self, min_votes: int = 10000, limit: int = 100) -> List[Dict]:
        """Get top-rated movies for feature store initialization"""
        if self.title_basics is None or self.title_ratings is None:
            return []
        
        # Merge and filter
        top_movies = self.title_basics.merge(
            self.title_ratings,
            on='tconst',
            how='inner'
        )
        
        # Filter by minimum votes
        top_movies = top_movies[top_movies['numVotes'] >= min_votes]
        
        # Sort by rating
        top_movies = top_movies.sort_values('averageRating', ascending=False).head(limit)
        
        results = []
        for _, row in top_movies.iterrows():
            results.append({
                'tconst': row['tconst'],
                'title': row['primaryTitle'],
                'year': int(row['startYear']) if pd.notna(row['startYear']) else None,
                'rating': float(row['averageRating']),
                'votes': int(row['numVotes']),
                'genres': row['genres'].split(',') if pd.notna(row['genres']) else []
            })
        
        return results


class IMDbFeatureStore:
    """Store IMDb features in Cassandra for fast access"""
    
    def __init__(self, cassandra_host: str = 'cassandra'):
        self.cluster = Cluster([cassandra_host])
        self.session = None
        self._init_schema()
    
    def _init_schema(self):
        """Initialize Cassandra schema for IMDb features"""
        self.session = self.cluster.connect()
        
        # Create keyspace
        self.session.execute("""
            CREATE KEYSPACE IF NOT EXISTS imdb_features
            WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
        """)
        
        self.session.set_keyspace('imdb_features')
        
        # Create movie_metadata table
        self.session.execute("""
            CREATE TABLE IF NOT EXISTS movie_metadata (
                tconst text PRIMARY KEY,
                title text,
                year int,
                runtime int,
                genres list<text>,
                imdb_rating float,
                imdb_votes int,
                cast list<text>,
                directors list<text>,
                composite_rating float
            )
        """)
        
        # Create title index for searches
        self.session.execute("""
            CREATE INDEX IF NOT EXISTS ON movie_metadata (title)
        """)
        
        logger.info("✓ IMDb feature store schema initialized")
    
    def store_movie(self, movie_data: Dict):
        """Store enriched movie data"""
        insert = SimpleStatement("""
            INSERT INTO movie_metadata 
            (tconst, title, year, runtime, genres, imdb_rating, imdb_votes, 
             cast, directors, composite_rating)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """)
        
        self.session.execute(insert, (
            movie_data.get('tconst'),
            movie_data.get('title'),
            movie_data.get('year'),
            movie_data.get('runtime'),
            movie_data.get('genres', []),
            movie_data.get('imdb_rating'),
            movie_data.get('imdb_votes'),
            movie_data.get('cast', []),
            movie_data.get('directors', []),
            movie_data.get('composite_rating')
        ))
    
    def get_movie_features(self, title: str) -> Optional[Dict]:
        """Retrieve movie features from store"""
        query = "SELECT * FROM movie_metadata WHERE title = %s LIMIT 1"
        rows = self.session.execute(query, [title])
        
        row = rows.one()
        if row:
            return {
                'tconst': row.tconst,
                'title': row.title,
                'year': row.year,
                'runtime': row.runtime,
                'genres': row.genres,
                'imdb_rating': row.imdb_rating,
                'imdb_votes': row.imdb_votes,
                'cast': row.cast,
                'directors': row.directors,
                'composite_rating': row.composite_rating
            }
        return None
    
    def close(self):
        """Cleanup"""
        if self.cluster:
            self.cluster.shutdown()


def main():
    """Main entry point for loading IMDb datasets"""
    logger.info("=" * 60)
    logger.info("IMDb Dataset Loader - TrendScope-AI")
    logger.info("=" * 60)
    
    # Initialize loader with Docker volume path
    loader = IMDbDatasetLoader(data_dir="/data/imdb_datasets")
    
    # Load datasets
    loader.load_datasets()
    
    # Test search
    test_movies = ["Fight Club", "The Shawshank Redemption", "Pulp Fiction"]
    
    logger.info("\nTesting movie search:")
    for movie in test_movies:
        result = loader.search_movie(movie)
        if result:
            logger.info(f"✓ {movie}: IMDb {result['imdb_rating']}/10 ({result['imdb_votes']:,} votes)")
        else:
            logger.warning(f"✗ {movie}: Not found")
    
    # Initialize feature store
    logger.info("\nInitializing feature store...")
    feature_store = IMDbFeatureStore()
    
    # Store top 100 movies
    top_movies = loader.get_top_rated_movies(min_votes=50000, limit=100)
    logger.info(f"Storing {len(top_movies)} top-rated movies...")
    
    for movie in top_movies:
        # Get cast/crew
        cast_crew = loader.get_cast_and_crew(movie['tconst'])
        movie.update(cast_crew)
        
        # Store in Cassandra
        feature_store.store_movie(movie)
    
    logger.info("✓ Feature store populated!")
    
    # Cleanup
    feature_store.close()
    
    logger.info("\n" + "=" * 60)
    logger.info("IMDb datasets loaded and indexed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
