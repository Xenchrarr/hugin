from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import jwt

from src.models.orchestrator.User import User

log = logging.getLogger(__name__)

JWT_SECRET: str = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

SERVICE_KEY: str = os.environ.get("SERVICE_KEY", "")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _secret_fingerprint() -> str:
    return hashlib.md5(JWT_SECRET.encode()).hexdigest()[:8]


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "is_admin": user.is_admin,
        "exp": datetime.now(tz=timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    log.debug("create_token: secret fingerprint=%s", _secret_fingerprint())
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    log.debug("decode_token: secret fingerprint=%s", _secret_fingerprint())
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        log.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        log.warning("JWT token invalid: %s: %s", type(e).__name__, e)
        return None
