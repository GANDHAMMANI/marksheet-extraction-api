# Marksheet Extraction API

FastAPI service that reads academic marksheets and returns structured JSON with per-field confidence scores. Two vision LLMs run in parallel, cross-validate each other, and Tesseract pins fields to their location on the page (locally — disabled in production, see below).

**Live:** https://marksheet-extraction-api-1-5h3g.onrender.com  
**Swagger:** https://marksheet-extraction-api-1-5h3g.onrender.com/docs  
**Approach note:** `approach_note.md`

A working auth token is provided with this submission. To generate your own locally, see Setup below.

---

## Stack
- FastAPI + Pydantic v2
- Llama 4 Scout (Groq) + MiniMax-M3 (NVIDIA NIM) — dual vision LLMs, concurrent
- Tesseract OCR — bounding box location only, not text extraction
- PyMuPDF + Pillow + OpenCV — file normalization and deskew
- JWT auth, async parallel model calls, 16 passing unit tests

---

## Why two models

Llama 4 Scout alone occasionally transposes adjacent subject rows on photographed marksheets — confidently, with no self-doubt. Running MiniMax-M3 independently on the same document and comparing outputs converts that into an explicit low-confidence warning instead of a silent wrong answer. Confirmed this catches real errors on multiple test documents, including ones I sourced myself beyond the provided samples (see approach note).

NVIDIA's endpoint is a trial service, not production infrastructure — response times vary from seconds to minutes. The MiniMax call has a 45-second timeout; if it doesn't respond in time, the system falls back to a Scout-only result with an explicit warning rather than hanging the request.

---

## Confidence scoring

Three layers: model self-report (anchored to a concrete 0–1 scale in the prompt), cross-model agreement (agreement boosts confidence, disagreement halves it and logs a warning naming the field), and rule-based checks (missing required fields zeroed, marks-sum mismatches flagged as informational, not punitive). Full reasoning and test evidence in `approach_note.md`.

---

## Bounding boxes — why they're off in production

Tesseract locates extracted values on the page after the LLMs finish, using fuzzy word matching. Works correctly when testing locally. On Render's free tier (512MB RAM), the OCR preprocessing (image upscaling + thresholding) combined with two concurrent LLM calls occasionally exceeded available memory and crashed the process.

Rather than risk reliability for a bonus feature, it's toggled off in production via an env var:
```
ENABLE_BBOX_LOCATOR=false   # production (Render)
ENABLE_BBOX_LOCATOR=true    # local — default if unset
```
Run locally to see it working.

---

## Local Setup

Needs Python 3.11+, Tesseract installed, Groq + NVIDIA NIM API keys.

```bash
git clone https://github.com/GANDHAMMANI/marksheet-extraction-api.git
cd marksheet-extraction-api
python -m venv venv && venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Fill in `.env`:
```
GROQ_API_KEY=your-groq-key
NVIDIA_API_KEY=your-nvidia-key
JWT_SECRET_KEY=any-long-random-string
AUTH_USERNAME=admin
AUTH_PASSWORD=choose-your-own-password
```

```bash
uvicorn app.main:app --reload
```

Demo UI at `localhost:8000`, Swagger at `localhost:8000/docs`. Get a token via `/token` using the username/password you set in `.env`.

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /token | No | Get JWT token |
| POST | /extract | Bearer | Single marksheet |
| POST | /extract/batch | Bearer | Multiple files, one request |
| GET | /health | No | Uptime check |

Note: `/extract/batch` doesn't render a file picker in Swagger UI due to a known OpenAPI 3.1 / Swagger rendering gap for array-of-binary fields — the endpoint itself works correctly (tested via curl and the demo UI). A schema patch in `main.py` partially works around this.

---

## Known limitations

- One marksheet record per request — a PDF containing two distinct exam records (e.g. two semesters in one file) isn't supported; split into separate files first
- Confidence catches *disagreement* between models, not cases where both happen to agree on the same wrong value (rare, but observed)
- Bounding boxes disabled in production for memory reasons (see above)

Full breakdown with evidence in `approach_note.md`.

---

## Tests
```bash
pytest -v   # 16 tests, no API key needed — LLM calls are mocked
```
```

