# Tender Automation Service

FastAPI-based multi-agent service using LangGraph that generates structured tender responses from Excel or JSON input. References historical responses, maintains consistency, and adapts to each client's wording.

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
| POST | `/api/v1/tender/process/json` | Process JSON body |

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
curl -X POST "http://localhost:8000/api/v1/tender/process?format=json" \
  -F "file=@data/sample_input.xlsx"
```

**Query params:** `format` = `json` (default) or `excel`

---

#### 4. Process JSON
```bash
curl -X POST "http://localhost:8000/api/v1/tender/process/json?format=json" \
  -H "Content-Type: application/json" \
  -d '{
    "questions": [
      {"question_number": 1, "original_question": "Does the platform enforce TLS 1.2 or higher?"},
      {"question_number": 2, "original_question": "Do you support SSL and TLS?"}
    ]
  }'
```

**Request body:**
```json
{
  "questions": [
    {"question_number": 1, "original_question": "Your question here?"}
  ]
}
```

---

#### 5. Example Response (JSON)
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
