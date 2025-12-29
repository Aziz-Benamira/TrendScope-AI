"""
RAG (Retrieval-Augmented Generation) Module for TrendScope-AI
Provides real-time movie review insights using vector search and LLM generation
"""

from .embedding_service import EmbeddingService
from .rag_service import RAGService
from .vector_store import VectorStore

__all__ = ['EmbeddingService', 'RAGService', 'VectorStore']
