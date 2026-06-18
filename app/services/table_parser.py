import asyncio
import io
import logging
import tempfile
from pathlib import Path

import opendataloader_pdf
from PIL import Image

logger = logging.getLogger(__name__)

def extract_table_text(image: Image.Image) -> str | None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = Path(tmp_dir) / "page.pdf"
        pdf_path.write_bytes(_image_to_pdf_bytes(image))

        try:
            opendataloader_pdf.convert(
                input_path=[str(pdf_path)],
                output_dir=tmp_dir,
                format="markdown",
                hybrid="docling-fast",
                hybrid_mode="full",
            )
        except Exception as exc:
            logger.warning("OpenDataLoader extraction failed, falling back to image-only: %s", exc)
            return None

        markdown_path = Path(tmp_dir) / "page.md"
        if not markdown_path.exists():
            logger.warning("OpenDataLoader produced no markdown output for this page")
            return None

        content = markdown_path.read_text(encoding="utf-8")
        logger.warning("OpenDataLoader output (%d chars): %s", len(content), content[:300])
        return content

def _image_to_pdf_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PDF")
    return buffer.getvalue()


async def extract_table_text_async(images: list[Image.Image]) -> str | None:
    results = await asyncio.gather(*(asyncio.to_thread(extract_table_text, img) for img in images))
    texts = [t for t in results if t]
    return "\n\n".join(texts) if texts else None