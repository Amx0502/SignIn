import hashlib
import uuid
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Tuple

from .models import User, LoginRequest, LoginResponse


USER_DATA_FILE = Path(__file__).resolve().parent.parent / "users.json"
SESSION_DATA_FILE = Path(__file__).resolve().parent.parent / "sessions.json"


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if salt is None:
        salt = uuid.uuid4().hex[:16]
    password_bytes = (password + salt).encode("utf-8")
    hash_result = hashlib.sha256(password_bytes).hexdigest()
    return hash_result, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    computed_hash, _ = hash_password(password, salt)
    return computed_hash == password_hash


def generate_token() -> str:
    return uuid.uuid4().hex


class AuthService:
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, dict] = {}
        self.login_attempts: Dict[str, dict] = {}
        self._load_users()
        self._load_sessions()
        self._cleanup_expired_sessions()

    def _load_users(self):
        if USER_DATA_FILE.exists():
            try:
                data = json.loads(USER_DATA_FILE.read_text(encoding="utf-8"))
                for username, user_data in data.items():
                    if user_data.get('created_at'):
                        try:
                            user_data['created_at'] = datetime.fromisoformat(user_data['created_at'])
                        except ValueError:
                            user_data['created_at'] = datetime.now()
                    if user_data.get('last_login'):
                        try:
                            user_data['last_login'] = datetime.fromisoformat(user_data['last_login'])
                        except ValueError:
                            user_data['last_login'] = None
                    self.users[username] = User(**user_data)
            except Exception:
                pass
        if not self.users:
            default_hash, default_salt = hash_password("admin123")
            self.users["admin"] = User(
                username="admin",
                email="admin@example.com",
                password_hash=f"{default_hash}:{default_salt}",
            )
            self._save_users()

    def _save_users(self):
        data = {}
        for username, user in self.users.items():
            user_dict = user.model_dump()
            if user_dict.get('created_at'):
                user_dict['created_at'] = user_dict['created_at'].isoformat()
            if user_dict.get('last_login'):
                user_dict['last_login'] = user_dict['last_login'].isoformat()
            data[username] = user_dict
        USER_DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_sessions(self):
        if SESSION_DATA_FILE.exists():
            try:
                self.sessions = json.loads(SESSION_DATA_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save_sessions(self):
        SESSION_DATA_FILE.write_text(json.dumps(self.sessions, indent=2), encoding="utf-8")

    def _cleanup_expired_sessions(self):
        now = time.time()
        expired = [token for token, session in self.sessions.items() if session["expires_at"] < now]
        for token in expired:
            del self.sessions[token]
        if expired:
            self._save_sessions()

    def _check_login_attempts(self, username: str, ip_address: str) -> Tuple[bool, Optional[str]]:
        key = f"{username}:{ip_address}"
        now = time.time()
        
        if key not in self.login_attempts:
            self.login_attempts[key] = {"count": 0, "first_attempt": now, "locked_until": 0}
        
        attempt = self.login_attempts[key]
        
        if attempt["locked_until"] > now:
            remaining = int(attempt["locked_until"] - now)
            minutes = remaining // 60
            seconds = remaining % 60
            return False, f"账户已被锁定，请{minutes}分{seconds}秒后再试"
        
        if attempt["count"] >= 5:
            attempt["locked_until"] = now + 300
            self.login_attempts[key] = attempt
            return False, "登录失败次数过多，账户已被锁定5分钟"
        
        return True, None

    def _record_login_attempt(self, username: str, ip_address: str, success: bool):
        key = f"{username}:{ip_address}"
        now = time.time()
        
        if key not in self.login_attempts:
            self.login_attempts[key] = {"count": 0, "first_attempt": now, "locked_until": 0}
        
        attempt = self.login_attempts[key]
        
        if success:
            attempt["count"] = 0
        else:
            attempt["count"] += 1
        
        self.login_attempts[key] = attempt
        
        if attempt["count"] == 0:
            if attempt["first_attempt"] < now - 3600:
                del self.login_attempts[key]

    def login(self, request: LoginRequest, ip_address: str) -> Tuple[bool, dict]:
        allowed, message = self._check_login_attempts(request.username, ip_address)
        if not allowed:
            return False, {"error": message}
        
        user = self.users.get(request.username)
        if not user or not user.is_active:
            self._record_login_attempt(request.username, ip_address, False)
            return False, {"error": "用户名或密码错误"}
        
        try:
            password_hash, salt = user.password_hash.split(":")
        except ValueError:
            self._record_login_attempt(request.username, ip_address, False)
            return False, {"error": "系统错误，请联系管理员"}
        
        if not verify_password(request.password, password_hash, salt):
            self._record_login_attempt(request.username, ip_address, False)
            return False, {"error": "用户名或密码错误"}
        
        self._record_login_attempt(request.username, ip_address, True)
        
        access_token = generate_token()
        expires_in = 86400 if request.remember_me else 3600
        expires_at = time.time() + expires_in
        
        self.sessions[access_token] = {
            "username": user.username,
            "expires_at": expires_at,
            "ip_address": ip_address,
            "created_at": time.time()
        }
        self._save_sessions()
        
        user.last_login = datetime.now()
        self._save_users()
        
        return True, {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_at": datetime.fromtimestamp(expires_at).isoformat(),
            "user": {
                "username": user.username,
                "email": user.email,
                "last_login": user.last_login.isoformat()
            }
        }

    def logout(self, access_token: str):
        if access_token in self.sessions:
            del self.sessions[access_token]
            self._save_sessions()
        return True

    def verify_token(self, access_token: str) -> Optional[User]:
        self._cleanup_expired_sessions()
        
        session = self.sessions.get(access_token)
        if not session:
            return None
        
        if session["expires_at"] < time.time():
            del self.sessions[access_token]
            self._save_sessions()
            return None
        
        return self.users.get(session["username"])