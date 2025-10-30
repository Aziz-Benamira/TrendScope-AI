FROM bitnami/spark:3.5.0

USER root

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

USER 1001

CMD ["python", "spark_streaming_processor.py"]
