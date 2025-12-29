#!/bin/bash
set -e

echo "Waiting for Spark Master to be ready..."
sleep 10

echo "Submitting Spark Streaming job to Spark Master..."
docker exec spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,com.datastax.spark:spark-cassandra-connector_2.12:3.4.1 \
  --conf spark.cassandra.connection.host=cassandra \
  --conf spark.cassandra.connection.port=9042 \
  --conf spark.executor.memory=1g \
  --conf spark.driver.memory=1g \
  --conf spark.cores.max=2 \
  --conf spark.sql.streaming.checkpointLocation=/tmp/spark-checkpoint \
  /opt/spark-apps/spark_streaming_processor.py

echo "Spark job completed or failed. Container will exit."
