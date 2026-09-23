from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from jose import jwt

from backend.core.config import settings

password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)

def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes = int(settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({'exp' : expire, 'iat': datetime.now(timezone.utc)})

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms = [settings.ALGORITHM])