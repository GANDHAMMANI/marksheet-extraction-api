from pathlib import Path

import pytest
from PIL import Image

from app.core.exceptions import CorruptFileError, FileTooLargeError, UnsupportedFormatError
from app.services.file_handler import load_pages, validate_file

SAMPLE_PATH = Path(__file__).parent.parent / "sample_data" / "marks_sheet_1.webp"


def test_validate_file_rejects_oversized_upload():
    huge = b"0" * (11 * 1024 * 1024)
    with pytest.raises(FileTooLargeError):
        validate_file("image/png", huge)


def test_validate_file_rejects_unsupported_type():
    with pytest.raises(UnsupportedFormatError):
        validate_file("application/zip", b"not really a zip")


def test_validate_file_accepts_supported_image():
    validate_file("image/webp", SAMPLE_PATH.read_bytes())


def test_load_pages_returns_one_image_for_a_photo():
    pages = load_pages("image/webp", SAMPLE_PATH.read_bytes())
    assert len(pages) == 1
    assert isinstance(pages[0], Image.Image)


def test_load_pages_raises_on_corrupt_file():
    with pytest.raises(CorruptFileError):
        load_pages("image/png", b"this is not an image")