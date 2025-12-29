#!/bin/bash
set -e

# Set user environment for Hadoop/Spark
export USER=root
export LOGNAME=root
export HADOOP_USER_NAME=root

# Run the Python script
exec python spark_streaming_processor.py
