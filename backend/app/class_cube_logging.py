from collections import deque
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import re
from threading import RLock

from . import config


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

    def load_tail(self, path: Path, limit: int = 500) -> None:
        try:
            lines = path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except OSError:
            return
        with self._lock:
            for line in lines[-max(1, int(limit)):]:
                self._records.append(line)


class _StoreHandler(logging.Handler):
    def __init__(self, store: ClassCubeLogStore):
        super().__init__()
        self.store = store

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.store.append(self.format(record))
        except Exception:
            self.handleError(record)


class _SensitiveFilter(logging.Filter):
    _assignment = re.compile(
        r"(?i)\b(cookie|password|remember_student_[\w-]+)"
        r"\s*=\s*([^\s;]+)"
    )
    _webhook = re.compile(
        r"https://qyapi\.weixin\.qq\.com/"
        r"cgi-bin/webhook/send\?key=[^\s]+",
        re.IGNORECASE,
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        message = self._assignment.sub(
            lambda match: f"{match.group(1)}=******",
            message,
        )
        message = self._webhook.sub(
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=******",
            message,
        )
        record.msg = message
        record.args = ()
        return True


def create_class_cube_logger(
    store: ClassCubeLogStore,
    log_path: Path | None = None,
) -> logging.Logger:
    path = Path(log_path or (config.LOG_DIR / "class_cube.log"))
    path.parent.mkdir(parents=True, exist_ok=True)
    store.load_tail(path)
    logger = logging.getLogger("class_cube")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for existing in tuple(logger.handlers):
        existing.close()
    logger.handlers.clear()
    logger.filters.clear()
    logger.addFilter(_SensitiveFilter())
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )
    memory_handler = _StoreHandler(store)
    memory_handler.setFormatter(formatter)
    file_handler = TimedRotatingFileHandler(
        path,
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(memory_handler)
    logger.addHandler(file_handler)
    return logger
