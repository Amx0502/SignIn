import requests

from . import config


class MiaoyingRemoteError(RuntimeError):
    pass


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
        for _ in range(2):
            try:
                # 秒应当前接口要求请求具有 JSON 语义；完全空的 POST 偶发会被
                # 上游网关挂起，最终被本系统转换成 502。
                response = self.session.post(
                    f"{self.qr_url}/qrcodeLogin",
                    json={},
                    timeout=(5, 12),
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

    def graphql(self, token: str, operation: str, query: str, variables: dict) -> dict:
        response = self.session.post(
            self.graphql_url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"operationName": operation, "query": query, "variables": variables},
            timeout=20,
        )
        payload = self._json(response, f"秒应 {operation}")
        if payload.get("errors"):
            message = payload["errors"][0].get("message", "GraphQL 请求失败")
            raise MiaoyingRemoteError(message)
        return payload.get("data") or {}

    def get_me(self, token: str) -> dict:
        data = self.graphql(token, "getMe", "query getMe { me { _id nickname role avatar } }", {})
        return data.get("me") or {}

    def get_tongjis(self, token: str, uid: str, limit: int = 50) -> list[dict]:
        query = """query getTongjis($uid:String!,$limit:String,$skip:String){tongjis(sort:\"-createdAt\",createdBy:$uid,limit:$limit,skip:$skip){_id title content createdAt updatedAt isClosed isRepeat repeatStartDate repeatEndDate endTime isRemove needInfo needLocation needSubmitLocation needWifi needImages imageIsRequired needVideo videoIsRequired needAudio audioIsRequired needSignature requiredFields infoForms{type title required} allowSubmitTimeRules{_id startTime endTime}}}"""
        rows = self.graphql(token, "getTongjis", query, {"uid": uid, "limit": str(limit), "skip": "0"}).get("tongjis") or []
        return [row for row in rows if not row.get("isRemove")]

    def get_tongji(self, token: str, remote_id: str) -> dict:
        query = """query getTongji($_id:String){tongji(_id:$_id){_id title content isClosed isRepeat startTime endTime repeatStartDate repeatEndDate needInfo needLocation needSubmitLocation needWifi wifiInfos{ssid bssid} locations{name longtitude latitude distance} locationInfos{name longtitude latitude} needImages imageIsRequired needVideo videoIsRequired needAudio audioIsRequired needSignature requiredFields infoForms{id type title required} allowSubmitTimeRules{_id startTime endTime}}}"""
        return self.graphql(token, "getTongji", query, {"_id": remote_id}).get("tongji") or {}

    def get_records(self, token: str, uid: str, limit: int = 100) -> list[dict]:
        query = """query getAllBaomingRecords($uid:String,$limit:String){baomings(userId:$uid,sort:\"-createdAt\",limit:$limit){_id tongjiId createdAt infoKey infoVal}}"""
        return self.graphql(token, "getAllBaomingRecords", query, {"uid": uid, "limit": str(limit)}).get("baomings") or []

    def submit(self, token: str, payload: dict) -> str:
        query = """mutation createBaomingByInput($input:createBaomingInput!){createBaomingByInput(input:$input){_id}}"""
        result = self.graphql(token, "createBaomingByInput", query, {"input": payload}).get("createBaomingByInput") or {}
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
