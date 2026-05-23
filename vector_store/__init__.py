"""vector_store: backend-agnostic vector storage for RAG pipelines."""
 
from .factory import get_vector_store
from .types import CollectionInfo, QueryResult, VectorStore
 
__all__ = [
    "QueryResult",
    "CollectionInfo",
    "VectorStore",
    "get_vector_store",
]