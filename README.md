# Polara Evidence Quality Checker

An ML-powered microservice that evaluates whether an uploaded document is sufficient evidence for a given SOC 2 control. It returns a score (0–1), a verdict (`sufficient`, `insufficient`, or `uncertain`), a plain-language explanation, and a list of missing elements.

It is **advisory only** — it flags issues but never blocks an upload.

---

## Quick Start (Docker)

```bash
# 1. Clone the repo
git clone <repo-url> && cd polara-evidence-checker

# 2. Create your .env file (see .env.example for reference)
cp .env.example .env
# Fill in: HF_TOKEN, CHECKER_API_KEY, OPENAI_API_KEY

# 3. Build and start (first build takes ~5 min to download the embedding model)
docker-compose build
docker-compose up -d

# 4. Verify it's running
curl http://localhost:8000/health
# → {"status":"ok"}
```

---

## Calling the API

**Endpoint:** `POST /api/v1/check`

**Auth:** Pass your `CHECKER_API_KEY` in the `X-API-Key` header.

**Request:** Multipart form with two fields:
- `file` — the evidence document (PDF, DOCX, TXT, or MD)
- `control_id` — the SOC 2 control ID (e.g. `CC6.1`)

**Example (curl):**
```bash
curl -X POST http://localhost:8000/api/v1/check \
  -H "X-API-Key: your-checker-api-key" \
  -F "file=@path/to/document.pdf" \
  -F "control_id=CC6.1"
```

**Example (PowerShell):**
```powershell
curl.exe -X POST http://localhost:8000/api/v1/check `
  -H "X-API-Key: your-checker-api-key" `
  -F "file=@path\to\document.pdf" `
  -F "control_id=CC6.1"
```

**Response:**
```json
{
  "score": 0.82,
  "verdict": "sufficient",
  "explanation": "Document covers RBAC definitions, least privilege, access reviews, and provisioning/revocation procedures with named tools and review dates.",
  "missing_elements": [],
  "control_id": "CC6.1",
  "checked_at": "2026-03-10T14:30:00Z"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `score` | float (0–1) | Composite quality score |
| `verdict` | string | `sufficient`, `insufficient`, or `uncertain` |
| `explanation` | string | Human-readable summary of what was found/missing |
| `missing_elements` | string[] | Subcriteria the document doesn't cover |
| `control_id` | string | The control that was checked against |
| `checked_at` | string | ISO 8601 timestamp |

### Supported Controls

CC6.1, CC6.2, CC6.3, CC6.6, CC6.7, CC6.8, CC7.2, CC7.3, CC8.1, CC1.1, CC1.2, CC1.3, CC1.4, CC1.5, CC2.1, CC2.2, CC2.3, CC3.1, CC3.2, CC3.3, CC3.4, CC4.1, CC4.2, CC5.1, CC5.2, CC5.3, CC6.4, CC6.5, CC7.1, CC7.4, CC7.5, CC9.1, CC9.2

---

## How It Works

The system is a four-stage pipeline:

1. **Extraction** — Converts PDF, DOCX, TXT, or MD into clean plaintext (PyMuPDF, python-docx).
2. **Deterministic Scoring** — Computes a weighted composite score from four signals:
   - *Semantic similarity* (40%) — chunk-level cosine similarity against per-control subcriteria using `google/embeddinggemma-300m`
   - *Concept coverage* (25%) — keyword and phrase matching against expected vocabulary
   - *Specificity* (20%) — detects concrete evidence (named tools, dates, config details) vs. vague language
   - *Mismatch penalty* (15%, subtractive) — catches wrong-type documents (e.g. encryption-at-rest for an encryption-in-transit control)
3. **Verdict Gate** — Compares the score against per-control threshold bands. Clear pass/fail cases get an immediate verdict; borderline cases go to step 4.
4. **LLM Adjudication** — For ambiguous cases only, sends pre-digested signals (not the full document) to GPT-4o-mini to decide enforcement vs. intention.

~80% of documents are resolved by the deterministic path alone (under 3 seconds). The LLM is invoked for ~20% of cases and adds ~2 seconds.

---

## Running Locally (Without Docker)

```bash
# Requires Python 3.11+
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
pip install -e .

# Authenticate with Hugging Face (one-time — embeddinggemma is gated)
huggingface-cli login

# Set environment variables (or create a .env file)
# CHECKER_API_KEY=your-key
# OPENAI_API_KEY=sk-...

# Start the server
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## Running the Evaluation

```bash
python scripts/test_document.py
```

This runs all 88 synthetic test documents (44 sufficient, 44 insufficient) against the scorer and reports pass/fail, LLM adjudication usage, and latency per file.

**Current results: 88/88 passing (100% accuracy on synthetic test set).**

21 of 88 cases required LLM adjudication — these are borderline documents where the deterministic score fell within the uncertain band. All 21 were adjudicated correctly.

---

## Project Structure

```
polara-evidence-checker/
├── api/                        # FastAPI service
│   ├── main.py                 # App entry point, lifespan, /health, /api/v1/check
│   └── dependencies.py         # X-API-Key header validation
├── polara_checker/             # Core Python package
│   ├── extraction.py           # PDF/DOCX/TXT/MD → clean text
│   ├── chunking.py             # Split text into overlapping chunks
│   ├── embeddings.py           # EmbeddingGemma model loading + similarity
│   ├── keywords.py             # Keyword/concept matching
│   ├── mismatch.py             # Wrong-control detection
│   ├── specificity.py          # Vague vs. concrete evidence scoring
│   ├── scorer.py               # Combines all signals into final score
│   ├── verdicts.py             # Per-control thresholds → verdict
│   ├── llm_adjudicator.py      # GPT-4o-mini call for uncertain cases
│   └── schemas.py              # Pydantic models
├── controls/                   # One JSON per SOC 2 control (33 total)
├── test_documents/             # Synthetic test evidence (88 files)
│   ├── sufficient/
│   └── insufficient/
├── scripts/
│   ├── build_references.py     # One-time: embeds subcriteria → control JSONs
│   └── test_document.py        # Evaluation runner
├── integration/                # Reference Netlify Function (TypeScript)
│   └── check-evidence-quality.ts
├── migrations/                 # Supabase SQL
│   └── 001_create_evidence_quality_scores.sql
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── requirements.txt
└── pyproject.toml
```

---

## Supabase Integration

### Database Migration

Run `migrations/001_create_evidence_quality_scores.sql` against your Supabase project. It creates the `evidence_quality_scores` table with Row Level Security scoped to the organization that owns the evidence.

**Before running**, update these placeholders in the SQL:
- `evidence_uploads` → the actual table name for uploaded evidence files
- `eu.org_id` → the actual column that links evidence to an organization
- `auth.jwt() ->> 'org_id'` → the actual JWT claim path for the user's org

### Netlify Function

`integration/check-evidence-quality.ts` is a reference implementation showing the round-trip:

1. Frontend calls the function with `evidence_id`, `control_id`, and `storage_path`
2. Function downloads the file from Supabase Storage
3. POSTs it to the checker API
4. Writes the result to `evidence_quality_scores`
5. Returns the verdict to the frontend

This is not production code — it's a starting point for wiring into the actual upload flow. The function expects these environment variables in Netlify:

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (server-side only) |
| `CHECKER_URL` | URL where the checker is deployed (e.g. `https://checker.polara.app`) |
| `CHECKER_API_KEY` | Same key the checker validates against |

---

## Environment Variables

| Variable | Used By | Required |
|----------|---------|----------|
| `HF_TOKEN` | Docker build only | Yes (at build time) |
| `CHECKER_API_KEY` | FastAPI service | Yes |
| `OPENAI_API_KEY` | LLM adjudicator | Yes |

---

## Deployment Notes

- **Workers:** The Dockerfile runs uvicorn with `--workers 1`. Each worker loads the embedding model (~1.2 GB in memory). Scale horizontally (more containers) rather than vertically (more workers).
- **Memory:** The container needs ~2.5 GB minimum. The `docker-compose.yml` sets a 4 GB limit.
- **Cold start:** The embedding model is downloaded at Docker build time, not at runtime. Container startup (model load + control file parsing) takes ~5 seconds.
- **Gated model:** `google/embeddinggemma-300m` requires accepting the license at https://huggingface.co/google/embeddinggemma-300m and a Hugging Face token.

---

## Adding New Controls

1. Add a new JSON file to `controls/` (e.g. `CC9.9.json`) following the existing schema: `control_id`, `description`, `subcriteria` with reference text, `expected_keywords`, `mismatch_signals`, and `thresholds`.
2. Run `python scripts/build_references.py` to compute and embed the subcriteria vectors.
3. Restart the service — the new control is picked up automatically at startup.

No code changes required.