import json
import sys

sys.path.insert(0, r"C:\Users\ASUS\Desktop\SignIn\backend")

from sqlalchemy import create_engine, inspect, text

from app.auth_migrations import migrate_auth_schema
from app.database_config import load_database_config

result = {}
try:
    settings = load_database_config()
    engine = create_engine(settings.url(), pool_pre_ping=True)
    with engine.connect() as conn:
        before = [c["name"] for c in inspect(conn).get_columns("users")]
        result["before_has_column"] = "initial_password_enc" in before
        versions_before = [
            row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))
        ]
    result["versions_before"] = sorted(versions_before)

    applied = migrate_auth_schema(engine)
    result["newly_applied"] = applied

    with engine.connect() as conn:
        after = [c["name"] for c in inspect(conn).get_columns("users")]
        result["after_has_column"] = "initial_password_enc" in after
        versions_after = [
            row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))
        ]
    result["versions_after"] = sorted(versions_after)
    result["ok"] = True
except Exception as exc:  # noqa: BLE001
    result["ok"] = False
    result["error"] = f"{type(exc).__name__}: {exc}"

with open(r"C:\Users\ASUS\Desktop\SignIn\backend\migrate_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
