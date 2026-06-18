import io
from typing import List

import logging

import cv2
import numpy as np

import fitz
from PIL import Image

from app.config import settings
from app.core.exceptions import CorruptFileError, FileTooLargeError, UnsupportedFormatError


logger = logging.getLogger(__name__)

def validate_file(content_type: str, file_bytes: bytes) -> None:
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(settings.max_file_size_mb)
    if content_type not in settings.allowed_content_types:
        raise UnsupportedFormatError(content_type)


def load_pages(content_type: str, file_bytes: bytes) -> List[Image.Image]:
    if content_type == "application/pdf":
        pages = _pdf_to_images(file_bytes)
    else:
        pages = [_load_single_image(file_bytes)]
    return [_deskew(page) for page in pages]


def _deskew(image: Image.Image) -> Image.Image:
    cv_image = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    coords = np.column_stack(np.where(binary > 0))
    if coords.size == 0:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle

    if abs(angle) < 0.5 or abs(angle) > 20:
        logger.info("Deskew: angle %.2f deg outside correction range, leaving image as-is", angle)
        return image

    logger.info("Deskew: rotating image by %.2f degrees", angle)
    h, w = cv_image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    rotated = cv2.warpAffine(cv_image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))

def _load_single_image(file_bytes: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(file_bytes)).convert("RGB")
    except Exception:
        raise CorruptFileError()


def _pdf_to_images(file_bytes: bytes, dpi: int = 200) -> List[Image.Image]:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:
        raise CorruptFileError()

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    pages = [Image.open(io.BytesIO(page.get_pixmap(matrix=matrix).tobytes("png"))) for page in doc]
    doc.close()
    return pages