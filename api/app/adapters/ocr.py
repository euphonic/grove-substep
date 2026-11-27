"""OCR adapter for photos of handwritten journals."""

from typing import Protocol

from app.config import Settings

MOCK_OCR_TEXT = "Synthetic handwriting sample. This text is a mock OCR result."


class OCR(Protocol):
    def extract_text(self, image: bytes, mime: str) -> str: ...


class MockOCR:
    def extract_text(self, image: bytes, mime: str) -> str:
        return MOCK_OCR_TEXT


def get_ocr(settings: Settings) -> OCR:
    if settings.ocr_mode == "mock":
        return MockOCR()
    raise NotImplementedError("Gemini vision OCR is wired up in M4")
