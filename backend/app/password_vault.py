"""Encrypted copies of admin-set passwords, used only for the admin
account-export feature.

System login passwords are stored as bcrypt hashes (irreversible). To allow
admins to export freshly created/reset credentials, we keep an AES-GCM
encrypted copy of the password set by an admin. The copy is cleared when the
user changes their own password.

The AES key comes from the EXPORT_SECRET_KEY env var (base64 or hex, 16/24/32
bytes). When unset, a random key is generated once and persisted to
``export_secret.key`` next to settings.json. Losing that file makes existing
copies undecryptable (they will simply export as "未保存").
"""

import base64
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import APP_DIR

KEY_FILE = Path(os.getenv("EXPORT_SECRET_KEY_FILE", str(APP_DIR / "export_secret.key")))

_KEY_CACHE: bytes | None = None


class PasswordVaultError(RuntimeError):
    pass


def _load_or_create_key() -> bytes:
    global _KEY_CACHE
    if _KEY_CACHE:
        return _KEY_CACHE

    env_key = os.getenv("EXPORT_SECRET_KEY", "").strip()
    if env_key:
        _KEY_CACHE = _parse_key(env_key)
        return _KEY_CACHE

    try:
        if KEY_FILE.exists():
            raw = KEY_FILE.read_text(encoding="utf-8").strip()
            if raw:
                _KEY_CACHE = _parse_key(raw)
                return _KEY_CACHE
        key = AESGCM.generate_key(bit_length=256)
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(base64.b64encode(key).decode("ascii"), encoding="utf-8")
        try:
            os.chmod(KEY_FILE, 0o600)
        except OSError:
            pass
        _KEY_CACHE = key
        return _KEY_CACHE
    except OSError as exc:
        raise PasswordVaultError(f"导出密钥文件读写失败：{exc}") from exc


def _parse_key(value: str) -> bytes:
    text = value.strip()
    try:
        key = base64.b64decode(text, validate=True)
    except Exception:
        key = b""
    if len(key) not in (16, 24, 32):
        cleaned = text.removeprefix("0x").replace(" ", "")
        try:
            key = bytes.fromhex(cleaned)
        except ValueError:
            key = b""
    if len(key) not in (16, 24, 32):
        raise PasswordVaultError("EXPORT_SECRET_KEY 格式无效：需要 16/24/32 字节的 base64 或 hex")
    return key


def encrypt_password(plain: str) -> bytes | None:
    """Encrypt a password copy; returns None for empty input."""
    if not plain:
        return None
    key = _load_or_create_key()
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(key).encrypt(nonce, plain.encode("utf-8"), None)


def decrypt_password(blob: bytes | None) -> str | None:
    """Decrypt a password copy; returns None when missing or undecryptable."""
    if not blob:
        return None
    try:
        key = _load_or_create_key()
        nonce, payload = bytes(blob[:12]), bytes(blob[12:])
        return AESGCM(key).decrypt(nonce, payload, None).decode("utf-8")
    except Exception:
        return None
