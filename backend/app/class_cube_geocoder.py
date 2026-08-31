from collections import OrderedDict
import math
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
        self._clock = clock or time.monotonic
        self._session = session or requests.Session()
        self._owns_session = session is None
        self._cache: OrderedDict[
            tuple[str, int],
            tuple[float, tuple[dict[str, Any], ...]],
        ] = OrderedDict()
        self._lock = threading.RLock()
        self._last_request_at: float | None = None

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

            if self._last_request_at is not None:
                wait_seconds = (
                    self.minimum_interval_seconds
                    - (now - self._last_request_at)
                )
                if wait_seconds > 0:
                    time.sleep(wait_seconds)

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
                self._last_request_at = self._clock()
                response.raise_for_status()
                results = self._normalize_results(response.json())
            except (
                requests.RequestException,
                ValueError,
                TypeError,
            ) as exc:
                self._last_request_at = self._clock()
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
