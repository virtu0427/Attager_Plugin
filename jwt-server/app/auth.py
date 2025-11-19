from datetime import datetime, timedelta
from typing import Any, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 비밀번호 해시/검증 함수
def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

# JWT 발급
def create_access_token(
    *,
    subject: str,
    tenant: str | list[str],
    additional_claims: Dict[str, Any] | None = None,
) -> str:
    to_encode: Dict[str, Any] = {"sub": subject, "tenant": tenant}
    if additional_claims:
        to_encode.update(additional_claims)

    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# JWT 검증
def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
