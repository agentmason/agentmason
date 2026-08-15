# Vector Store & Embeddings

## Vector Store Architecture

AgentMason uses PostgreSQL with pgvector extension for vector storage and similarity search.

### Why pgvector?

- **Integrated with existing database** - No separate service required
- **SQL-based filtering** - Combine vector search with metadata filters
- **Familiar operations** - Use SQL queries alongside semantic search
- **Development-friendly** - Works with SQLite for local development
- **Production-ready** - Scales with proper indexes and connection pooling

### Alternative Vector Stores

Future implementations can support:
- **Milvus** - Dedicated vector database
- **Qdrant** - Rust-based, high performance
- **Pinecone** - Serverless vector database
- **Weaviate** - GraphQL API, production deployments
- **Vespa** - Yahoo's search platform

Abstraction layer allows switching with minimal code changes.

## Embeddings

### OpenAI Embeddings

**Model:** text-embedding-3-small

- **Dimensions:** 1536
- **Training data:** Up to April 2024
- **Performance:** Optimized for cost/performance
- **Rate limits:** Depends on API plan
- **Pricing:** ~$0.02 per 1M tokens

### Embedding Process

1. **Text Cleaning**
   - Remove excess whitespace
   - Truncate to 8000 characters (OpenAI limit)
   - Preserve structure for semantic meaning

2. **Batch Embedding**
   - Group chunks for efficiency
   - Typical batch size: 50-100 chunks
   - Retry logic for rate limits

3. **Vector Storage**
   - Store as FLOAT8 array in database
   - Index for similarity search
   - Maintain alongside chunk metadata

### Token Counting

Approximate token count:
```
tokens ≈ characters / 4
```

For accurate counts (future):
```python
import tiktoken
encoding = tiktoken.get_encoding("cl100k_base")
tokens = len(encoding.encode(text))
```

## Similarity Search

### Cosine Similarity

AgentMason uses cosine similarity for ranking:

```
similarity = dot_product(vec1, vec2) / (norm(vec1) * norm(vec2))
```

Score range: -1 to 1 (higher = more similar)

### Hybrid Search (Future)

Combine semantic similarity with keyword matching:

```
score = 0.7 * semantic_score + 0.3 * keyword_score
```

Would improve:
- Recall of important but rare terms
- Handling of acronyms
- Domain-specific vocabulary

## Configuration

### Environment Variables

```bash
# Embedding Provider
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Vector Store
VECTOR_STORE=pgvector

# Search Parameters
RAG_TOP_K=5  # Number of results per search
```

### Chunk Configuration

```bash
CHUNK_SIZE=800        # Tokens per chunk
CHUNK_OVERLAP=120     # Overlap between chunks
```

Tuning guidance:
- **Larger chunks (1000+):** Good for dense documents, fewer results
- **Smaller chunks (500):** Good for sparse documents, more precise results
- **More overlap (200+):** Better context continuity, slower performance
- **Less overlap (50):** Faster, less redundancy

## Performance Tuning

### Database Indexes

Automatic indexes created on:
```sql
CREATE INDEX idx_organization ON document_vectors(organization_id);
CREATE INDEX idx_embedding ON document_vectors USING ivfflat (
  embedding vector_cosine_ops
) WITH (lists = 100);
```

IVF (Inverted File) index:
- Trade-off between accuracy and speed
- Good for production use
- Lists parameter controls granularity

### Connection Pooling

```python
AsyncConnectionPool(
    min_size=5,    # Min connections
    max_size=20,   # Max connections
)
```

Tune based on:
- Concurrent API requests
- Average query latency
- Memory constraints

### Query Optimization

```python
# Good: Fetch only needed top-k
results = vector_store.search(
    query_embedding=embedding,
    top_k=5
)

# Avoid: Fetching all results
all_results = vector_store.search(query_embedding=embedding)
limit_results(all_results, 5)
```

## Monitoring & Debugging

### Vector Search Quality

Manually test search quality:
```bash
curl "http://localhost:8000/api/knowledge/search?q=vacation+policy" \
  -H "Authorization: Bearer TOKEN" | jq '.sources[] | .score'
```

Good scores: 0.8+
Acceptable: 0.7+
Poor: <0.6

### Embedding Quality

Check if embeddings capture meaning:
```python
# Semantically similar terms should have similar embeddings
provider = OpenAIEmbeddingProvider(api_key)

vec1 = await provider.embed_text("PTO days off")
vec2 = await provider.embed_text("vacation time")
# cosine(vec1, vec2) should be high (~0.8+)
```

### Database Inspection

```sql
-- Count vectors by organization
SELECT organization_id, COUNT(*) as count
FROM document_vectors
GROUP BY organization_id;

-- Check index statistics
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM document_vectors
WHERE organization_id = 'org123'
ORDER BY embedding <-> embedding '[...]'::vector
LIMIT 5;

-- Verify embedding format
SELECT chunk_id, array_length(embedding::float8[], 1) as dim
FROM document_vectors
LIMIT 1;
```

## Troubleshooting

### No search results despite indexed documents

1. **Check embedding dimension mismatch**
   ```sql
   SELECT COUNT(*) FROM document_vectors WHERE embedding IS NULL;
   ```
   If count > 0, embeddings failed to generate.

2. **Verify organization isolation**
   ```sql
   SELECT COUNT(*) FROM document_vectors
   WHERE organization_id = 'your-org-id';
   ```

3. **Test vector similarity manually**
   ```python
   # Generate embedding for test query
   test_query = "What is PTO?"
   embedding = await provider.embed_text(test_query)
   
   # Search in database
   results = await vector_store.search(
       organization_id='org123',
       query_embedding=embedding,
       top_k=5
   )
   ```

### Slow searches

1. **Check indexes**
   ```sql
   SELECT * FROM pg_indexes 
   WHERE tablename = 'document_vectors';
   ```
   Should have indexes on organization_id and embedding.

2. **Analyze query plan**
   ```sql
   EXPLAIN ANALYZE
   SELECT * FROM document_vectors
   WHERE organization_id = 'org123'
   ORDER BY embedding <-> (SELECT embedding FROM ...)
   LIMIT 5;
   ```

3. **Increase pooling if high concurrency**
   Update `max_size` in connection pool config.

### Embedding API limits

If getting rate limit errors:
1. Implement retry with exponential backoff
2. Batch smaller chunks together
3. Consider higher tier API plan
4. Cache frequently searched embeddings

## Migration Guides

### Switching Embedding Model

1. Update .env:
   ```bash
   OPENAI_EMBEDDING_MODEL=text-embedding-3-large
   ```

2. Reindex all documents:
   ```bash
   for doc_id in $(curl -s http://localhost:8000/api/knowledge/documents \
    -H "Authorization: Bearer TOKEN" | jq -r '.documents[].id');
   do
     curl -X POST http://localhost:8000/api/knowledge/documents/$doc_id/reindex \
       -H "Authorization: Bearer TOKEN"
   done
   ```

3. Verify new embeddings:
   ```sql
   SELECT DISTINCT embedding_model FROM document_chunks;
   ```

### Scaling to Larger Deployments

1. **Separate vector database**
   - Migrate to dedicated Milvus or Qdrant instance
   - Keep PostgreSQL for document metadata
   - Update configuration to point to new store

2. **Caching layer**
   - Cache popular queries
   - Redis for embedding cache
   - Reduces API calls

3. **Batch processing**
   - Use job queue for embedding large documents
   - Parallel ingestion for multiple uploads
   - Background reindexing

## Security Considerations

### API Keys

- Store OPENAI_API_KEY in secrets, not .env
- Rotate keys periodically
- Use rate limiting to detect abuse
- Monitor API usage for anomalies

### Vector Privacy

- Vectors derived from documents
- Don't store raw vectors in logs
- Sensitive business data stays in database
- No data sent to OpenAI beyond embedding input

### Filtering Enforcement

- Always include organization_id in queries
- Never create cross-tenant embeddings
- Use SQL constraints to prevent data leakage
