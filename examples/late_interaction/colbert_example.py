#!/usr/bin/env python3
"""
ColBERT Late Interaction Example

This example demonstrates how to use the ColBERT late interaction model with AstraDB:
1. Sets up a ColBERT model and pipeline
2. Loads and indexes sample documents
3. Performs searches with various parameters
4. Shows how to use optimization features like token pooling

Requirements:
- An AstraDB instance with vector search capabilities
- ColBERT library installed (pip install colbert-ai)
"""

import asyncio
import json
import os
import uuid
from dotenv import load_dotenv
from typing import Dict, Any, List

from astrapy import DataAPIClient

from late_interaction import LateInteractionPipeline, ColBERTModel


# Sample documents for indexing
SAMPLE_DOCUMENTS = [
    {
        "content": "AstraDB is a vector database that enables developers to build AI applications with vector search.",
        "metadata": {"source": "docs", "topic": "database", "category": "technical"}
    },
    {
        "content": "Vector search allows you to find similar items based on their vector embeddings rather than exact keyword matches.",
        "metadata": {"source": "docs", "topic": "search", "category": "technical"}
    },
    {
        "content": "Late interaction models like ColBERT provide higher accuracy than dense retrievers by comparing individual token pairs.",
        "metadata": {"source": "blog", "topic": "retrieval", "category": "technical"}
    },
    {
        "content": "Python is a high-level programming language known for its readability and simplicity.",
        "metadata": {"source": "wiki", "topic": "programming", "category": "education"}
    },
    {
        "content": "Machine learning algorithms learn patterns from data to make predictions or decisions without explicit programming.",
        "metadata": {"source": "course", "topic": "ai", "category": "education"}
    },
]


async def setup_pipeline() -> LateInteractionPipeline:
    """Set up the ColBERT pipeline with AstraDB."""
    # Load environment variables
    load_dotenv()
    
    # Required environment variables for AstraDB
    astra_token = os.getenv("ASTRA_TOKEN")
    astra_api_endpoint = os.getenv("ASTRA_API_ENDPOINT")
    
    if not astra_token or not astra_api_endpoint:
        raise ValueError(
            "Please set ASTRA_TOKEN and ASTRA_API_ENDPOINT environment variables"
        )
    
    # Create async database client
    db_client = DataAPIClient(token=astra_token)
    db = db_client.get_async_database(api_endpoint=astra_api_endpoint)
    
    # Create a ColBERT model
    # You can choose different models like colbert-ir/colbertv2.0, 
    # stanford-crfm/colbert-ir-v2, or answerdotai/answerai-colbert-small-v1
    model = ColBERTModel(
        model_name="answerdotai/answerai-colbert-small-v1",
        # Use 'cuda' if you have a GPU available
        device="cpu"  
    )
    
    # Create pipeline with customized parameters
    pipeline = LateInteractionPipeline(
        db=db,
        model=model,
        base_table_name="colbert_example",
        # Doc pooling reduces token count by this factor (None to disable)
        doc_pool_factor=2,  
        # Query pooling combines tokens within this cosine distance (0 to disable)
        query_pool_distance=0.03,
        # Default concurrency for async operations
        default_concurrency_limit=5,
    )
    
    # Initialize the tables
    await pipeline.initialize()
    
    return pipeline


async def index_sample_documents(pipeline: LateInteractionPipeline) -> List[uuid.UUID]:
    """Index sample documents into the ColBERT pipeline."""
    print("Indexing sample documents...")
    doc_ids = []
    
    # Index documents individually
    for i, doc in enumerate(SAMPLE_DOCUMENTS[:2]):
        doc_id = await pipeline.index_document(
            content=doc["content"],
            metadata=doc["metadata"]
        )
        doc_ids.append(doc_id)
        print(f"Indexed document {i+1}/2 with ID: {doc_id}")
    
    # Index remaining documents in bulk
    remaining_docs = SAMPLE_DOCUMENTS[2:]
    bulk_contents = [doc["content"] for doc in remaining_docs]
    bulk_metadata = [doc["metadata"] for doc in remaining_docs]
    
    bulk_ids = await pipeline.bulk_index_documents(
        documents=bulk_contents,
        metadata_list=bulk_metadata,
        max_concurrency=3
    )
    doc_ids.extend(bulk_ids)
    print(f"Bulk indexed {len(bulk_ids)} additional documents")
    
    return doc_ids


async def perform_searches(pipeline: LateInteractionPipeline):
    """Perform different searches to demonstrate ColBERT capabilities."""
    print("\nPerforming searches...")
    
    # Basic search
    query = "vector database"
    results = await pipeline.search(query=query, k=3)
    
    print(f"\nSearch results for '{query}':")
    for i, (doc_id, score, metadata) in enumerate(results):
        # Fetch document to get content
        doc = await pipeline.get_document(doc_id)
        print(f"{i+1}. Score: {score:.4f}")
        print(f"   Content: {doc['content']}")
        print(f"   Metadata: {json.dumps(metadata)}")
    
    # Search with filtering by metadata
    query = "programming"
    filter_condition = {"metadata": {"$contains": "\"category\":\"education\""}}
    results = await pipeline.search(
        query=query, 
        k=2,
        filter_condition=filter_condition
    )
    
    print(f"\nFiltered search results for '{query}' (category=education):")
    for i, (doc_id, score, metadata) in enumerate(results):
        doc = await pipeline.get_document(doc_id)
        print(f"{i+1}. Score: {score:.4f}")
        print(f"   Content: {doc['content']}")
        print(f"   Metadata: {json.dumps(metadata)}")
    
    # Advanced search with customized parameters
    query = "machine learning algorithms"
    results = await pipeline.search(
        query=query,
        k=3,
        # Number of tokens to retrieve per query token
        n_ann_tokens=200,
        # Number of document candidates for MaxSim scoring
        n_maxsim_candidates=20
    )
    
    print(f"\nAdvanced search results for '{query}':")
    for i, (doc_id, score, metadata) in enumerate(results):
        doc = await pipeline.get_document(doc_id)
        print(f"{i+1}. Score: {score:.4f}")
        print(f"   Content: {doc['content']}")
        print(f"   Metadata: {json.dumps(metadata)}")


async def main():
    # Set up the pipeline
    pipeline = await setup_pipeline()
    
    try:
        # Index documents
        doc_ids = await index_sample_documents(pipeline)
        
        # Perform searches
        await perform_searches(pipeline)
        
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())