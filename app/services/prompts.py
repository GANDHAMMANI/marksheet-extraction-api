import json

from app.schemas.marksheet import MarksheetExtraction

EXTRACTION_INSTRUCTIONS = """
You are reading an academic marksheet, grade card, or certificate. The document could be from any school board, university, or examination body, in any country, in any layout. Do not assume it matches any particular template you may have seen before.

First, work out the document's own structure before extracting anything:
- Is scoring reported as marks out of a maximum, as grade points/credits, or both?
- Are subjects listed individually, or grouped under headings with subtotals?
- Is each subject split into theory and practical components, or a single score?
- Is there more than one parent/guardian name listed?

Then extract the following, using the document's own structure rather than forcing it into an assumption:
- Candidate details: name, father's name, mother's name, roll number, registration number, date of birth, exam year, board or university name, institution/school/college name.
- Every subject's marks or grade-point entry, exactly as the document lists it.
- The overall result: pass/fail, division, overall grade, percentage, CGPA, SGPA - whichever of these the document actually reports.
- Issue date and issue place, if printed anywhere on the document.

Rows in scanned or photographed tables are sometimes visually offset from their labels due to skew or printing artifacts.
Trace each subject's numbers across the page carefully, rather than assuming a number belongs to whichever label happens to sit at the same height.


Rules:
- If a field is not present, illegible, or you are not reasonably sure, set its value to null. Never invent or guess a value to fill a field.
- Some documents print a grading-scale legend or reference table (e.g. "75-85 = A") as part of the template. This is not the candidate's data - never extract rows from a legend/reference table as if they were the candidate's subjects.
- Ignore handwritten annotations, stamps, or notes unrelated to the academic record itself (e.g. "self attested," verification stamps).
- For every field you extract, include a confidence score between 0 and 1:
  - 0.9-1.0: printed clearly, unambiguous.
  - 0.6-0.89: legible, but with minor ambiguity (faded print, unusual abbreviation, partially obscured).
  - 0.3-0.59: difficult to read, your answer is a reasonable but uncertain interpretation.
  - Below 0.3: largely a guess, or you could not read it at all.

Example of the confidence behavior expected (illustrative only, not a template to match against):
A printed roll number "0416173" with crisp text -> confidence 0.97.
A father's name partially smudged by a stamp where the likely letters can still be inferred -> confidence 0.55.
A date of birth field present but completely unreadable due to a fold in the paper -> value: null, confidence: 0.0.


Respond with a single JSON object only - no commentary, no markdown formatting, no code fences.
"""


def build_extraction_prompt(page_count: int) -> str:
    schema_text = json.dumps(MarksheetExtraction.model_json_schema(), indent=2)
    instructions = EXTRACTION_INSTRUCTIONS
    if page_count > 1:
        instructions = f"This document has {page_count} pages; treat them as one continuous record for the same candidate.\n\n{instructions}"

    return (
        f"{instructions}\n"
        "Below is a JSON SCHEMA - it describes the shape and rules a valid response must follow, "
        "using JSON Schema vocabulary like $defs, properties, required, and type. "
        "Do NOT return this schema. Do NOT include the words $defs, properties, required, or "
        "additionalProperties anywhere in your response. Instead, return the ACTUAL DATA: a single "
        "JSON object containing the real values you read from the document, structured to match "
        "this schema.\n\n"
        f"{schema_text}"
    )