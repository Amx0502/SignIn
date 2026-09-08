import mimetypes
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import config


TONGJI_FIELDS = """_id title content createdAt updatedAt isClosed isRepeat startTime endTime repeatStartDate repeatEndDate noName nameLabel groupLabelName fixedNo showNameList nameList{name no groupName noLabel} needInfo needLocation needSubmitLocation openLocationInfo needWifi wifiInfos{ssid bssid} locations{name longtitude latitude distance} locationInfos{name longtitude latitude} needImages imageIsRequired needVideo videoIsRequired needAudio audioIsRequired needSignature requiredFields needOptions optionFields{title isImage isMulti required maxSelect options} infoForms{id isRemove type title desc order required options maxSelect minSelect textareaRow limitCharGt limitCharlt mediaSourceType showConditions{optionId optionIdxs optionLogic} showConditionsLogic} allowSubmitTimeRules{_id startTime endTime}"""


class MiaoyingRemoteError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class MiaoyingClient:
    def __init__(self):
        self.qr_url = config.MIAOYING_QR_API_URL
        self.graphql_url = config.MIAOYING_GRAPHQL_URL
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SignIn-Miaoying/1.0", "Accept": "application/json"})

    def close(self):
        self.session.close()

    def create_qr(self) -> dict:
        last_error = None
        qr_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Origin": "https://miaoying.hui51.cn",
            "Referer": "https://miaoying.hui51.cn/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
        }
        for _ in range(2):
            try:
                # 秒应当前接口要求请求具有 JSON 语义；完全空的 POST 偶发会被
                # 上游网关挂起，最终被本系统转换成 502。
                # 创建与轮询复用同一连接，减少首次轮询重复 TLS 握手。
                response = self.session.post(
                    f"{self.qr_url}/qrcodeLogin",
                    headers=qr_headers,
                    json={},
                    timeout=(4, 8),
                )
                return self._json(response, "创建秒应二维码")
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
        raise MiaoyingRemoteError("连接秒应二维码服务超时，请稍后重试") from last_error

    def poll_qr(self, scene_id: str) -> dict | None:
        try:
            response = self.session.get(
                f"{self.qr_url}/getUserWithSceneId/{scene_id}",
                timeout=(5, 12),
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise MiaoyingRemoteError("连接秒应扫码状态服务超时，请稍后重试") from exc

        # 该接口以 HTTP 400 表示二维码仍在等待扫码，而不是请求失败。
        # 仅识别这个明确的业务消息，其他 400 仍交给统一错误处理。
        if response.status_code == 400:
            try:
                waiting_payload = response.json()
            except ValueError:
                waiting_payload = {}
            waiting_message = str(waiting_payload.get("message") or "")
            if "等待用户扫码" in waiting_message:
                return None

        payload = self._json(response, "查询扫码状态")
        data = payload.get("data")
        return data if isinstance(data, dict) and data.get("token") else None

    def graphql(
        self,
        token: str,
        operation: str,
        query: str,
        variables: dict,
        *,
        retryable: bool = True,
    ) -> dict:
        attempts = 3 if retryable else 1
        last_error = None
        response = None
        for _ in range(attempts):
            try:
                # 秒应网关偶尔会留下不可复用的 keep-alive 连接。GraphQL
                # 查询使用短连接并允许重试，可避免连接池中的失效连接直接
                # 变成系统 500；写操作不重试，防止响应超时后重复提交。
                response = requests.post(
                    self.graphql_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "SignIn-Miaoying/1.0",
                    },
                    json={"operationName": operation, "query": query, "variables": variables},
                    timeout=(5, 15),
                )
                break
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
        if response is None:
            action = "提交签到" if not retryable else "查询"
            suffix = "；结果可能已被上游接收，请先刷新签到记录再决定是否重试" if not retryable else "，请稍后重试"
            raise MiaoyingRemoteError(
                f"连接秒应{action}服务超时{suffix}", retryable=retryable
            ) from last_error
        payload = self._json(response, f"秒应 {operation}")
        if payload.get("errors"):
            errors = payload["errors"]
            first_error = errors[0] if isinstance(errors, list) else errors
            message = first_error.get("message", "GraphQL 请求失败") if isinstance(first_error, dict) else str(first_error)
            raise MiaoyingRemoteError(message)
        return payload.get("data") or {}

    def get_me(self, token: str) -> dict:
        data = self.graphql(token, "getMe", "query getMe { me { _id nickname role avatar } }", {})
        return data.get("me") or {}

    def get_tongjis(self, token: str, uid: str, limit: int = 50) -> list[dict]:
        query = f"""query getTongjis($uid:String!,$limit:String,$skip:String){{tongjis(sort:\"-createdAt\",createdBy:$uid,limit:$limit,skip:$skip){{isRemove {TONGJI_FIELDS}}}}}"""
        rows = self.graphql(token, "getTongjis", query, {"uid": uid, "limit": str(limit), "skip": "0"}).get("tongjis") or []
        return [row for row in rows if not row.get("isRemove")]

    def get_tongji(self, token: str, remote_id: str) -> dict:
        query = f"""query getTongji($_id:String){{tongji(_id:$_id){{{TONGJI_FIELDS}}}}}"""
        return self.graphql(token, "getTongji", query, {"_id": remote_id}).get("tongji") or {}

    def get_records(self, token: str, uid: str, limit: int = 100) -> list[dict]:
        query = """query getAllBaomingRecords($uid:String,$limit:String){baomings(userId:$uid,sort:\"-createdAt\",limit:$limit){_id tongjiId createdAt infoKey infoVal}}"""
        return self.graphql(token, "getAllBaomingRecords", query, {"uid": uid, "limit": str(limit)}).get("baomings") or []

    def get_sync_context(
        self,
        token: str,
        uid: str,
        form_limit: int = 50,
        record_limit: int = 100,
        known_remote_ids: list[str] | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """一次取得列表、记录及已缓存项目详情，避免同步阶段重复往返。"""
        cached_ids = list(dict.fromkeys(
            str(value) for value in (known_remote_ids or []) if value
        ))[:20]
        definitions = [
            "$uid:String!",
            "$formLimit:String",
            "$recordLimit:String",
            "$skip:String",
        ]
        definitions.extend(
            f"$cached{index}:String" for index in range(len(cached_ids))
        )
        cached_selections = " ".join(
            f"cached{index}:tongji(_id:$cached{index}){{{TONGJI_FIELDS}}}"
            for index in range(len(cached_ids))
        )
        query = (
            f"query getSyncContext({','.join(definitions)}){{"
            f"tongjis(sort:\"-createdAt\",createdBy:$uid,limit:$formLimit,skip:$skip)"
            f"{{isRemove {TONGJI_FIELDS}}} "
            f"baomings(userId:$uid,sort:\"-createdAt\",limit:$recordLimit)"
            f"{{_id tongjiId createdAt}} {cached_selections}}}"
        )
        variables = {
            "uid": uid,
            "formLimit": str(form_limit),
            "recordLimit": str(record_limit),
            "skip": "0",
        }
        variables.update(
            {f"cached{index}": remote_id for index, remote_id in enumerate(cached_ids)}
        )
        data = self.graphql(
            token,
            "getSyncContext",
            query,
            variables,
        )
        forms_by_id = {
            str(row.get("_id")): row
            for row in (data.get("tongjis") or [])
            if row.get("_id") and not row.get("isRemove")
        }
        for index in range(len(cached_ids)):
            item = data.get(f"cached{index}")
            if isinstance(item, dict) and item.get("_id"):
                forms_by_id[str(item["_id"])] = item
        return list(forms_by_id.values()), data.get("baomings") or []

    def get_tongjis_by_ids(
        self,
        token: str,
        remote_ids: list[str],
        batch_size: int = 25,
    ) -> list[dict]:
        """通过 GraphQL aliases 批量补全不在创建列表中的历史项目。"""
        unique_ids = list(dict.fromkeys(str(value) for value in remote_ids if value))
        rows: list[dict] = []
        for offset in range(0, len(unique_ids), batch_size):
            batch = unique_ids[offset:offset + batch_size]
            definitions = ",".join(f"$id{index}:String" for index in range(len(batch)))
            selections = " ".join(
                f"item{index}:tongji(_id:$id{index}){{{TONGJI_FIELDS}}}"
                for index in range(len(batch))
            )
            query = f"query getTongjisByIds({definitions}){{{selections}}}"
            variables = {f"id{index}": remote_id for index, remote_id in enumerate(batch)}
            data = self.graphql(token, "getTongjisByIds", query, variables)
            rows.extend(
                item for item in data.values()
                if isinstance(item, dict) and item.get("_id")
            )
        return rows

    def get_checkin_context(
        self, token: str, remote_id: str, uid: str, limit: int = 100
    ) -> tuple[dict, list[dict]]:
        """一次请求取得项目详情与用户记录，减少签到前的网络往返。"""
        query = f"""query getCheckinContext($_id:String,$uid:String,$limit:String){{tongji(_id:$_id){{{TONGJI_FIELDS}}} baomings(userId:$uid,sort:\"-createdAt\",limit:$limit){{_id tongjiId createdAt}}}}"""
        data = self.graphql(
            token,
            "getCheckinContext",
            query,
            {"_id": remote_id, "uid": uid, "limit": str(limit)},
        )
        return data.get("tongji") or {}, data.get("baomings") or []

    def upload_image(
        self,
        token: str,
        remote_user_id: str,
        content: bytes,
        original_name: str,
        content_type: str = "",
    ) -> dict:
        """Upload one image with Miaoying's signed OSS workflow."""
        # The upstream endpoint rejects a zero-length POST. Browser FormData
        # sends an empty multipart body containing only the closing boundary.
        boundary = f"----SignInMiaoying{uuid.uuid4().hex}"
        try:
            sign_response = requests.post(
                "https://miaoying.hui51.cn/api/file/getOssSign",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Origin": "https://miaoying.hui51.cn",
                    "Referer": "https://miaoying.hui51.cn/",
                    "User-Agent": "SignIn-Miaoying/1.0",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
                data=f"--{boundary}--\r\n".encode(),
                timeout=(5, 15),
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise MiaoyingRemoteError("获取秒应图片上传凭证超时，请稍后重试") from exc
        sign_payload = self._json(sign_response, "获取秒应图片上传凭证")
        credential = sign_payload.get("data") or {}
        if not isinstance(credential, dict):
            raise MiaoyingRemoteError("秒应图片上传凭证格式异常")

        upload_url = str(credential.get("uploadImageUrl") or "").strip()
        parsed = urlparse(upload_url)
        allowed_hosts = {
            "oss2.hui51.cn",
            "oss.hui51.cn",
            "hui51.oss-cn-beijing.aliyuncs.com",
        }
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
            raise MiaoyingRemoteError("秒应返回了不受信任的图片上传地址")

        maximum_mb = credential.get("maxSize")
        try:
            if maximum_mb and len(content) > float(maximum_mb) * 1024 * 1024:
                raise MiaoyingRemoteError(
                    f"图片大小不能超过 {maximum_mb} MB", retryable=False
                )
        except (TypeError, ValueError):
            pass

        suffix = Path(original_name or "image.jpg").suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = mimetypes.guess_extension(content_type or "") or ".jpg"
        object_name = f"{remote_user_id}_{uuid.uuid4().hex}{suffix}"
        object_key = f"uploads/{object_name}"
        fields = {"key": object_key, "success_action_status": "200"}
        for name in ("policy", "OSSAccessKeyId", "signature"):
            value = credential.get(name)
            if not value:
                raise MiaoyingRemoteError("秒应图片上传凭证不完整")
            fields[name] = str(value)

        try:
            response = requests.post(
                upload_url,
                data=fields,
                files={
                    "file": (
                        original_name or object_name,
                        content,
                        content_type
                        or mimetypes.guess_type(original_name)[0]
                        or "image/jpeg",
                    )
                },
                timeout=(5, 30),
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise MiaoyingRemoteError("上传秒应图片超时，请稍后重试") from exc
        if response.status_code not in (200, 201, 204):
            raise MiaoyingRemoteError(
                f"上传秒应图片失败（OSS HTTP {response.status_code}）"
            )
        return {
            "name": object_name,
            "url": f"https://oss2.hui51.cn/encode/uploads/{object_name}",
        }

    def submit(self, token: str, payload: dict) -> str:
        query = """mutation createBaomingByInput($input:createBaomingInput!){createBaomingByInput(input:$input){_id}}"""
        result = self.graphql(
            token,
            "createBaomingByInput",
            query,
            {"input": payload},
            retryable=False,
        ).get("createBaomingByInput") or {}
        remote_id = str(result.get("_id") or "")
        if not remote_id:
            raise MiaoyingRemoteError("秒应未返回报名记录 ID，未确认签到成功")
        return remote_id

    @staticmethod
    def _json(response: requests.Response, action: str) -> dict:
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            message = ""
            try:
                error_payload = response.json()
                if isinstance(error_payload, dict):
                    message = str(error_payload.get("message") or error_payload.get("error") or "").strip()
            except ValueError:
                pass
            detail = f"：{message}" if message else ""
            raise MiaoyingRemoteError(f"{action}失败（上游 HTTP {response.status_code}）{detail}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise MiaoyingRemoteError(f"{action}返回格式异常") from exc
        if not isinstance(payload, dict):
            raise MiaoyingRemoteError(f"{action}返回格式异常")
        if payload.get("statusCode") not in (None, 200):
            raise MiaoyingRemoteError(str(payload.get("message") or f"{action}失败"))
        return payload
