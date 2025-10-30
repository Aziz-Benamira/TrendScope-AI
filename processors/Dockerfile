FROM python:3.10

WORKDIR /app

# Install Java (required for PySpark)
RUN apt-get update && \
    apt-get install -y default-jre && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

USER 1001

CMD ["python", "spark_streaming_processor.py"]
