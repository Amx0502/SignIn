import json
import sys
import traceback

sys.path.insert(0, r"C:\Users\ASUS\Desktop\SignIn\backend")

result = {}
try:
    from fastapi.testclient import TestClient
    import app.main as main_mod
    from app.auth_database import AuthDatabase
    from app.auth_repository import AuthRepository
    from app.database_config import load_database_config

    db = AuthDatabase(load_database_config())
    db.initialize()
    main_mod.auth_service.set_repository(AuthRepository(db))

    def fake_admin():
        return {"id": 1, "username": "admin", "role": "admin"}

    main_mod.app.dependency_overrides[main_mod.require_admin] = fake_admin

    client = TestClient(main_mod.app)
    resp = client.get("/api/users/export")
    result["status"] = resp.status_code
    result["body_head"] = resp.content[:300].decode("utf-8", "replace")
    result["ok"] = resp.status_code == 200
except Exception as exc:
    result["ok"] = False
    result["error"] = f"{type(exc).__name__}: {exc}"
    result["traceback"] = traceback.format_exc()

with open(r"C:\Users\ASUS\Desktop\SignIn\backend\tc_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
