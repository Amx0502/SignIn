import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait


class ClassCubeScheduler:
    def __init__(
        self,
        service,
        max_workers=2,
        start_thread=True,
        clock=time.monotonic,
    ):
        self.service = service
        self.clock = clock
        self.max_workers = min(2, max(1, int(max_workers)))
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="class-cube",
        )
        self._lock = threading.RLock()
        self._running_task_ids = set()
        self._futures = set()
        self._last_tick = None
        self._stop = threading.Event()
        self._thread = None
        self._closed = False
        self.logger = getattr(service, "logger", logging.getLogger(__name__))
        if start_thread:
            self.start()

    def start(self):
        with self._lock:
            if self._closed or (self._thread and self._thread.is_alive()):
                return
            self._thread = threading.Thread(
                target=self._loop,
                name="class-cube-scheduler",
                daemon=True,
            )
            self._thread.start()

    def _loop(self):
        while not self._stop.wait(1):
            try:
                self.tick()
            except Exception as exc:
                self.logger.error(
                    "班级魔方调度扫描失败（%s）", type(exc).__name__
                )

    def tick(self):
        now = self.clock()
        with self._lock:
            if self._closed:
                return
            if self._last_tick is not None:
                if now < self._last_tick:
                    self._last_tick = now
                    return
                elif now - self._last_tick < 30:
                    return
            self._last_tick = now
        for task in self.service.list_due_tasks():
            self.submit(int(task["id"]))

    def submit(self, task_id):
        task_id = int(task_id)
        with self._lock:
            if self._closed or task_id in self._running_task_ids:
                return False
            self._running_task_ids.add(task_id)
            try:
                future = self._executor.submit(
                    self.service.run_scheduled_task, task_id
                )
            except Exception:
                self._running_task_ids.discard(task_id)
                raise
            self._futures.add(future)
            future.add_done_callback(
                lambda completed, tid=task_id: self._release(tid, completed)
            )
            return True

    def _release(self, task_id, future):
        with self._lock:
            self._running_task_ids.discard(task_id)
            self._futures.discard(future)

    def wait_for_idle(self):
        while True:
            with self._lock:
                futures = tuple(self._futures)
            if not futures:
                return
            wait(futures)

    def shutdown(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._stop.set()
            thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2)
        self._executor.shutdown(wait=True, cancel_futures=True)
