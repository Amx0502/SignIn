from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = APP_DIR / "accounts.json"
SETTINGS_FILE = APP_DIR / "settings.json"
LOG_DIR = APP_DIR / "logs"
UPLOAD_DIR = APP_DIR / "uploads"

DEFAULT_REFRESH_TIMES = ["07:30:00", "11:30:00", "14:00:00", "17:00:00", "18:30:00"]
DEFAULT_FALLBACK_LOCATION = {
    "latitude": 26.036513,
    "longitude": 119.314487,
    "accuracy": 323,
    "wifi": "",
}

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
