import pytest

from app.jobs import InMemoryJobQueue

pytestmark = pytest.mark.anyio


async def test_payload_must_be_ids_not_content() -> None:
    q = InMemoryJobQueue()
    with pytest.raises(ValueError, match="short id"):
        await q.enqueue("summarize", {"text": "x" * 200})
    with pytest.raises(ValueError):
        await q.enqueue("summarize", {"messages": ["a"]})  # type: ignore[dict-item]


async def test_unknown_job_kind_fails_cleanly(settings: object) -> None:
    from app.config import Settings
    from app.runtime import open_runtime
    from app.worker import process_one

    assert isinstance(settings, Settings)
    async with open_runtime(settings) as rt:
        await rt.jobs.enqueue("nope", {"id": "1"})
        await process_one(rt)
        assert isinstance(rt.jobs, InMemoryJobQueue)
        assert rt.jobs.failed[0][1] == "LookupError"
