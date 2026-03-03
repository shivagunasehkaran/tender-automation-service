# Tender Automation Service

FastAPI-based multi-agent service using LangGraph that generates structured tender responses from Excel input. References historical responses, maintains consistency, and adapts to each client's wording.

---

## 1. Repository & Deploy

### Prerequisites
- Python 3.10+
- OpenAI API key

### Setup
```bash
# Clone and enter
cd tender-automation-service

# Create venv and install
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: set OPENAI_API_KEY=your-key
```

### Run
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Verify
```bash
# Health
curl http://localhost:8000/api/v1/health

# Load historical data (required before processing)
curl -X POST http://localhost:8000/api/v1/historical/load

# Process sample Excel
curl -X POST -F "file=@data/sample_input.xlsx" "http://localhost:8000/api/v1/tender/process?format=json"
```

### Tests
```bash
pytest tests/ -v
```

---

## 2. Agent Definitions

| Agent | File | Model | Purpose |
|-------|------|-------|---------|
| **Classifier** | `app/agents/classifier.py` | gpt-4o-mini | Domain tagging (Security, Infrastructure, AI/ML, etc.) + keyword extraction |
| **Retrieval** | `app/agents/retrieval.py` | None | ChromaDB vector search with domain filter |
| **Generator** | `app/agents/generator.py` | gpt-4o | Generates answer (with or without history) |
| **Reviewer** | `app/agents/reviewer.py` | gpt-4o-mini | Confidence score, consistency check, flags |

**Workflow:** classify → retrieve → [branch: with_history / without_history] → generate → review → loop or summarize

---

## 3. Sample Data & Output

| Item | Location |
|------|----------|
| **Historical data** | `data/historical/*.json` (6 files, 38 Q&A pairs) |
| **Sample input Excel** | `data/sample_input.xlsx` (15 questions) |
| **Example output** | JSON or Excel via API (see payloads below) |

---

## 4. API Details — Postman / cURL

### Base URL
```
http://localhost:8000
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/historical/load` | Load historical data |
| GET | `/api/v1/historical/stats` | Vector store stats |
| POST | `/api/v1/tender/process` | Process Excel file |

---

### Sample Payloads

#### 1. Health Check
```bash
curl http://localhost:8000/api/v1/health
```
**Response:**
```json
{"status":"ok","version":"1.0.0","vector_store_ready":true}
```

---

#### 2. Load Historical Data
```bash
curl -X POST http://localhost:8000/api/v1/historical/load
```
**Response:**
```json
{"loaded":38,"message":"Loaded 38 historical responses"}
```

---

#### 3. Process Excel (multipart)
```bash
# JSON response (default)
curl -X POST "http://localhost:8000/api/v1/tender/process?format=json" \
  -F "file=@data/sample_input.xlsx"

# Excel file (save with -o)
curl -X POST "http://localhost:8000/api/v1/tender/process?format=excel" \
  -F "file=@data/sample_input.xlsx" \
  -o tender_response.xlsx
```

**Query params:** `format` = `json` (default) or `excel`

---

#### 4. Example Response (JSON)
```json
{
  "session_id": "uuid-here",
  "results": [
    {
      "question_number": 1,
      "original_question": "Does the platform enforce TLS 1.2 or higher?",
      "generated_answer": "Yes. Our platform enforces TLS 1.2 or higher...",
      "domain": "Security",
      "confidence": 0.9,
      "historical_match": true,
      "reviewer_flags": [],
      "status": "success",
      "error": null
    }
  ],
  "summary": {
    "total_questions": 1,
    "successful": 1,
    "failed": 0,
    "flagged_inconsistencies": 0,
    "overall_status": "completed"
  }
}
```

---

### Swagger UI
```
http://localhost:8000/docs
```

---

## 5. Current Scope & Future Production Considerations

This is an assessment MVP. The following capabilities are not implemented but would be addressed when expanding to a production system:

| Area | Current State |
|------|---------------|
| **Chunking strategy** | No. Historical Q&A pairs are stored as whole documents (one question per document). No sentence splitting, recursive splitting, or other chunking. |
| **Validation / guardrails** | Limited. Prompts say "never fabricate" and "maintain consistency." The reviewer flags issues. There is a `similarity_threshold` (0.7) to filter weak matches. No programmatic guardrails (PII, prompt injection, output validation). |
| **Security standards** | No. No auth, rate limiting, or input sanitization. File upload only checks `.xlsx`/`.xls`. No explicit security controls. |
| **RAG output evaluation** | No. No metrics, ground-truth comparison, or automated evaluation of retrieval or generation quality. |
| **Latency, cost, metrics** | No. No latency tracking, token counting, cost calculation, or metrics. |
| **Recall@5 or MRR** | No. No retrieval metrics (Recall@5, MRR, etc.). |
| **Reranking** | No. Single-stage retrieval: ChromaDB `top_k` + `similarity_threshold`. No second-stage reranker. |
