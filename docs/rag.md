# AgentMason Phase 3: Business Knowledge & RAG

## Overview

Phase 3 implements a complete Retrieval-Augmented Generation (RAG) system enabling AgentMason to ingest business documents, embed them into a vector store, and provide grounded AI responses with citations.

## Architecture

### Document Ingestion Pipeline

```
File Upload
    ↓
Validation (MIME type, size)
    ↓
Storage (LocalFileStorage)
    ↓
Database Record
    ↓
Async Processing Job
    ↓
Document Parsing (PDF, DOCX, TXT, Markdown, CSV, JSON)
    ↓
Normalization & Cleaning
    ↓
Chunking (800 tokens, 120 overlap)
    ↓
Batch Embedding (OpenAI text-embedding-3-small)
    ↓
Vector Storage (PostgreSQL + pgvector)
    ↓
Status: INDEXED
```

### RAG Query Pipeline

```
User Query
    ↓
Generate Query Embedding
    ↓
Vector Search (pgvector)
    ↓
Retrieve Top K Chunks
    ↓
Build Formatted Context
    ↓
LLM Generation
    ↓
Extract Citations
    ↓
Grounded Answer with Sources
```

## Components

### 1. Document Models

**Document**
- Stores metadata about uploaded documents
- Tracks processing status (UPLOADED, PROCESSING, INDEXED, FAILED, DELETED)
- Enforces organization isolation
- Fields: id, organization_id, name, file_name, mime_type, file_size, storage_location, checksum, status, metadata, error_message

**DocumentChunk**
- Stores individual document chunks after splitting
- Preserves embedding vectors
- Maintains metadata for filtering
- Fields: id, organization_id, document_id, chunk_index, content, token_count, embedding, metadata

### 2. File Storage

**FileStorage (Abstract)**
- Interface for different storage backends
- Methods: save(), get(), delete(), exists()

**LocalFileStorage**
- Development implementation using local filesystem
- Organized by organization_id
- No cloud credentials required

Future implementations:
- Amazon S3
- Azure Blob Storage
- Google Cloud Storage

### 3. Document Parsers

Supports multiple file formats:

- **PDF** (PyPDF2): Extracts text with page markers
- **DOCX** (python-docx): Extracts paragraphs and tables
- **TXT**: Plain text extraction
- **Markdown**: Preserves structure
- **CSV**: Converts rows to searchable text
- **JSON**: Flattens structure for readability

**ParserRegistry** handles format detection and parser selection.

### 4. Chunking Service

- Configurable chunk size (default: 800 tokens)
- Configurable overlap (default: 120 tokens)
- Preserves document metadata with each chunk
- Estimates token counts for capacity planning

Configuration:
```python
ChunkConfig(
    chunk_size=800,
    chunk_overlap=120,
    separator="\n\n"
)
```

### 5. Embedding Provider

**EmbeddingProvider (Abstract)**
- Interface for different embedding backends
- Methods: embed_text(), embed_documents()

**OpenAIEmbeddingProvider**
- Uses text-embedding-3-small (1536 dimensions)
- Batch embedding support
- Automatic text cleaning and truncation

**MockEmbeddingProvider**
- For testing without API calls
- Deterministic embeddings based on text hash

Future implementations:
- Cohere
- Voyage
- Local embeddings
- Hugging Face

### 6. Vector Store

**VectorStore (Abstract)**
- Interface for different vector database backends
- Methods: upsert(), search(), delete(), delete_by_document()
- Enforces organization isolation

**PostgreSQLVectorStore**
- Uses PostgreSQL with pgvector extension
- Supports cosine similarity search
- Async connection pooling
- Proper indexing for performance

Future implementations:
- Milvus
- Qdrant
- Pinecone
- Weaviate

### 7. Retrieval Service

Coordinates:
1. Query embedding generation
2. Vector store search
3. Metadata filtering
4. Score normalization
5. Chunk enrichment with context

Returns: List of RetrievedChunk objects with similarity scores

### 8. Context Builder

Formats retrieved chunks for LLM consumption:
- Numbered sources with document names
- Page numbers when available
- Relevance scores
- Proper separation from system instructions

Prevents prompt injection by treating document content as data only.

### 9. RAG Tool

**search_business_knowledge**
- Registered with tool registry
- Requires READ permission (no approval needed)
- Automatically receives organization context
- Returns structured results with citations

Input:
```python
{
    "query": "What is the PTO policy?",
    "organization_id": "org123",
    "top_k": 5,
    "filters": {}
}
```

Output:
```python
{
    "results": [...],
    "citations": [...],
    "context": "...",
    "message": "Found X relevant documents"
}
```

### 10. Document Ingestion Service

**IngestionService**
- Orchestrates the complete ingestion pipeline
- Handles errors gracefully
- Updates document status
- Manages batch embedding
- Stores vectors with metadata

Workflow:
1. Retrieve document from storage
2. Parse based on MIME type
3. Normalize content
4. Split into chunks
5. Embed chunks in batch
6. Store chunks and vectors
7. Update status to INDEXED

### 11. Knowledge Management APIs

**POST /api/knowledge/documents**
- Upload document
- Validates file type and size
- Creates database record
- Queues for processing
- Returns document ID and status

**GET /api/knowledge/documents**
- List documents for organization
- Paginated response
- Shows status and file info
- Filters by organization

**GET /api/knowledge/documents/{id}**
- Get document details
- Shows processing status
- Displays chunk count
- Shows any errors

**DELETE /api/knowledge/documents/{id}**
- Soft delete from storage
- Removes chunks from database
- Removes vectors from store
- Ensures no orphaned data

**POST /api/knowledge/documents/{id}/reindex**
- Triggers reprocessing
- Useful if configuration changes
- Idempotent operation

## Configuration

Environment variables (see .env.example):

```bash
# Embeddings
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Chunking
CHUNK_SIZE=800
CHUNK_OVERLAP=120

# Search
RAG_TOP_K=5

# Upload limits
MAX_UPLOAD_SIZE_MB=25

# Storage
VECTOR_STORE=pgvector
LOCAL_STORAGE_PATH=./storage
```

## Database Migrations

Migration: `0002_add_rag_models.py`

Creates:
- `documents` table with appropriate indexes
- `document_chunks` table with FK to documents
- Supports both SQLite (development) and PostgreSQL (production)

Run migrations:
```bash
alembic upgrade head
```

## Security Considerations

### Organization Isolation
- All queries filtered by organization_id
- Documents never visible across organizations
- Vector search enforces tenant filtering

### Prompt Injection Protection
- Document content treated as data only
- Retrieved text escaped in prompts
- System instructions never overridable
- Content stored separately from instructions

### File Handling
- No code execution from uploaded files
- MIME type validation
- File size limits
- Virus scanning (future)

### Access Control
- Document operations require authentication
- User must be member of organization
- Deletion only by authorized users

## Testing

### Unit Tests

**test_document_parsing.py**
- Text, Markdown, CSV, JSON parsing
- Parser registry
- Chunking with metadata preservation
- Token estimation

**test_rag.py**
- Mock embedding provider
- Context builder
- Citation extraction
- RetrievedChunk serialization

### Integration Tests

Mock vector store integration to avoid API calls.

### Test Fixtures

Located in `tests/fixtures/documents/`:
- `employee-handbook.md` - Company HR policies
- `company-policies.txt` - Security, expense policies
- `products.csv` - Product information
- `benefits.json` - Benefits structure

These synthetic documents enable testing the complete pipeline.

## Performance

### Batch Operations
- Embeddings are batched (not one-per-chunk)
- Vector search uses proper indexing
- Document lists paginated

### Database Indexes
- organization_id for tenant isolation
- document_id for chunk lookups
- created_at for time-based queries
- embedding vectors with cosine_ops index

### Async I/O
- Document upload non-blocking
- Ingestion happens asynchronously
- Vector search concurrent-safe

## Limitations & Future Work

### Current Limitations
- Synchronous ingestion API (async job planned)
- SQLite vector search (limited to development)
- No hybrid search (semantic only)
- No long-term memory across conversations
- No multi-modal content

### Planned Enhancements
- Gmail integration for email search
- Google Drive document sync
- OneDrive/SharePoint support
- Slack channel indexing
- CRM system integration
- Hybrid keyword + semantic search
- Vector store alternatives (Qdrant, Milvus)
- Production deployment guides
- Observability and metrics

## Monitoring

### Logs
- Document parsing errors captured
- Ingestion latency tracked
- Vector search performance logged
- API response times monitored

### Metrics (Future)
- Documents indexed per day
- Average retrieval latency
- Embedding cache hit rate
- Vector store query times
- Citation accuracy

## Troubleshooting

### Document not appearing after upload
1. Check document status: `GET /api/knowledge/documents/{id}`
2. Review error_message field
3. Check file format support
4. Verify organization context

### Vector search returns no results
1. Verify documents are in INDEXED status
2. Check organization_id matches user's organization
3. Try broader search query
4. Check chunk metadata filters

### Embedding generation fails
1. Verify OPENAI_API_KEY is set
2. Check API rate limits
3. Ensure sufficient API quota
4. Review chunk content (may exceed limits)

## Example Usage

See Phase 3 end-to-end demo below.
