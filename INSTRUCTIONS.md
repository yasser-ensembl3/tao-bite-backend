# 📖 Complete Instructions - Tao Bite Backend

Complete guide to install, launch, and use the backend API.

---

## 🚀 Installation and Launch

### Prerequisites
- Python 3.9+
- pip3
- git

### Step 1: Clone the repository

```bash
git clone https://github.com/yasser-ensembl3/tao-bite-backend.git
cd tao-bite-backend
```

### Step 2: Create a virtual environment (recommended)

```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python3 -m venv venv
venv\Scripts\activate
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure API keys

Create a `.env` file at the project root:

```bash
cp .env.example .env
```

Edit the `.env` file with your API keys:

```env
# API Keys Configuration
LLAMA_CLOUD_API_KEY=your_llama_cloud_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Qdrant Cloud Configuration (optional, otherwise uses local storage)
QDRANT_URL=your_qdrant_cloud_url_here
QDRANT_API_KEY=your_qdrant_api_key_here
```

### Step 5: Launch the server

```bash
python3 app.py
```

The server starts on **http://localhost:8080**

---

## 📚 API Usage

### Complete Workflow

#### 1️⃣ Upload a PDF

**Command:**
```bash
curl -X POST http://localhost:8080/upload \
  -F "file=@path/to/your-document.pdf"
```

**Example with a test file:**
```bash
curl -X POST http://localhost:8080/upload \
  -F "file=@test.pdf"
```

**Expected response:**
```json
{
  "success": true,
  "message": "File uploaded successfully",
  "job_id": "abc123-def456-789ghi",
  "filename": "test.pdf"
}
```

**💡 Important:** Note the `job_id` - you'll need it for the following steps!

---

#### 2️⃣ Check conversion status

**Command:**
```bash
curl http://localhost:8080/status/YOUR_JOB_ID
```

**Example:**
```bash
curl http://localhost:8080/status/abc123-def456-789ghi
```

**Response (in progress):**
```json
{
  "status": "processing",
  "message": "Converting PDF...",
  "job_id": "abc123-def456-789ghi"
}
```

**Response (completed):**
```json
{
  "status": "completed",
  "message": "Conversion complete",
  "job_id": "abc123-def456-789ghi",
  "markdown_file": "outputs/abc123-def456-789ghi.md"
}
```

**💡 Tip:** Wait until the status is "completed" before moving to the next step.

---

#### 3️⃣ Download the markdown (optional)

**Command:**
```bash
curl http://localhost:8080/download/YOUR_JOB_ID -o document.md
```

**Example:**
```bash
curl http://localhost:8080/download/abc123-def456-789ghi -o my-document.md
```

---

#### 4️⃣ Chunking + Embeddings + Injection into vector database

This command does everything automatically:
- Splits text into chunks
- Generates embeddings with OpenAI
- Injects into Qdrant

**Command:**
```bash
curl -X POST http://localhost:8080/auto-pipeline/YOUR_JOB_ID \
  -H "Content-Type: application/json" \
  -d '{
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "collection_name": "pdf_documents"
  }'
```

**Example:**
```bash
curl -X POST http://localhost:8080/auto-pipeline/abc123-def456-789ghi \
  -H "Content-Type: application/json" \
  -d '{
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "collection_name": "pdf_documents"
  }'
```

**Parameters:**
- `chunk_size`: Size of each chunk in tokens (recommended: 1000)
- `chunk_overlap`: Overlap between chunks (recommended: 200)
- `collection_name`: Qdrant collection name (default: "pdf_documents")

**Expected response:**
```json
{
  "success": true,
  "message": "Pipeline completed successfully",
  "total_chunks": 145,
  "total_tokens": 98432,
  "collection_name": "pdf_documents"
}
```

---

#### 5️⃣ Generate content with Claude AI

Semantically search through your documents and generate content with Claude.

**Command:**
```bash
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "your keywords",
    "instructions": "what you want to generate",
    "num_chunks": 10,
    "min_relevance": 0.3
  }'
```

**Practical Examples:**

**Example 1: Extract quotes**
```bash
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "entrepreneurship leadership",
    "instructions": "Extract the 5 best quotes with author names",
    "num_chunks": 10
  }'
```

**Example 2: Summarize concepts**
```bash
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "innovation startup",
    "instructions": "Summarize key concepts in 5 main points",
    "num_chunks": 15
  }'
```

**Example 3: Create an article**
```bash
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "decision making psychology",
    "instructions": "Create a 500-word blog post on this topic",
    "num_chunks": 20
  }'
```

**Parameters:**
- `keywords` (required): Keywords for semantic search
- `instructions` (required): Instructions for Claude AI
- `num_chunks` (optional): Number of relevant passages to use (default: 10)
- `min_relevance` (optional): Minimum relevance score 0-1 (default: 0.3)

**Response:**
```json
{
  "success": true,
  "content": "Content generated by Claude...",
  "metadata": {
    "chunks_found": 10,
    "avg_relevance": 0.72,
    "max_relevance": 0.89,
    "processing_time": 2.34
  }
}
```

---

## 📊 Query the Database

### View database statistics

```bash
curl http://localhost:8080/api/database/stats
```

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

---

### List all documents

```bash
curl http://localhost:8080/api/database/documents/list
```

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
    },
    {
      "filename": "Zero to One.pdf",
      "chunk_count": 285,
      "total_tokens": 189432,
      "source": "llamaparse",
      "job_id": "def456"
    }
  ],
  "total_documents": 2,
  "total_chunks": 695
}
```

---

### Search for a specific document

```bash
curl "http://localhost:8080/api/database/documents/list?search=thinking"
```

---

### View documents with pagination

```bash
curl "http://localhost:8080/api/database/documents?limit=50&offset=0"
```

---

## 🔍 Semantic search in Qdrant

```bash
curl -X POST http://localhost:8080/qdrant/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "your search",
    "collection_name": "pdf_documents",
    "limit": 10
  }'
```

---

## 🤖 Complete Automated Script

Create a `test-pipeline.sh` file:

```bash
#!/bin/bash

# Configuration
PDF_FILE="my-document.pdf"
COLLECTION="pdf_documents"

echo "=========================================="
echo "🚀 COMPLETE TAO BITE BACKEND PIPELINE"
echo "=========================================="

# 1. Upload
echo ""
echo "📤 Step 1/5: Uploading PDF..."
RESPONSE=$(curl -s -X POST http://localhost:8080/upload -F "file=@$PDF_FILE")
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')

if [ "$JOB_ID" == "null" ]; then
  echo "❌ Upload error"
  echo $RESPONSE | jq '.'
  exit 1
fi

echo "✅ Upload successful - Job ID: $JOB_ID"

# 2. Wait for conversion
echo ""
echo "⏳ Step 2/5: Conversion in progress..."
while true; do
  STATUS=$(curl -s http://localhost:8080/status/$JOB_ID | jq -r '.status')

  if [ "$STATUS" == "completed" ]; then
    echo "✅ Conversion complete!"
    break
  elif [ "$STATUS" == "error" ]; then
    echo "❌ Conversion error"
    exit 1
  fi

  echo "   Status: $STATUS - waiting..."
  sleep 2
done

# 3. Processing + Injection
echo ""
echo "🔄 Step 3/5: Chunking and injecting into Qdrant..."
PIPELINE_RESPONSE=$(curl -s -X POST http://localhost:8080/auto-pipeline/$JOB_ID \
  -H "Content-Type: application/json" \
  -d "{
    \"chunk_size\": 1000,
    \"chunk_overlap\": 200,
    \"collection_name\": \"$COLLECTION\"
  }")

TOTAL_CHUNKS=$(echo $PIPELINE_RESPONSE | jq -r '.total_chunks')
echo "✅ Pipeline complete - $TOTAL_CHUNKS chunks created"

# 4. Stats
echo ""
echo "📊 Step 4/5: Database statistics..."
curl -s http://localhost:8080/api/database/stats | jq '.'

# 5. Content generation
echo ""
echo "🤖 Step 5/5: AI content generation..."
CONTENT=$(curl -s -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "innovation startup entrepreneurship",
    "instructions": "Summarize key concepts in 3 main points",
    "num_chunks": 10
  }')

echo ""
echo "=========================================="
echo "✅ GENERATED CONTENT:"
echo "=========================================="
echo $CONTENT | jq -r '.content'
echo ""
echo "=========================================="
echo "📈 Metadata:"
echo "=========================================="
echo $CONTENT | jq '.metadata'

echo ""
echo "✅ Complete pipeline finished successfully!"
```

**Usage:**
```bash
chmod +x test-pipeline.sh
./test-pipeline.sh
```

**Note:** This script requires `jq` for JSON parsing.
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq
```

---

## 🛠️ Useful Commands

### Stop the server
```bash
# In the terminal where the server is running
Ctrl+C
```

### Restart the server
```bash
python3 app.py
```

### Check if the server is working
```bash
curl http://localhost:8080/api/database/stats
```

### Clean uploads and outputs
```bash
rm -rf uploads/* outputs/*
```

### View logs in real-time
Logs are displayed directly in the terminal with emojis:
- 🔍 = Search/Query
- ✓ = Success
- ❌ = Error
- 📚 = Database
- 🎯 = Configuration

---

## 🐛 Troubleshooting

### Server won't start

**Error: Port 8080 already in use**
```bash
# Find the process
lsof -ti:8080

# Kill the process
kill -9 $(lsof -ti:8080)
```

**Error: Module not found**
```bash
pip install -r requirements.txt
```

---

### API keys not working

1. Check that the `.env` file exists
2. Verify keys are correct (no spaces)
3. Restart the server after modifying `.env`

---

### Conversion fails

The system has 2 fallback methods:
1. **pdfplumber** (fast, for simple PDFs)
2. **LlamaParse** (backup, for complex PDFs)

If both fail, check:
- The PDF is not corrupted
- The PDF is not password protected
- Your `LLAMA_CLOUD_API_KEY` is valid

---

### Qdrant not working

**Option 1: Use local Qdrant**
- Don't define `QDRANT_URL` and `QDRANT_API_KEY` in `.env`
- Data will be stored in `./qdrant_storage/`

**Option 2: Use Qdrant Cloud**
- Verify `QDRANT_URL` and `QDRANT_API_KEY` are correct
- URL format: `https://xxx.cloud.qdrant.io`

---

## 📖 Resources

- **Complete API**: See `API.md`
- **Quick Guide**: See `QUICKSTART.md`
- **README**: See `README.md`
- **GitHub**: https://github.com/yasser-ensembl3/tao-bite-backend

---

## 💡 Usage Examples

### Use Case 1: Book Library

Upload multiple books and ask cross-document questions:

```bash
# Upload book 1
curl -X POST http://localhost:8080/upload -F "file=@book1.pdf"
# Wait for conversion + auto-pipeline

# Upload book 2
curl -X POST http://localhost:8080/upload -F "file=@book2.pdf"
# Wait for conversion + auto-pipeline

# Cross-document search
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "leadership resilience",
    "instructions": "Compare different authors perspectives on this topic",
    "num_chunks": 20
  }'
```

---

### Use Case 2: Quote Extraction

```bash
curl -X POST http://localhost:8080/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "failure success pivot",
    "instructions": "Extract 10 inspiring quotes about failure and pivoting, with author name and context",
    "num_chunks": 15
  }'
```

---

### Use Case 3: Substack Content Generation

```bash
curl -X POST http://localhost:8080/generate-draft \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "The Art of Decision Making",
    "num_chunks": 20,
    "style": "conversational"
  }'
```

---

## 🔐 Security (Production)

If deploying to production:

1. **Disable debug mode** in `app.py`
   ```python
   app.run(host='0.0.0.0', port=8080, debug=False)
   ```

2. **Use a WSGI server** (Gunicorn or Waitress)
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8080 app:app
   ```

3. **Configure CORS** for your domain only

4. **Use HTTPS** (nginx + Let's Encrypt)

5. **Add authentication** (JWT, API keys, etc.)

6. **Rate limiting** (Flask-Limiter or nginx)

---

## ✅ Pre-launch Checklist

- [ ] Python 3.9+ installed
- [ ] pip installed
- [ ] Repository cloned
- [ ] Dependencies installed
- [ ] `.env` file created with API keys
- [ ] Server launched and accessible at http://localhost:8080
- [ ] Basic test successful (`curl http://localhost:8080/api/database/stats`)

---

**You're ready to use Tao Bite Backend! 🚀**
