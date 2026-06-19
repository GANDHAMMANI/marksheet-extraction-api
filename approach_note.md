# Approach Note

## What this does

Takes a marksheet image or PDF, runs it through two vision LLMs in parallel,
merges the results, and returns structured JSON with a confidence score per field.
The confidence score is the actual interesting part — explained below.

## Extraction

Every input gets normalized to page images first (PyMuPDF for PDFs, Pillow for
images). A quick deskew pass runs using OpenCV before anything hits the model.

I went with a direct vision LLM approach rather than OCR + text parsing. OCR
engines like Tesseract read left-to-right with no table awareness — on a
staggered marks table they scramble which numbers belong to which subject.
Tested this directly with OpenDataLoader's hybrid OCR mode; the output was
worse than just sending the image to the model.

The prompt tells the model to figure out the document's own structure first
(marks vs grade points, flat vs grouped subjects) before extracting anything,
rather than pattern-matching a known board's layout.

## Models

**Llama 4 Scout via Groq** — primary model. Fast, vision-capable, free tier.

**MiniMax-M3 via NVIDIA NIM** — cross-validation model. Added because Scout has
a consistent failure on staggered table rows: it transposes adjacent subjects
confidently, no self-doubt. MiniMax resolved this correctly in testing.

Checked several other options: Maverick was deprecated on Groq, Llama 3.2
Vision decommissioned, Qwen3-VL gated behind enterprise access, GPT-OSS-120B
is text-only despite the name.

NVIDIA's endpoint is a trial/eval service, not committed production
infrastructure, and it showed — response times ranged from 8 seconds to over
5 minutes, occasionally timing out with a 504. Added a 45-second timeout on
the MiniMax call specifically; if it doesn't respond in time, the system
falls back to a Scout-only result with a warning explaining why, instead of
hanging the request or failing outright. Confirmed both modes working in the
same testing session — full ensemble on most requests, clean fallback when
NVIDIA was slow.

## Confidence scoring

Three layers:

**Self-report** — each model rates its own confidence with a concrete anchor
scale in the prompt (0.9+ clear text, 0.6-0.8 minor ambiguity, etc). Without
that anchor, models just return 0.9 for everything.

**Cross-model agreement** — if both models return the same value, confidence
gets a small boost. If they disagree, confidence gets halved and a warning
fires naming the field and both values. This is the useful part: on the UP
Board sample, Scout alone returned Mathematics=85 at 1.0 confidence with no
warning — wrong, and silently so. The ensemble caught the disagreement,
dropped confidence to 0.475, and flagged exactly that field. Tested this
again later on my own postgrad transcripts and the ensemble correctly
resolved two genuinely swapped grades that Scout alone would have missed.

**Rule checks** — required fields that come back null get zeroed confidence.
Sum-of-marks mismatches get a warning, not a confidence penalty, since
documents with nested sub-components and combined totals (West Bengal
Madhyamik) always fail a naive sum check.

## What didn't work

OpenDataLoader hybrid OCR: tested, reverted. 290 seconds per page on CPU,
garbled table output.

Chain-of-thought scratchpad field: tried forcing the model to transcribe the
table before structuring it. Broke the schema on West Bengal — model started
returning bare strings instead of proper field objects. Reverted.

Geometric deskewing: kept, but didn't fix the UP Board row swap. The
staggering there isn't photographic skew, it's the print layout itself.

## Production reliability

Render's free tier gave 512MB RAM, which wasn't enough headroom for Tesseract
OCR preprocessing (2.5x image upscale + adaptive thresholding) running
alongside two concurrent LLM calls — caused intermittent process crashes
under memory pressure. Bounding box location is implemented and works
correctly locally (toggled via ENABLE_BBOX_LOCATOR), but disabled on the
deployed instance to keep extraction reliable. Reliability over a bonus
feature felt like the right tradeoff given the constraint.

## Tested on real, unseen documents

Beyond the three provided samples, ran my own postgraduate semester grade
cards through it — a structurally different format (Credits / Grade Point /
Letter Grade columns) not in the original sample set. Subject extraction was
accurate across both semesters. Found a new, repeatable failure mode here:
MiniMax consistently misreads small checkmark annotations next to letter
grades as "+/-" modifiers that don't exist in the source document. Both
passes disagree on which modifier, so the system correctly flags low
confidence on those fields, even though neither model's value is exactly
right. Also found a real schema gap from this: there's no dedicated field
for a 0-10 grade-point value separate from credits, so the model
inconsistently maps it into obtained_credits across documents.

Also found and fixed a real bug through this testing: the sum-check warning
was firing as a false positive and tanking confidence on West Bengal's
correctly-extracted total, since that document lists sub-components and
combined totals separately. Made the check informational only.

## Honest assessment

Works well on grade-point cards and grouped-subject mark sheets — close to
perfect on the West Bengal and postgrad samples across repeated runs.
Struggles with photographed documents where the marks column is visually
offset from subject labels — both models can make the same confident mistake
there, which the agreement check can't catch since it only protects against
the two models disagreeing, not agreeing on the same wrong answer.