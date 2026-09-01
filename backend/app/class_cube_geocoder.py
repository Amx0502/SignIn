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
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = bool(retryable)


class ClassCubeGeocoder:
    """Small Nominatim client with process-wide throttling and an in-memory cache."""

    def __init__(
        self,
        *,
        base_url: str,
        user_agent: str,
        provider: str = "nominatim",
        account_id: str = "",
        api_key: str = "",
        coordinate_system: str = "gcj02",
        cache_ttl_seconds: float = 24 * 60 * 60,
        cache_limit: int = 512,
        minimum_interval_seconds: float | None = None,
        shared_rate_file: str | Path | None = None,
        clock: Callable[[], float] | None = None,
        session: requests.Session | None = None,
    ):
        self.base_url = str(base_url).rstrip("/")
        self.user_agent = str(user_agent).strip()
        self.provider = str(provider or "nominatim").strip().lower()
        if self.provider not in {"amap", "apihz", "nominatim", "tencent"}:
            self.provider = "tencent"
        self.account_id = str(account_id or "").strip()
        self.api_key = str(api_key or "").strip()
        self.coordinate_system = (
            "GCJ02"
            if str(coordinate_system or "").strip().lower() == "gcj02"
            else "WGS84"
        )
        self.cache_ttl_seconds = max(float(cache_ttl_seconds), 0.0)
        self.cache_limit = max(int(cache_limit), 1)
        default_interval = 6.1 if self.provider == "apihz" else 1.0
        self.minimum_interval_seconds = max(
            float(
                default_interval
                if minimum_interval_seconds is None
                else minimum_interval_seconds
            ),
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
            tuple[str, int, str],
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
        key: tuple[str, int, str],
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
    def _normalize_nominatim_results(
        payload: Any,
    ) -> tuple[dict[str, Any], ...]:
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

    @classmethod
    def _normalize_apihz_result(
        cls,
        payload: Any,
        query: str,
        coordinate_system: str,
    ) -> tuple[dict[str, Any], ...]:
        if not isinstance(payload, dict):
            raise ClassCubeGeocoderError("国内模糊地址搜索返回了无效数据")
        try:
            code = int(payload.get("code"))
        except (TypeError, ValueError):
            code = 0
        if code != 200:
            detail = cls._text(payload.get("msg"))
            normalized_detail = detail.casefold()
            credential_error = any(token in normalized_detail for token in (
                "key", "秘钥", "密钥", "id参数", "id 参数", "用户id",
            ))
            raise ClassCubeGeocoderError(
                detail or "国内模糊地址搜索失败，请稍后重试",
                retryable=not credential_error,
            )
        try:
            latitude = float(payload.get("lat"))
            longitude = float(payload.get("lng"))
        except (TypeError, ValueError) as exc:
            raise ClassCubeGeocoderError(
                "国内模糊地址搜索未返回有效坐标"
            ) from exc
        if (
            not math.isfinite(latitude)
            or not math.isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise ClassCubeGeocoderError(
                "国内模糊地址搜索未返回有效坐标"
            )
        try:
            score = max(0.0, min(float(payload.get("score")), 100.0))
        except (TypeError, ValueError):
            score = None
        level = cls._text(payload.get("level")) or "地点"
        result = {
            "id": f"apihz:{latitude:.7f}:{longitude:.7f}",
            "name": query,
            "address": query,
            "latitude": latitude,
            "longitude": longitude,
            "category": level,
            "type": level,
            "province": "",
            "city": "",
            "district": "",
            "provider": "apihz",
            "coordinate_system": coordinate_system,
            "level": level,
        }
        if score is not None:
            result["score"] = round(score, 1)
        return (result,)

    def _request_apihz(
        self,
        query: str,
    ) -> tuple[dict[str, Any], ...]:
        if not self.account_id or not self.api_key:
            raise ClassCubeGeocoderError(
                "尚未配置接口盒子用户 ID 或通讯密钥，无法使用国内模糊地址搜索",
                retryable=False,
            )
        response = self._session.post(
            f"{self.base_url}/jwjuhe.php",
            data={
                "id": self.account_id,
                "key": self.api_key,
                "address": query,
            },
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            timeout=10,
        )
        response.raise_for_status()
        return self._normalize_apihz_result(
            response.json(),
            query,
            self.coordinate_system,
        )

    @staticmethod
    def _text(value: Any) -> str:
        if isinstance(value, list):
            return ""
        return str(value or "").strip()

    @classmethod
    def _normalize_amap_results(
        cls,
        payload: Any,
    ) -> tuple[dict[str, Any], ...]:
        if not isinstance(payload, dict):
            raise ClassCubeGeocoderError("国内地址搜索服务返回了无效数据")
        if str(payload.get("status") or "") != "1":
            info = cls._text(payload.get("info"))
            info_code = cls._text(payload.get("infocode"))
            message = "国内地址搜索服务暂时不可用"
            if info_code in {"10001", "10002", "10003", "10007"}:
                message = "高德 Web 服务 Key 无效或无搜索权限"
            elif info_code in {
                "10004", "10005", "10009", "10010", "10019", "10020",
                "10021",
            }:
                message = "高德地址搜索调用额度或频率已受限"
            elif info:
                message = f"国内地址搜索失败：{info}"
            raise ClassCubeGeocoderError(message, retryable=False)

        rows = payload.get("pois")
        if not isinstance(rows, list):
            raise ClassCubeGeocoderError("国内地址搜索服务返回了无效数据")
        normalized: list[dict[str, Any]] = []
        seen: set[tuple[float, float, str]] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            location = cls._text(row.get("location"))
            try:
                longitude_text, latitude_text = location.split(",", 1)
                latitude = float(latitude_text)
                longitude = float(longitude_text)
            except (TypeError, ValueError):
                continue
            if (
                not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                continue
            name = cls._text(row.get("name")) or "搜索结果"
            address = cls._text(row.get("address"))
            province = cls._text(row.get("pname"))
            city = cls._text(row.get("cityname"))
            district = cls._text(row.get("adname"))
            address_parts = []
            for part in (province, city, district, address):
                if part and (not address_parts or part != address_parts[-1]):
                    address_parts.append(part)
            full_address = "".join(address_parts) or name
            dedupe_key = (
                round(latitude, 7),
                round(longitude, 7),
                name.casefold(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append({
                "id": f"amap:{cls._text(row.get('id')) or len(normalized)}",
                "name": name,
                "address": full_address,
                "latitude": latitude,
                "longitude": longitude,
                "category": cls._text(row.get("type")),
                "type": cls._text(row.get("typecode")),
                "province": province,
                "city": city,
                "district": district,
                "provider": "amap",
                "coordinate_system": "GCJ02",
            })
        return tuple(normalized)

    def _request_amap(
        self,
        query: str,
        limit: int,
    ) -> tuple[dict[str, Any], ...]:
        if not self.api_key:
            raise ClassCubeGeocoderError(
                "尚未配置高德 Web 服务 Key，无法使用国内地址搜索",
                retryable=False,
            )
        response = self._session.get(
            f"{self.base_url}/text",
            params={
                "key": self.api_key,
                "keywords": query,
                "offset": limit,
                "page": 1,
                "extensions": "all",
                "output": "JSON",
            },
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            timeout=10,
        )
        response.raise_for_status()
        return self._normalize_amap_results(response.json())

    @classmethod
    def _normalize_tencent_results(
        cls,
        payload: Any,
    ) -> tuple[dict[str, Any], ...]:
        if not isinstance(payload, dict):
            raise ClassCubeGeocoderError("腾讯地点搜索返回了无效数据")
        try:
            status = int(payload.get("status"))
        except (TypeError, ValueError):
            status = -1
        if status != 0:
            detail = cls._text(payload.get("message"))
            normalized_detail = detail.casefold()
            if status == 121 or any(
                token in normalized_detail
                for token in ("每日调用量", "daily quota", "日配额")
            ):
                message = "腾讯地址搜索今日调用额度已用完，请提升配额或更换可用 Key"
                retryable = False
            elif status in {120, 122} or any(
                token in normalized_detail
                for token in ("quota", "qps", "配额", "频率", "限流", "调用量")
            ):
                message = "腾讯地址搜索调用频率或配额受限，请稍后重试"
                retryable = True
            elif status in {110, 111, 112, 114, 115, 116, 160} or any(
                token in normalized_detail
                for token in ("key", "鉴权", "权限", "签名", "授权")
            ):
                message = "腾讯位置服务 Key 无效、未授权或未开通 WebService API"
                retryable = False
            else:
                message = (
                    f"腾讯地点搜索失败：{detail}"
                    if detail else "腾讯地点搜索暂时不可用"
                )
                retryable = status >= 300 or status < 0
            raise ClassCubeGeocoderError(message, retryable=retryable)

        rows = payload.get("data")
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            raise ClassCubeGeocoderError("腾讯地点搜索返回了无效数据")

        normalized: list[dict[str, Any]] = []
        seen: set[tuple[float, float, str]] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            location = row.get("location")
            if not isinstance(location, dict):
                continue
            try:
                latitude = float(location.get("lat"))
                longitude = float(location.get("lng"))
            except (TypeError, ValueError):
                continue
            if (
                not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                continue

            name = cls._text(row.get("title")) or "搜索结果"
            address = cls._text(row.get("address"))
            ad_info = row.get("ad_info")
            if not isinstance(ad_info, dict):
                ad_info = {}
            province = cls._text(ad_info.get("province"))
            city = cls._text(ad_info.get("city"))
            district = cls._text(ad_info.get("district"))
            full_address = address
            if not full_address:
                full_address = "".join(dict.fromkeys(
                    part for part in (province, city, district) if part
                )) or name

            dedupe_key = (
                round(latitude, 7),
                round(longitude, 7),
                name.casefold(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            item = {
                "id": f"tencent:{cls._text(row.get('id')) or len(normalized)}",
                "name": name,
                "address": full_address,
                "latitude": latitude,
                "longitude": longitude,
                "category": cls._text(row.get("category")),
                "type": (
                    cls._text(row.get("type"))
                    or cls._text(row.get("category"))
                ),
                "province": province,
                "city": city,
                "district": district,
                "provider": "tencent",
                "coordinate_system": "GCJ02",
            }
            try:
                distance = float(row.get("_distance"))
            except (TypeError, ValueError):
                distance = None
            if distance is not None and math.isfinite(distance) and distance >= 0:
                item["distance"] = round(distance, 1)
            normalized.append(item)
        return tuple(normalized)

    def _request_tencent(
        self,
        query: str,
        limit: int,
        region: str,
    ) -> tuple[dict[str, Any], ...]:
        if not self.api_key:
            raise ClassCubeGeocoderError(
                "尚未配置腾讯位置服务 Key，无法使用腾讯地点搜索",
                retryable=False,
            )
        params: dict[str, Any] = {
            "key": self.api_key,
            "keyword": query,
            "page_size": limit,
            "output": "json",
        }
        if region:
            params["region"] = region
            params["region_fix"] = 1
        response = self._session.get(
            f"{self.base_url}/ws/place/v1/suggestion",
            params=params,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            timeout=10,
        )
        response.raise_for_status()
        return self._normalize_tencent_results(response.json())

    def _request_nominatim(
        self,
        query: str,
        limit: int,
    ) -> tuple[dict[str, Any], ...]:
        response = self._session.get(
            f"{self.base_url}/search",
            params={
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": limit,
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
        return self._normalize_nominatim_results(response.json())

    def search(
        self,
        query: str,
        limit: int = 5,
        *,
        region: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_query = " ".join(str(query or "").strip().split())
        if len(normalized_query) < 2:
            raise ValueError("请至少输入 2 个字符搜索地址")
        normalized_limit = min(max(int(limit), 1), 8)
        normalized_region = "".join(str(region or "").strip().split())
        key = (
            self._query_key(normalized_query),
            normalized_limit,
            normalized_region.casefold(),
        )

        with self._lock:
            now = self._clock()
            cached = self._cached(key, now)
            if cached is not None:
                return cached

            if (
                self.provider in {"apihz", "tencent"}
                and not self.api_key
            ):
                raise ClassCubeGeocoderError(
                    (
                        "尚未配置腾讯位置服务 Key，无法使用腾讯地点搜索"
                        if self.provider == "tencent"
                        else "尚未配置接口盒子通讯密钥，无法使用国内模糊地址搜索"
                    ),
                    retryable=False,
                )
            if self.provider == "apihz" and not self.account_id:
                raise ClassCubeGeocoderError(
                    "尚未配置接口盒子用户 ID，无法使用国内模糊地址搜索",
                    retryable=False,
                )

            self._wait_for_rate_slot()

            try:
                if self.provider == "apihz":
                    results = self._request_apihz(normalized_query)
                elif self.provider == "tencent":
                    results = self._request_tencent(
                        normalized_query,
                        normalized_limit,
                        normalized_region,
                    )
                elif self.provider == "amap":
                    results = self._request_amap(
                        normalized_query,
                        normalized_limit,
                    )
                else:
                    results = self._request_nominatim(
                        normalized_query,
                        normalized_limit,
                    )
            except ClassCubeGeocoderError:
                raise
            except (
                requests.RequestException,
                ValueError,
                TypeError,
            ) as exc:
                raise ClassCubeGeocoderError(
                    "国内地址搜索服务暂时不可用"
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
