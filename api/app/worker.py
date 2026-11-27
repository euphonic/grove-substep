"""Background worker: claims jobs from public.jobs and runs their handlers.

Run with `python -m app.worker`. Needs CHECKPOINTER_BACKEND=postgres.
"""

import asyncio
import contextlib
import logging
import signal
from collections.abc import Awaitable, Callable
from typing import Any

from app.config import Settings, get_settings
from app.jobs import Job, PostgresJobQueue
from app.memory.summarize import summarize_thread
from app.runtime import Runtime, open_runtime

log = logging.getLogger("grove.worker")
POLL_SECONDS = 2.0

Handler = Callable[[Runtime, dict[str, Any]], Awaitable[None]]
HANDLERS: dict[str, Handler] = {"summarize": summarize_thread}


async def process_one(rt: Runtime) -> Job | None:
    """Claim and run one job. Returns the job, or None if nothing was ready."""
    job = await rt.jobs.claim()
    if job is None:
        return None
    handler = HANDLERS.get(job.kind)
    try:
        if handler is None:
            raise LookupError(f"no handler for {job.kind}")
        await handler(rt, job.payload)
    except Exception as exc:  # noqa: BLE001
        # Error type only: messages could contain user text.
        log.warning("job %s (%s) failed: %s", job.id, job.kind, type(exc).__name__)
        await rt.jobs.fail(job, type(exc).__name__)
    else:
        await rt.jobs.complete(job)
        log.info("job %s (%s) done", job.id, job.kind)
    return job


async def run(settings: Settings, stop: asyncio.Event) -> None:
    async with open_runtime(settings) as rt:
        if isinstance(rt.jobs, PostgresJobQueue):
            requeued = await rt.jobs.requeue_stale()
            if requeued:
                log.info("requeued %d stale jobs", requeued)
        log.info("worker started; handlers: %s", ", ".join(HANDLERS))
        while not stop.is_set():
            if await process_one(rt) is None:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=POLL_SECONDS)
    log.info("worker stopped")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    stop = asyncio.Event()

    async def _main() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        await run(get_settings(), stop)

    asyncio.run(_main())


if __name__ == "__main__":
    main()
