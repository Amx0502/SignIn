import asyncio
import json
from collections.abc import AsyncIterator


def format_version_event(version: int) -> str:
    payload = json.dumps({"version": version}, separators=(",", ":"))
    return f"event: version\ndata: {payload}\n\n"


class MenuEventBroker:
    def __init__(self):
        self._condition = asyncio.Condition()
        self._version = 0

    async def publish(self, version: int) -> None:
        async with self._condition:
            self._version = max(self._version, int(version))
            self._condition.notify_all()

    async def subscribe(
        self,
        *,
        last_version: int = 0,
        heartbeat_seconds: float = 15,
    ) -> AsyncIterator[str]:
        observed = int(last_version)
        while True:
            try:
                async with self._condition:
                    await asyncio.wait_for(
                        self._condition.wait_for(
                            lambda: self._version > observed
                        ),
                        timeout=heartbeat_seconds,
                    )
                    observed = self._version
                yield format_version_event(observed)
            except TimeoutError:
                yield ": keep-alive\n\n"
