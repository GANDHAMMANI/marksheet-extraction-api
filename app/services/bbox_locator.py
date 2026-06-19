import logging
import re
import shutil
from typing import Optional

import pytesseract
from PIL import Image, ImageEnhance
from pydantic import BaseModel as PydanticBase
import cv2
import numpy as np
from app.schemas.marksheet import FieldValue, NumericFieldValue

logger = logging.getLogger(__name__)

if shutil.which("tesseract") is None:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def locate_fields(result, pages: list[Image.Image]) -> None:
    if not pages:
        return
    page = pages[0]
    img_w, img_h = page.size
    try:
        word_boxes = _get_word_boxes(page)
        logger.info("Tesseract found %d words on page", len(word_boxes))
    except Exception as e:
        logger.warning("Tesseract failed, skipping bbox location: %s", e)
        return
    if not word_boxes:
        return
    _walk(result, word_boxes, img_w, img_h)


def _get_word_boxes(image: Image.Image) -> list[dict]:
    scale = 2.5

    
    cv_img = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)

   
    new_w = int(cv_img.shape[1] * scale)
    new_h = int(cv_img.shape[0] * scale)
    cv_img = cv2.resize(cv_img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    
    cv_img = cv2.adaptiveThreshold(
        cv_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )

    pil_img = Image.fromarray(cv_img)

    data = pytesseract.image_to_data(
        pil_img,
        lang="eng",
        config="--psm 3 --oem 3",
        output_type=pytesseract.Output.DICT,
    )

    boxes = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = int(data["conf"][i])
        if text and conf > 0:
           
            boxes.append({
                "text": text,
                "x": int(data["left"][i] / scale),
                "y": int(data["top"][i] / scale),
                "w": int(data["width"][i] / scale),
                "h": int(data["height"][i] / scale),
                "conf": conf,
            })
    return boxes

def _walk(obj, word_boxes, img_w, img_h):
    if obj is None:
        return
    if isinstance(obj, (FieldValue, NumericFieldValue)):
        if obj.value is not None and obj.bbox is None:
            bbox = _find_bbox(str(obj.value), word_boxes, img_w, img_h)
            if bbox:
                obj.bbox = bbox
        return
    if isinstance(obj, list):
        for item in obj:
            _walk(item, word_boxes, img_w, img_h)
        return
    
    if isinstance(obj, PydanticBase):
        for field_name in type(obj).model_fields:
            _walk(getattr(obj, field_name, None), word_boxes, img_w, img_h)


def _find_bbox(value: str, word_boxes: list[dict], img_w: int, img_h: int) -> Optional[list[float]]:
    value = value.strip()
    if not value or len(value) < 2:
        return None

    words = value.upper().split()
    result = _search(words, word_boxes, img_w, img_h)
    if result:
        return result

    
    alt_words = re.split(r"[-/.,]", value.upper())
    alt_words = [w.strip() for w in alt_words if w.strip() and len(w.strip()) >= 2]
    if len(alt_words) > 1 and alt_words != words:
        result = _search(alt_words, word_boxes, img_w, img_h)
        if result:
            return result

    
    if len(words) > 3:
        return _search(words[:3], word_boxes, img_w, img_h)

    return None


def _search(words: list[str], word_boxes: list[dict], img_w: int, img_h: int) -> Optional[list[float]]:
    if not words:
        return None
    texts = [b["text"].upper() for b in word_boxes]

    if len(words) == 1:
        for i, b in enumerate(word_boxes):
            if _match(texts[i], words[0]):
                return _norm(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"], img_w, img_h)
        return None

   
    for start in range(len(word_boxes) - len(words) + 1):
        if all(_match(texts[start + j], words[j]) for j in range(len(words))):
            group = word_boxes[start: start + len(words)]
            return _norm(
                min(b["x"] for b in group), min(b["y"] for b in group),
                max(b["x"] + b["w"] for b in group), max(b["y"] + b["h"] for b in group),
                img_w, img_h,
            )

    
    if len(words) >= 3:
        for start in range(len(word_boxes) - 1):
            if _match(texts[start], words[0]) and _match(texts[start + 1], words[1]):
                end = start + 1
                j = 2
                while j < len(words) and end + 1 < len(word_boxes):
                    end += 1
                    if _match(texts[end], words[j]):
                        j += 1
                if j >= max(2, len(words) // 2):
                    group = word_boxes[start: end + 1]
                    return _norm(
                        min(b["x"] for b in group), min(b["y"] for b in group),
                        max(b["x"] + b["w"] for b in group), max(b["y"] + b["h"] for b in group),
                        img_w, img_h,
                    )
    return None


def _match(ocr: str, target: str) -> bool:
    if ocr == target:
        return True
    ocr_c = re.sub(r"[^A-Z0-9]", "", ocr)
    tgt_c = re.sub(r"[^A-Z0-9]", "", target)
    if not ocr_c or not tgt_c:
        return False
    if ocr_c == tgt_c:
        return True
    if len(ocr_c) >= 4 and len(tgt_c) >= 4 and abs(len(ocr_c) - len(tgt_c)) <= 1:
        diffs = sum(a != b for a, b in zip(ocr_c, tgt_c[:len(ocr_c)]))
        return diffs <= 1
    return False


def _norm(x1, y1, x2, y2, img_w, img_h) -> list[float]:
    pad = 4
    return [
        round(max(0, x1 - pad) / img_w, 4),
        round(max(0, y1 - pad) / img_h, 4),
        round(min(img_w, x2 + pad) / img_w, 4),
        round(min(img_h, y2 + pad) / img_h, 4),
    ]