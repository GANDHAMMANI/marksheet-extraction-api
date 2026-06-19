import asyncio
import json
import logging

from app.config import settings
from app.core.exceptions import LLMExtractionError
from app.schemas.marksheet import MarksheetExtraction
from app.services import bbox_locator, confidence, file_handler, llm_client
from app.services.prompts import build_extraction_prompt

logger = logging.getLogger(__name__)

MINIMAX_TIMEOUT_SECONDS = 45


async def extract_marksheet(content_type: str, file_bytes: bytes) -> MarksheetExtraction:
    file_handler.validate_file(content_type, file_bytes)
    pages = file_handler.load_pages(content_type, file_bytes)
    prompt = build_extraction_prompt(len(pages))

    logger.info("Starting extraction: %d page(s), content_type=%s", len(pages), content_type)

    scout_task = asyncio.create_task(llm_client.call_scout(pages, prompt))
    minimax_task = asyncio.create_task(llm_client.call_minimax(pages, prompt))

    raw_scout = await scout_task
    scout_pass = _parse(raw_scout, "Scout")

    try:
        raw_minimax = await asyncio.wait_for(minimax_task, timeout=MINIMAX_TIMEOUT_SECONDS)
        minimax_pass = _parse(raw_minimax, "MiniMax")
        result = confidence.merge_and_score(scout_pass, minimax_pass)
    except (asyncio.TimeoutError, LLMExtractionError) as exc:
        logger.warning("MiniMax unavailable (%s), falling back to Scout-only result", exc)
        minimax_task.cancel()
        result = confidence.merge_and_score(scout_pass, scout_pass)
        result.warnings.append("MiniMax cross-validation unavailable for this request; result reflects Scout only")

    if settings.enable_bbox_locator:
        try:
            await asyncio.to_thread(bbox_locator.locate_fields, result, pages)
        except Exception as exc:
            logger.warning("Bounding box location failed, continuing without it: %s", exc)

    logger.info("Extraction complete: document_confidence=%.3f, warnings=%d",
                result.document_confidence, len(result.warnings))
    return result


def _parse(raw_json: str, model_name: str) -> MarksheetExtraction:
    try:
        return MarksheetExtraction(**json.loads(raw_json))
    except Exception as exc:
        logger.error("%s returned invalid data: %s", model_name, exc)
        logger.debug("Raw response from %s: %.500s", model_name, raw_json)
        raise LLMExtractionError(f"Model returned invalid data: {exc}")