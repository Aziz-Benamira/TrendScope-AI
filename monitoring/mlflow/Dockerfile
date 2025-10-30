FROM python:3.10-slim

WORKDIR /mlflow

RUN pip install --no-cache-dir mlflow==2.9.2 psycopg2-binary

EXPOSE 5000

CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000"]
