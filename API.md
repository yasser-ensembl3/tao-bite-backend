# 📡 API Documentation

Base URL: `http://localhost:8080`

---

## 📤 Upload & Processing

### 1. Upload PDF

**Endpoint:** `POST /upload`

**Content-Type:** `multipart/form-data`

**Body:**
```
file: [PDF File]
```

**Response:**
```json
{
  "success": true,
  "message": "File uploaded successfully",
  "job_id": "abc123-def456-...",
  "filename": "document.pdf"
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/upload \
  -F "file=@document.pdf"
```

---

### 2. Check Conversion Status

**Endpoint:** `GET /status/{job_id}`

**Response (Processing):**
```json
{
  "status": "processing",
  "message": "Converting PDF...",
  "job_id": "abc123-def456-..."
}
```

**Response (Completed):**
```json
{
  "status": "completed",
  "message": "Conversion complete",
  "job_id": "abc123-def456-...",
  "markdown_file": "outputs/abc123-def456-....md"
}
```

**cURL Example:**
```bash
curl http://localhost:8080/status/abc123-def456
```

---

### 3. Auto-Pipeline (Embeddings + Injection)

**Endpoint:** `POST /auto-pipeline/{job_id}`

**Content-Type:** `application/json`

**Body:**
```json
{
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "collection_name": "pdf_documents"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Pipeline completed successfully",
  "total_chunks": 145,
  "total_tokens": 98432,
  "collection_name": "pdf_documents"
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/auto-pipeline/abc123-def456 \
  -H "Content-Type: application/json" \
  -d '{
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "collection_name": "pdf_documents"
  }'
```

---

## 🤖 AI Content Generation

### Generate Content

**Endpoint:** `POST /generate-content`

**Content-Type:** `application/json`

**Body:**
```json
{
  "keywords": "entrepreneurship leadership",
  "instructions": "Extract the 5 best quotes about this topic with author names",
  "num_chunks": 10,
  "min_relevance": 0.3
}
```

**Parameters:**
- `keywords` (string, required): Keywords for semantic search
- `instructions` (string, required): Instructions for Claude AI
- `num_chunks` (int, optional): Number of relevant passages to use (default: 10)
- `min_relevance` (float, optional): Minimum relevance score 0-1 (default: 0.3)

**Response:**
```json
{
  "success": true,
  "content": "Generated content here...",
  "metadata": {
    "chunks_found": 10,
    "avg_relevance": 0.72,
    "max_relevance": 0.89,
    "processing_time": 2.34
  }
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "resilience",
    "instructions": "Summarize key concepts",
    "num_chunks": 10
  }'
```

---

## 📊 Database

### 1. Get Database Statistics

**Endpoint:** `GET /api/database/stats`

**Response:**
```json
{
  "collections": [
    {
      "name": "pdf_documents",
      "vectors_count": 2335,
      "vector_size": 1536
    }
  ],
  "total_vectors": 2335
}
```

**cURL Example:**
```bash
curl http://localhost:8080/api/database/stats
```

---

### 2. Get Documents (Paginated)

**Endpoint:** `GET /api/database/documents`

**Query Parameters:**
- `collection_name` (string, optional): Collection name (default: "pdf_documents")
- `limit` (int, optional): Number of chunks to return (default: 100)
- `offset` (int, optional): Offset for pagination (default: 0)

**Response:**
```json
{
  "collection_name": "pdf_documents",
  "documents": [
    {
      "filename": "Thinking Fast and Slow.pdf",
      "chunks": [...],
      "total_tokens": 265038,
      "total_chars": 987654,
      "chunk_count": 410,
      "job_id": "abc123",
      "source": "pdfplumber"
    }
  ],
  "total_documents": 16,
  "total_chunks": 100,
  "total_chunks_in_collection": 2335,
  "limit": 100,
  "offset": 0,
  "has_more": true
}
```

**cURL Example:**
```bash
curl "http://localhost:8080/api/database/documents?limit=50&offset=0"
```

---

### 3. List All Documents (Scalable)

**Endpoint:** `GET /api/database/documents/list`

**Query Parameters:**
- `collection_name` (string, optional): Collection name (default: "pdf_documents")
- `search` (string, optional): Filter by filename

**Response:**
```json
{
  "collection_name": "pdf_documents",
  "documents": [
    {
      "filename": "Thinking Fast and Slow.pdf",
      "chunk_count": 410,
      "total_tokens": 265038,
      "source": "pdfplumber",
      "job_id": "abc123"
    }
  ],
  "total_documents": 19,
  "total_chunks": 2335,
  "search_term": null
}
```

**cURL Example (with search):**
```bash
curl "http://localhost:8080/api/database/documents/list?search=resilience"
```

---

## 🔍 Search Example

**Full workflow example:**

```bash
# 1. Upload a PDF
JOB_ID=$(curl -X POST http://localhost:8080/upload \
  -F "file=@mybook.pdf" \
  | jq -r '.job_id')

# 2. Wait for conversion (poll every 2s)
while [ "$(curl -s http://localhost:8080/status/$JOB_ID | jq -r '.status')" != "completed" ]; do
  sleep 2
done

# 3. Process & inject into database
curl -X POST http://localhost:8080/auto-pipeline/$JOB_ID \
  -H "Content-Type: application/json" \
  -d '{"chunk_size": 1000, "chunk_overlap": 200, "collection_name": "pdf_documents"}'

# 4. Generate content
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "leadership decision-making",
    "instructions": "Extract key insights and create a summary",
    "num_chunks": 15
  }'
```

---

## 🌐 CORS

CORS est activé pour toutes les origines en développement. Pour la production, configurez dans `app.py` :

```python
CORS(app, resources={
    r"/*": {
        "origins": ["https://your-domain.com"],
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"]
    }
})
```

---

## ⚠️ Error Responses

Toutes les erreurs retournent un JSON avec le format :

```json
{
  "error": "Error message here"
}
```

**HTTP Status Codes:**
- `200` - Success
- `400` - Bad Request (missing parameters, invalid input)
- `404` - Not Found (job_id or collection not found)
- `500` - Internal Server Error

---

## 🔐 Rate Limiting

Actuellement, il n'y a pas de rate limiting. Pour la production, considérez :
- Flask-Limiter
- nginx rate limiting
- API Gateway
