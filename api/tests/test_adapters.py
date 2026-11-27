import io
import math
import wave
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

from app.adapters.embeddings import get_embedder
from app.adapters.images import get_images
from app.adapters.llm import CANNED_REPLIES, get_chat_model
from app.adapters.ocr import MOCK_OCR_TEXT, get_ocr
from app.adapters.storage import LocalStorage, get_storage
from app.adapters.tts import SAMPLE_RATE, estimated_seconds, get_tts
from app.config import Settings


def test_mock_llm_is_deterministic(settings: Settings) -> None:
    model = get_chat_model(settings, "main")
    msgs = [HumanMessage(content="hello")]
    a, b = model.invoke(msgs).content, model.invoke(msgs).content
    assert a == b and a in CANNED_REPLIES


def test_mock_llm_streams_same_text(settings: Settings) -> None:
    model = get_chat_model(settings, "fast")
    msgs = [HumanMessage(content="stream me")]
    streamed = "".join(str(c.content) for c in model.stream(msgs))
    assert streamed == model.invoke(msgs).content


def test_mock_embeddings_shape_and_determinism(settings: Settings) -> None:
    emb = get_embedder(settings)
    v1, v2, v3 = emb.embed(["a", "a", "b"])
    assert len(v1) == settings.embedding_dim
    assert v1 == v2 and v1 != v3
    assert math.isclose(sum(x * x for x in v1), 1.0, rel_tol=1e-9)


def test_mock_tts_length_matches_text(settings: Settings) -> None:
    text = " ".join(["breathe"] * 150)  # ~60 seconds
    audio = get_tts(settings).synthesize(text, voice_id="any")
    with wave.open(io.BytesIO(audio)) as w:
        seconds = w.getnframes() / SAMPLE_RATE
    assert math.isclose(seconds, estimated_seconds(text), abs_tol=0.01)
    assert math.isclose(seconds, 60.0, abs_tol=0.01)


def test_placeholder_image_is_svg_and_stable(settings: Settings) -> None:
    imgs = get_images(settings)
    a, mime = imgs.image_for("mindfulness", "calm", "morning")
    b, _ = imgs.image_for("mindfulness", "calm", "morning")
    assert mime == "image/svg+xml" and a == b and a.startswith(b"<svg")


def test_local_storage_roundtrip(settings: Settings) -> None:
    store = get_storage(settings)
    store.put("audio/x.wav", b"data")
    assert store.get("audio/x.wav") == b"data"
    assert store.url("audio/x.wav") == "/media/audio/x.wav"


def test_local_storage_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).put("../escape.txt", b"x")


def test_mock_ocr(settings: Settings) -> None:
    assert get_ocr(settings).extract_text(b"", "image/png") == MOCK_OCR_TEXT
