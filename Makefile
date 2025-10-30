# TrendScope-AI Makefile
# Convenience commands for Docker Compose operations

.PHONY: help build up down restart logs clean init test

help: ## Show this help message
	@echo "TrendScope-AI - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Build all Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

restart: ## Restart all services
	docker-compose restart

logs: ## View logs from all services
	docker-compose logs -f

clean: ## Remove all containers, volumes, and images
	docker-compose down -v --rmi all

init: ## Initialize Cassandra schema
	docker-compose up -d cassandra
	@echo "Waiting for Cassandra to be ready..."
	@sleep 30
	docker-compose run --rm -v $$(pwd)/storage:/app python:3.10-slim bash -c "cd /app && pip install -r requirements.txt && python init_cassandra.py"

test: ## Run tests
	pytest tests/ -v

status: ## Show status of all services
	docker-compose ps

kafka-topics: ## List all Kafka topics
	docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

cassandra-shell: ## Open Cassandra CQL shell
	docker-compose exec cassandra cqlsh

spark-shell: ## Open Spark shell
	docker-compose exec spark-master spark-shell

dev: ## Start in development mode with logs
	docker-compose up

rebuild: ## Rebuild and restart all services
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d
