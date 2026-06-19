from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, extract, health
from app.core.exceptions import (
    CorruptFileError,
    FileTooLargeError,
    LLMExtractionError,
    UnsupportedFormatError,
    corrupt_file_handler,
    file_too_large_handler,
    llm_extraction_handler,
    unsupported_format_handler,
)
from app.utils.logging_config import setup_logging

setup_logging()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Marksheet Extraction API", version="1.0.0")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.add_exception_handler(FileTooLargeError, file_too_large_handler)
app.add_exception_handler(UnsupportedFormatError, unsupported_format_handler)
app.add_exception_handler(CorruptFileError, corrupt_file_handler)
app.add_exception_handler(LLMExtractionError, llm_extraction_handler)

app.include_router(auth.router, tags=["auth"])
app.include_router(extract.router, tags=["extraction"])
app.include_router(health.router, tags=["health"])


@app.get("/", include_in_schema=False)
async def serve_demo():
    return FileResponse(str(STATIC_DIR / "index.html"))


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)

    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            request_body = operation.get("requestBody", {})
            multipart = request_body.get("content", {}).get("multipart/form-data", {})
            body_schema_ref = multipart.get("schema", {}).get("$ref")
            if not body_schema_ref:
                continue

            schema_name = body_schema_ref.split("/")[-1]
            body_schema = schema.get("components", {}).get("schemas", {}).get(schema_name, {})

            for prop in body_schema.get("properties", {}).values():
                if prop.get("type") == "array" and "contentMediaType" in prop.get("items", {}):
                    prop["items"] = {"type": "string", "format": "binary"}
                elif "contentMediaType" in prop:
                    prop["format"] = "binary"
                    prop.pop("contentMediaType", None)

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi