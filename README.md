# Marksheet Extraction API

FastAPI service that reads academic marksheets and returns structured JSON with per-field confidence scores. Two vision models run in parallel, cross-validate each other's output, and Tesseract pins each field to its location on the page.

**Live:** https://marksheet-extraction-api-1-5h3g.onrender.com  
**Swagger:** https://marksheet-extraction-api-1-5h3g.onrender.com/docs  
**Approach note:** `approach_note.md` in this repo

---

## Stack
- FastAPI + Pydantic v2
- Llama 4 Scout (Groq) + MiniMax-M3 (NVIDIA NIM) — dual vision LLMs running concurrently
- Tesseract OCR — bounding box location only, not text extraction
- PyMuPDF + Pillow + OpenCV — file normalization and deskew
- JWT auth, async parallel model calls, 16 passing unit tests

---

## Why two models

A single vision model on a photographed marksheet will occasionally transpose adjacent subject rows with full confidence and zero self-doubt — the kind of silent wrong answer that's worse than no answer. Running Scout and MiniMax-M3 independently on the same document and comparing their outputs field by field converts that into an explicit low-confidence warning. When they agree, that agreement is real signal. When they don't, you know exactly where to look.

This wasn't a day-one decision. The pipeline started Gemini-first (quota issues), moved to Groq-only, hit the row-swap failure, went through OpenDataLoader hybrid OCR (tested, reverted — 290 seconds per page and worse accuracy than the model's own reading), geometric deskewing (implemented, kept, didn't fix the core issue), and a chain-of-thought scratchpad field (broke the schema on grouped-subject documents). The ensemble was the fix that actually worked without breaking what already did.

---

## Confidence scoring

Three layers, each catching something different:

**Cross-model agreement** — the main signal. Both models rate their own confidence per field, but those self-ratings are only half the story. If Scout says 0.95 and MiniMax says 0.95 for the same value, that's one thing. If Scout says 0.95 for "Mathematics: 85" and MiniMax says 0.95 for "Mathematics: 73", the confidence on that field gets halved and a warning fires — regardless of what either model thought of itself.

**Model self-report** — the prompt anchors confidence to a concrete scale (0.9+ for clearly printed text, 0.6–0.8 for minor ambiguity, below 0.5 for genuine uncertainty). Without that anchor, models return 0.9 for everything.

**Rule-based checks** — required fields that come back null get zeroed. Subject marks that don't sum to the printed total get a warning. These run independently of anything the model claims.

---

## Bounding boxes

Tesseract runs after extraction — not for reading text (that's the VLM's job), just for locating words on the page. Each extracted value gets searched in Tesseract's word-coordinate output using fuzzy matching to handle OCR errors. Coordinates normalize to 0–1 so they scale to any display size. Fields with model disagreements don't get bboxes, which is correct — if we're not confident in a value we shouldn't claim to know where it is either.

The preprocessing matters here: scale the image 2.5x before passing to Tesseract (48 words detected at original size, 170 after scaling), convert to grayscale, apply adaptive thresholding for uneven lighting. Without that, most words fall below Tesseract's confidence cutoff on photographed documents.

---

## Setup

Needs Python 3.11+, Tesseract installed locally, Groq and NVIDIA NIM API keys.

```bash
git clone https://github.com/GANDHAMMANI/marksheet-extraction-api.git
cd marksheet-extraction-api
python -m venv venv && venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env   # fill in your keys
uvicorn app.main:app --reload
```

Demo UI at `localhost:8000`, Swagger at `localhost:8000/docs`.

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /token | No | Get JWT token |
| POST | /extract | Bearer | Single marksheet |
| POST | /extract/batch | Bearer | Multiple files, one request |
| GET | /health | No | Uptime check |

---

## Tests

```bash
pytest -v   # 16 tests, no API key needed — LLM calls are mocked
```

Confidence logic and file validation tested with synthetic inputs so they run in isolation. The mock patches by function name so provider swaps don't break tests.