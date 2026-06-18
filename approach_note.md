# Approach Note

## What this does

Takes a marksheet image or PDF, runs it through two vision LLMs in parallel,
merges the results, and returns structured JSON with a confidence score per field.
The confidence score is the actual interesting part — explained below.

## Extraction

Every input gets normalized to page images first (PyMuPDF for PDFs, Pillow for
images). A quick deskew pass runs using OpenCV before anything hits the model —
photographed documents are often slightly tilted and it helps.

I went with a direct vision LLM approach rather than OCR + text parsing. The reason
is simple: OCR engines like Tesseract read left-to-right with no table awareness.
On a staggered marks table (which most scanned marksheets have), they scramble which
numbers belong to which subject. I actually tested this with OpenDataLoader's hybrid
OCR mode — the output was worse than just sending the image directly to the model.

The prompt tells the model to first figure out the document's own structure (marks
vs grade points, flat vs grouped subjects, etc.) before extracting anything. This
is what makes it generalize — it's not pattern-matching against a known board's
layout.

## Models

**Llama 4 Scout via Groq** — primary model. Fast, vision-capable, free tier.

**MiniMax-M3 via NVIDIA NIM** — cross-validation model. Added specifically because
Scout has a consistent failure on staggered table rows: it transposes adjacent
subjects confidently, with no self-doubt. MiniMax resolved this in testing. So both
run on every request and their outputs get compared.

I checked several other options: Maverick was deprecated, Llama 3.2 Vision
decommissioned, Qwen3-VL gated behind enterprise access. MiniMax was the only
genuinely different vision model accessible without a sales call.

## Confidence scoring

Three layers:

**Self-report** — each model rates its own confidence per field. The prompt gives
it a concrete anchor scale (0.9+ for clear text, 0.6-0.8 for minor ambiguity, etc.)
because without that, models just return 0.9 for everything.

**Cross-model agreement** — if both models return the same value, confidence gets
a small boost. If they disagree, confidence gets halved and a warning fires naming
the exact field and both values. This is the useful part: on the UP Board sample,
Scout alone returned Mathematics=85 at 1.0 confidence with no warning. The ensemble
returned the same value but at 0.475 with an explicit warning. Still wrong, but now
the system is honest about not knowing — which is what you actually want in a
document verification context.

**Rule checks** — required fields that come back null get zeroed confidence. If
the sum of subject marks doesn't match the printed total, a warning fires. This
check is informational only (doesn't penalize confidence) because nested documents
like West Bengal's Madhyamik sheet always fail a naive sum check — they list both
sub-components and combined totals.

## What didn't work

OpenDataLoader hybrid OCR: tested, reverted. 290 seconds per page on CPU, and the
table output was garbled.

Chain-of-thought scratchpad field: tried adding a raw_table_transcript field to
force the model to trace rows before structuring. It broke the schema on West Bengal
— the model started returning bare strings instead of {value, confidence} objects
for subject names. Reverted.

Geometric deskewing: implemented and kept, but didn't fix the UP Board row swap.
The staggering on that document isn't photographic skew — it's the print layout
itself.

## Honest assessment

Works well on grade-point cards and grouped-subject mark sheets. Struggles with
photographed documents where the marks column is visually offset from subject labels
by more than a line — both models make the same confident mistake in that case, so
the agreement check can't catch it. The system correctly flags this when the models
happen to disagree, but not when they consistently agree on the wrong answer.