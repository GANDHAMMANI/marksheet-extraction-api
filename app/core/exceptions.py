import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class FileTooLargeError(Exception):
    def __init__(self, max_size_mb: int):
        self.max_size_mb = max_size_mb


class UnsupportedFormatError(Exception):
    def __init__(self, content_type: str):
        self.content_type = content_type


class CorruptFileError(Exception):
    pass


class LLMExtractionError(Exception):
    def __init__(self, detail: str):
        self.detail = detail


async def file_too_large_handler(request: Request, exc: FileTooLargeError):
    logger.warning("File too large: exceeded %dMB limit", exc.max_size_mb)
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={"error": "file_too_large", "message": f"File exceeds the {exc.max_size_mb}MB limit"},
    )


async def unsupported_format_handler(request: Request, exc: UnsupportedFormatError):
    logger.warning("Unsupported format: %s", exc.content_type)
    return JSONResponse(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        content={"error": "unsupported_format", "message": f"'{exc.content_type}' is not supported. Use JPG, PNG, or PDF"},
    )


async def corrupt_file_handler(request: Request, exc: CorruptFileError):
    logger.warning("Corrupt file uploaded")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "corrupt_file", "message": "The uploaded file could not be read"},
    )


async def llm_extraction_handler(request: Request, exc: LLMExtractionError):
    logger.error("Extraction failed: %s", exc.detail)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "extraction_failed", "message": exc.detail},
    )