#!/bin/bash
set -e

echo "Installing Python dependencies on Spark master..."
docker-compose exec -T spark-master pip install kafka-python==2.0.2 cassandra-driver==3.28.0 vaderSentiment==3.3.2 textblob==0.17.1 python-dotenv==1.0.0 colorlog==6.8.0

echo "Submitting Spark streaming job..."
docker-compose exec -T spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,com.datastax.spark:spark-cassandra-connector_2.12:3.4.1 \
  --conf spark.cassandra.connection.host=cassandra \
  --conf spark.cassandra.connection.port=9042 \
  --conf spark.executor.memory=1g \
  --conf spark.driver.memory=1g \
  --conf spark.cores.max=2 \
  /opt/spark-apps/spark_streaming_processor.py

echo "Spark job submitted!"
