FROM apache/spark:3.5.0

USER root

# Remove existing spark user and create a new one
RUN userdel -r spark 2>/dev/null || true && \
    useradd -m -u 1000 -s /bin/bash spark && \
    mkdir -p /home/spark/.ivy2 && \
    chown -R spark:spark /home/spark

# Install Python dependencies
RUN pip install kafka-python==2.0.2 cassandra-driver==3.28.0 vaderSentiment==3.3.2 textblob==0.17.1 python-dotenv==1.0.0 colorlog==6.8.0

WORKDIR /app
COPY . /app/
RUN chown -R spark:spark /app

# Switch to the spark user
USER spark

# Set environment variables
ENV HOME=/home/spark
ENV USER=spark
ENV LOGNAME=spark

# Create submission script with CLUSTER deploy mode
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Waiting for Spark Master..."\n\
sleep 15\n\
echo "Submitting Spark job in CLUSTER mode..."\n\
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode cluster \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,com.datastax.spark:spark-cassandra-connector_2.12:3.4.1 \
  --conf spark.cassandra.connection.host=cassandra \
  --conf spark.cassandra.connection.port=9042 \
  --conf spark.executor.memory=1g \
  --conf spark.driver.memory=1g \
  --conf spark.cores.max=2 \
  --conf spark.driver.supervise=true \
  /app/spark_streaming_processor.py\n\
echo "Job submitted! Keeping container alive to monitor..."\n\
tail -f /dev/null' > /app/submit.sh && chmod +x /app/submit.sh

CMD ["/app/submit.sh"]
