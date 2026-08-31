import json
import os
from pathlib import Path
import tempfile

APP_DIR = Path(__file__).resolve().parent.parent
LEGACY_ACCOUNTS_FILE = APP_DIR / "accounts.json"
LEGACY_USERS_FILE = APP_DIR / "users.json"
LEGACY_SESSIONS_FILE = APP_DIR / "sessions.json"
SETTINGS_FILE = APP_DIR / "settings.json"
LOG_DIR = APP_DIR / "logs"
UPLOAD_DIR = APP_DIR / "uploads"
CLASS_CUBE_UPLOAD_DIR = UPLOAD_DIR / "class-cube"

DEFAULT_REFRESH_TIMES = ["07:30:00", "11:30:00", "14:00:00", "17:00:00", "18:30:00"]
DEFAULT_WEBHOOK_URL = ""

CLASS_CUBE_GEOCODER_PROVIDER = os.getenv(
    "CLASS_CUBE_GEOCODER_PROVIDER",
    "amap",
)
CLASS_CUBE_GEOCODER_URL = os.getenv(
    "CLASS_CUBE_GEOCODER_URL",
    "https://restapi.amap.com/v3/place",
)
CLASS_CUBE_GEOCODER_KEY = os.getenv(
    "CLASS_CUBE_GEOCODER_KEY",
    "",
)
CLASS_CUBE_GEOCODER_USER_AGENT = os.getenv(
    "CLASS_CUBE_GEOCODER_USER_AGENT",
    "SignIn-ClassCube/1.0",
)
CLASS_CUBE_GEOCODER_RATE_FILE = os.getenv(
    "CLASS_CUBE_GEOCODER_RATE_FILE",
    str(Path(tempfile.gettempdir()) / "signin-class-cube-geocoder.rate"),
)
CLASS_CUBE_MAP_LAYERS_JSON = os.getenv(
    "CLASS_CUBE_MAP_LAYERS_JSON",
    "",
)
CLASS_CUBE_SUBMIT_COORDINATE_SYSTEM = os.getenv(
    "CLASS_CUBE_SUBMIT_COORDINATE_SYSTEM",
    "gcj02",
)

_DEFAULT_CLASS_CUBE_MAP_LAYERS = [{
    "id": "amap",
    "name": "国内地图",
    "url": (
        "https://webrd01.is.autonavi.com/appmaptile"
        "?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}"
    ),
    "attribution": (
        '&copy; <a href="https://www.amap.com/" '
        'target="_blank">高德地图</a>'
    ),
    "coordinate_system": "gcj02",
    "max_zoom": 19,
}]


def class_cube_map_layers() -> list[dict]:
    raw_value = str(CLASS_CUBE_MAP_LAYERS_JSON or "").strip()
    if not raw_value:
        return [dict(layer) for layer in _DEFAULT_CLASS_CUBE_MAP_LAYERS]
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return [dict(layer) for layer in _DEFAULT_CLASS_CUBE_MAP_LAYERS]
    if not isinstance(parsed, list):
        return [dict(layer) for layer in _DEFAULT_CLASS_CUBE_MAP_LAYERS]

    layers = []
    for index, layer in enumerate(parsed[:4]):
        if not isinstance(layer, dict):
            continue
        url = str(layer.get("url") or "").strip()
        if not url or "{z}" not in url or "{x}" not in url or "{y}" not in url:
            continue
        try:
            max_zoom = min(max(int(layer.get("max_zoom", 19)), 3), 22)
        except (TypeError, ValueError):
            max_zoom = 19
        layers.append({
            "id": str(layer.get("id") or f"layer-{index + 1}")[:64],
            "name": str(layer.get("name") or f"地图 {index + 1}")[:64],
            "url": url,
            "attribution": str(layer.get("attribution") or "")[:2048],
            "coordinate_system": (
                "gcj02"
                if str(layer.get("coordinate_system") or "").lower() == "gcj02"
                else "wgs84"
            ),
            "max_zoom": max_zoom,
        })
    return layers or [dict(layer) for layer in _DEFAULT_CLASS_CUBE_MAP_LAYERS]


PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA3IbkWjuSaZWr/UtdHFsZ
f9z9pQnPssVYzSVkhRw2pjcbdey9LrHee/63TE7Fr2jm3s+FAkDI1V+r/aJRamg7
vEGOcYluTKPZtU1dUgYoV2YCPyPUL5N3lMxi125ewc9EyLtmFhzD+ErliDxW7EIG
goIG9qIcF1umHyVCZymqhLDiuSyppADolz4wSEJtb8fRowOM/KHibp2AsXI6ZJ1W
ZNsPFHIGB+rbmeYFZuCD+PbpDui8ROiBLYqgVJn0jtR7FYwUNS6Eelw32zCwW7gY
OtiJOhUKeC9uEwxwfNChehPkFBJIi8DGpeVwHB9TTWiB058mZswl2hM1XS6u60ll
bwIDAQAB
-----END PUBLIC KEY-----"""

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 "
        "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
        "MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) "
        "UnifiedPCWindowsWechat(0xf2541b34) XWEB/20079"
    ),
    "xweb_xhr": "1",
    "Accept": "*/*",
    "Referer": "https://servicewechat.com/wxee55405953922c86/791/page-frame.html",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
