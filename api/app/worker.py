"""Background worker. Uploads, rendering and summaries arrive in later milestones."""

import logging
import signal
import threading

log = logging.getLogger("grove.worker")
_stop = threading.Event()


def _handle_signal(signum: int, _frame: object) -> None:
    log.info("worker stopping (signal %s)", signum)
    _stop.set()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    log.info("worker started; no jobs registered yet")
    while not _stop.wait(timeout=30):
        log.debug("worker idle")


if __name__ == "__main__":
    main()
