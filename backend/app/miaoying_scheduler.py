import logging
import threading


class MiaoyingScheduler:
    def __init__(self, service):
        self.service = service
        self._stop = threading.Event()
        self._thread = None
        self.logger = logging.getLogger("miaoying.scheduler")

    def start(self):
        if self._thread and self._thread.is_alive(): return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="miaoying-scheduler", daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.wait(2):
            try: self.service.run_due_tasks()
            except Exception as exc: self.logger.error("秒应调度扫描失败：%s", exc)

    def shutdown(self):
        self._stop.set()
        if self._thread: self._thread.join(timeout=3)
        self._thread = None
