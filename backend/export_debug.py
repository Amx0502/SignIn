import json
import sys
import traceback

sys.path.insert(0, r"C:\Users\ASUS\Desktop\SignIn\backend")

result = {}
try:
    import openpyxl
    result["openpyxl"] = openpyxl.__version__
except Exception:
    result["openpyxl"] = "MISSING"
try:
    import cryptography
    result["cryptography"] = cryptography.__version__
except Exception:
    result["cryptography"] = "MISSING"

try:
    from types import SimpleNamespace
    from app.auth_database import AuthDatabase
    from app.auth_repository import AuthRepository
    from app.database_config import load_database_config
    import app.main as main_mod

    db = AuthDatabase(load_database_config())
    db.initialize()
    main_mod.auth_service.repository = AuthRepository(db)

    resp = main_mod.export_users(
        keyword=None, card_type=None, platform_scope=None, status=None,
        admin=SimpleNamespace(username="debug"),
    )
    result["endpoint_ok"] = True
    result["media_type"] = resp.media_type
    result["body_bytes"] = len(resp.content)
except Exception as exc:
    result["ok"] = False
    result["error"] = f"{type(exc).__name__}: {exc}"
    result["traceback"] = traceback.format_exc()

with open(r"C:\Users\ASUS\Desktop\SignIn\backend\export_debug.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
