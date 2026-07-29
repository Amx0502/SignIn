from collections import deque
import logging
from threading import RLock


class ClassCubeLogStore:
    def __init__(self, maxlen: int = 500):
        self._records = deque(maxlen=maxlen)
        self._lock = RLock()

    def append(self, message: str) -> None:
        with self._lock:
            self._records.append(str(message))

    def snapshot(self, limit: int = 200) -> list[str]:
        with self._lock:
            return list(self._records)[-max(1, int(limit)):]


class _StoreHandler(logging.Handler):
    def __init__(self, store: ClassCubeLogStore):
        super().__init__()
        self.store = store

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.store.append(self.format(record))
        except Exception:
            self.handleError(record)


def create_class_cube_logger(store: ClassCubeLogStore) -> logging.Logger:
    logger = logging.getLogger("class_cube")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = _StoreHandler(store)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger
