from collections import OrderedDict
from contextlib import contextmanager
import math
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable

import requests


class ClassCubeGeocoderError(RuntimeError):
    pass


class ClassCubeGeocoder:
    """Small Nominatim client with process-wide throttling and an in-memory cache."""

    def __init__(
        self,
        *,
        base_url: str,
        user_agent: str,
        cache_ttl_seconds: float = 24 * 60 * 60,
        cache_limit: int = 512,
        minimum_interval_seconds: float = 1.0,
        shared_rate_file: str | Path | None = None,
        clock: Callable[[], float] | None = None,
        session: requests.Session | None = None,
    ):
        self.base_url = str(base_url).rstrip("/")
        self.user_agent = str(user_agent).strip()
        self.cache_ttl_seconds = max(float(cache_ttl_seconds), 0.0)
        self.cache_limit = max(int(cache_limit), 1)
        self.minimum_interval_seconds = max(
            float(minimum_interval_seconds),
            1.0,
        )
        self.shared_rate_file = (
            Path(shared_rate_file)
            if shared_rate_file else None
        )
        self._clock = clock or time.monotonic
        self._session = session or requests.Session()
        self._owns_session = session is None
        self._cache: OrderedDict[
            tuple[str, int],
            tuple[float, tuple[dict[str, Any], ...]],
        ] = OrderedDict()
        self._lock = threading.RLock()
        self._last_request_at: float | None = None

    @contextmanager
    def _shared_rate_slot(self):
        if self.shared_rate_file is None:
            yield False
            return
        handle = None
        locked = False
        try:
            self.shared_rate_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            handle = self.shared_rate_file.open("a+b")
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0\n")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            locked = True
            handle.seek(0)
            try:
                last_started_at = float(
                    handle.read().decode("ascii", "ignore").strip()
                    or 0
                )
            except (TypeError, ValueError):
                last_started_at = 0
            wait_seconds = (
                self.minimum_interval_seconds
                - (time.time() - last_started_at)
            )
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            handle.seek(0)
            handle.truncate()
            handle.write(f"{time.time():.6f}\n".encode("ascii"))
            handle.flush()
            yield True
        except OSError:
            yield False
        finally:
            if handle is not None:
                if locked:
                    try:
                        handle.seek(0)
                        if os.name == "nt":
                            import msvcrt

                            msvcrt.locking(
                                handle.fileno(),
                                msvcrt.LK_UNLCK,
                                1,
                            )
                        else:
                            import fcntl

                            fcntl.flock(
                                handle.fileno(),
                                fcntl.LOCK_UN,
                            )
                    except OSError:
                        pass
                handle.close()

    def _wait_for_rate_slot(self) -> None:
        with self._shared_rate_slot() as used_shared_slot:
            if used_shared_slot:
                self._last_request_at = self._clock()
                return
            now = self._clock()
            if self._last_request_at is not None:
                wait_seconds = (
                    self.minimum_interval_seconds
                    - (now - self._last_request_at)
                )
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
            self._last_request_at = self._clock()

    @staticmethod
    def _query_key(query: str) -> str:
        return " ".join(str(query or "").strip().split()).casefold()

    @staticmethod
    def _copy_results(
        results: tuple[dict[str, Any], ...],
    ) -> list[dict[str, Any]]:
        return [dict(item) for item in results]

    def _cached(
        self,
        key: tuple[str, int],
        now: float,
    ) -> list[dict[str, Any]] | None:
        cached = self._cache.get(key)
        if cached is None:
            return None
        stored_at, results = cached
        if now - stored_at > self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return self._copy_results(results)

    @staticmethod
    def _normalize_results(payload: Any) -> tuple[dict[str, Any], ...]:
        if not isinstance(payload, list):
            raise ClassCubeGeocoderError("地址搜索服务返回了无效数据")
        normalized: list[dict[str, Any]] = []
        seen: set[tuple[float, float, str]] = set()
        for row in payload:
            if not isinstance(row, dict):
                continue
            try:
                latitude = float(row.get("lat"))
                longitude = float(row.get("lon"))
            except (TypeError, ValueError):
                continue
            if (
                not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                continue
            address = str(row.get("display_name") or "").strip()
            if not address:
                continue
            dedupe_key = (
                round(latitude, 7),
                round(longitude, 7),
                address.casefold(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            name = str(row.get("name") or "").strip()
            if not name:
                name = address.split(",", 1)[0].strip()
            address_parts = row.get("address")
            if not isinstance(address_parts, dict):
                address_parts = {}
            city = str(
                address_parts.get("city")
                or address_parts.get("municipality")
                or address_parts.get("town")
                or address_parts.get("village")
                or ""
            ).strip()
            district = str(
                address_parts.get("city_district")
                or address_parts.get("county")
                or address_parts.get("suburb")
                or ""
            ).strip()
            normalized.append({
                "id": f"nominatim:{row.get('place_id', len(normalized))}",
                "name": name or "搜索结果",
                "address": address,
                "latitude": latitude,
                "longitude": longitude,
                "category": str(
                    row.get("category") or row.get("class") or ""
                ),
                "type": str(row.get("type") or ""),
                "province": str(address_parts.get("state") or "").strip(),
                "city": city,
                "district": district,
                "provider": "nominatim",
                "coordinate_system": "WGS84",
            })
        return tuple(normalized)

    def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        normalized_query = " ".join(str(query or "").strip().split())
        if len(normalized_query) < 2:
            raise ValueError("请至少输入 2 个字符搜索地址")
        normalized_limit = min(max(int(limit), 1), 8)
        key = (self._query_key(normalized_query), normalized_limit)

        with self._lock:
            now = self._clock()
            cached = self._cached(key, now)
            if cached is not None:
                return cached

            self._wait_for_rate_slot()

            try:
                response = self._session.get(
                    f"{self.base_url}/search",
                    params={
                        "q": normalized_query,
                        "format": "jsonv2",
                        "addressdetails": 1,
                        "limit": normalized_limit,
                        "countrycodes": "cn",
                        "accept-language": "zh-CN,zh,en",
                    },
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": "application/json",
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
                    },
                    timeout=10,
                )
                response.raise_for_status()
                results = self._normalize_results(response.json())
            except (
                requests.RequestException,
                ValueError,
                TypeError,
            ) as exc:
                raise ClassCubeGeocoderError(
                    "地址搜索服务暂时不可用"
                ) from exc

            stored_at = self._clock()
            self._cache[key] = (stored_at, results)
            self._cache.move_to_end(key)
            while len(self._cache) > self.cache_limit:
                self._cache.popitem(last=False)
            return self._copy_results(results)

    def close(self) -> None:
        with self._lock:
            self._cache.clear()
            if self._owns_session:
                self._session.close()
