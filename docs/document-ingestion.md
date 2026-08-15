# Document Ingestion Guide

## Overview

The document ingestion system allows organizations to upload business documents, which are automatically processed and indexed for semantic search.

## Supported Formats

| Format | Extension | MIME Type | Parser |
|--------|-----------|-----------|--------|
| PDF | .pdf | application/pdf | PyPDF2 |
| Word | .docx | application/vnd.openxmlformats-officedocument.wordprocessingml.document | python-docx |
| Plain Text | .txt | text/plain | Built-in |
| Markdown | .md | text/markdown | Built-in |
| CSV | .csv | text/csv | Built-in |
| JSON | .json | application/json | Built-in |

## Upload Process

### Step 1: Upload Document

```bash
curl -X POST http://localhost:8000/api/knowledge/documents \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@employee-handbook.pdf"
```

Response:
```json
{
  "id": "doc-uuid-here",
  "name": "employee-handbook.pdf",
  "status": "uploaded",
  "message": "Document uploaded and queued for processing"
}
```

### Step 2: Check Processing Status

```bash
curl http://localhost:8000/api/knowledge/documents/doc-uuid-here \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "id": "doc-uuid-here",
  "name": "employee-handbook.pdf",
  "status": "indexed",
  "file_size": 245120,
  "chunk_count": 12,
  "created_at": "2024-08-12T10:30:00Z"
}
```

Status flow:
- `uploaded` → `processing` → `indexed` (success)
- `uploaded` → `processing` → `failed` (error)

### Step 3: Search Document Content

Once indexed, search the organization's knowledge:

```bash
curl "http://localhost:8000/api/knowledge/search?q=PTO%20policy" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Processing Pipeline

### 1. File Validation

- MIME type must be supported
- File size must be under 25 MB
- File extension must match MIME type (basic check)

### 2. Storage

Files are stored in:
```
./storage/{organization_id}/{document_id}
```

Organization isolation prevents cross-tenant access.

### 3. Parsing

Document parser selected based on MIME type:

```python
if mime_type == "application/pdf":
    extract text with PyPDF2
    add page numbers to extracted text

elif mime_type == "application/vnd.openxmlformats...":
    extract paragraphs with python-docx
    extract tables as formatted text

elif mime_type in ["text/plain", "text/markdown"]:
    read raw content

elif mime_type == "text/csv":
    convert rows to "key: value" format

elif mime_type == "application/json":
    pretty-print JSON structure
```

### 4. Normalization

- Normalize whitespace (remove extra spaces)
- Remove control characters
- Preserve meaningful structure (headings, tables)
- Preserve page information

### 5. Chunking

Document split into overlapping chunks:
- Default chunk size: 800 tokens (~3000 characters)
- Overlap: 120 tokens (provides context continuity)
- Metadata preserved: document ID, name, page number, section

Example chunk:
```
[Page 17]
Paid Time Off (PTO) Policy

All full-time employees receive 20 days of 
paid time off per year. PTO accrues monthly 
at 1.67 days per month...
```

### 6. Embedding

Each chunk embedded using OpenAI text-embedding-3-small:
- Vector dimension: 1536
- Batched for efficiency
- Stored in database as binary
- Also stored in pgvector for similarity search

### 7. Vector Storage

Embeddings stored in PostgreSQL:
- Organization isolation enforced
- Similarity index created for fast search
- Chunk metadata stored as JSON

### 8. Status Update

Document status changed from `processing` to `indexed` (or `failed` if error).

## Error Handling

### Common Errors

**Unsupported File Type**
```json
{
  "detail": "Unsupported file type: application/vnd.ms-excel"
}
```
Solution: Use supported format (.xlsx files not yet supported)

**File Too Large**
```json
{
  "detail": "File size exceeds 25 MB limit"
}
```
Solution: Split large PDF or request size increase

**Parse Error**
If document appears with status `failed`:
```bash
curl http://localhost:8000/api/knowledge/documents/doc-id \
  -H "Authorization: Bearer TOKEN"
```

Shows error_message field with details.

Solution: Ensure document is valid (not corrupted, proper encoding)

## Reindexing

If chunk configuration changes, reindex documents:

```bash
curl -X POST http://localhost:8000/api/knowledge/documents/{id}/reindex \
  -H "Authorization: Bearer YOUR_TOKEN"
```

This:
1. Removes old chunks and vectors
2. Re-parses document
3. Re-chunks with new configuration
4. Re-embeds with new settings
5. Stores new vectors

Operation is idempotent - safe to call multiple times.

## Deletion

Delete document and all associated data:

```bash
curl -X DELETE http://localhost:8000/api/knowledge/documents/{id} \
  -H "Authorization: Bearer YOUR_TOKEN"
```

This:
1. Deletes file from storage
2. Deletes document record from database
3. Deletes all chunks (cascaded)
4. Deletes all vectors from vector store
5. Returns status 200 on success

## Bulk Operations

### List All Documents

```bash
curl "http://localhost:8000/api/knowledge/documents?skip=0&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "documents": [
    {
      "id": "doc-1",
      "name": "Employee Handbook.pdf",
      "status": "indexed",
      "file_size": 245120,
      "created_at": "2024-08-12T10:30:00Z"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 10
}
```

### Filter by Organization

Documents automatically filtered by user's organization membership.

## Best Practices

1. **Organize Documents**
   - Use clear, descriptive file names
   - Keep related documents together
   - Version documents appropriately

2. **Document Format**
   - Use PDFs for public-facing docs (reports, handbooks)
   - Use Markdown for editable content
   - Use CSV for tabular data
   - Use JSON for structured data

3. **Update Documents**
   - Delete old version
   - Upload new version with updated date
   - Use POST /reindex if content changed significantly

4. **Monitor Ingestion**
   - Check document status after upload
   - Review chunk count (should match content)
   - Test searches to verify indexing

5. **Optimize Performance**
   - Split very large documents (>100 MB) before upload
   - Prefer structured formats (CSV, JSON) for data
   - Use meaningful document names for clarity

## Troubleshooting

### Document stuck in "processing"

Check system logs:
```bash
docker logs agentmason-api
```

If stuck for >5 minutes, try reindexing after checking worker status.

### Chunks not appearing in search

1. Verify document status is `indexed`:
   ```bash
   curl http://localhost:8000/api/knowledge/documents/{id} \
     -H "Authorization: Bearer TOKEN"
   ```

2. Try broader search query
3. Check OpenAI API key is configured
4. Verify database has pgvector extension

### Parsing fails for specific file

Try converting:
- PDF → Export to text first
- DOCX → Save as .txt
- Corrupted file → Verify file integrity

## Advanced Configuration

### Change Chunk Size

Update in `.env`:
```bash
CHUNK_SIZE=1000  # Larger chunks
CHUNK_OVERLAP=150
```

Then reindex existing documents.

### Change Embedding Model

Update in `.env`:
```bash
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```

Must reindex after changing (produces different vectors).

### Local Storage Path

Update in `.env`:
```bash
LOCAL_STORAGE_PATH=/data/documents
```

Ensure directory is writable and has enough space.

## API Reference

See `/api/knowledge` endpoints in Swagger UI:
```
http://localhost:8000/docs
```

All endpoints require authentication and organization context.
