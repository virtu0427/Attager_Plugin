# 요청/응답 구조 정의
from typing import List, Union
from pydantic import BaseModel # Pydantic은 데이터 유효성 검사를 위한 라이브러리

TenantValue = Union[str, List[str]]

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None
    tenant: TenantValue | None = None

class User(BaseModel):
    email: str
    tenant: TenantValue

class UserInDB(User):
    hashed_password: str
