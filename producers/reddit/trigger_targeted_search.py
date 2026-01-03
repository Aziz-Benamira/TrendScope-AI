"""
Trigger targeted Reddit searches for movies in metadata collection
"""
import requests
import time

# Movies to search for
MOVIES = [
    "Avatar Fire and Ash",
    "Zootopia 2",
    "Wicked For Good",
    "Five Nights at Freddy's 2",
    "Demon Slayer Infinity Castle",
    "SpongeBob Movie Search for SquarePants",
    "Wake Up Dead Man Knives Out",
    "Frankenstein",
    "Anaconda",
    "Now You See Me Now You Don't",
    "Marty Supreme",
    "Bāhubali The Epic",
    "Omniscient Reader The Prophecy"
]

# Send each movie to Kafka as if TMDB producer sent it
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

for movie in MOVIES:
    message = {
        'title': movie,
        'trigger_targeted_search': True,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
    }
    producer.send('tmdb_stream', value=message)
    print(f"✅ Triggered search for: {movie}")
    time.sleep(0.5)

producer.flush()
print(f"\n🎬 Sent {len(MOVIES)} movies to TMDB stream for targeted search")
