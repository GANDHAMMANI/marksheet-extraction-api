import asyncio

from fastapi import APIRouter, Depends, UploadFile

from app.api.deps import get_current_user
from app.schemas.marksheet import BatchItemResult, MarksheetExtraction
from app.services.extraction import extract_marksheet

router = APIRouter()


@router.post("/extract", response_model=MarksheetExtraction)
async def extract_single(file: UploadFile, _user: str = Depends(get_current_user)) -> MarksheetExtraction:
    file_bytes = await file.read()
    return await extract_marksheet(file.content_type, file_bytes)


@router.post("/extract/batch", response_model=list[BatchItemResult])
async def extract_batch(files: list[UploadFile], _user: str = Depends(get_current_user)) -> list[BatchItemResult]:
    uploads = [(f.filename, f.content_type, await f.read()) for f in files]
    outcomes = await asyncio.gather(
        *(extract_marksheet(content_type, data) for _, content_type, data in uploads),
        return_exceptions=True,
    )

    results = []
    for (filename, _, _), outcome in zip(uploads, outcomes):
        if isinstance(outcome, Exception):
            results.append(BatchItemResult(filename=filename, success=False, error=str(outcome)))
        else:
            results.append(BatchItemResult(filename=filename, success=True, data=outcome))
    return results