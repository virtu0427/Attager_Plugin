from fastapi import FastAPI, HTTPException, Request
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import os
import uvicorn
import uuid
import json
import hashlib
import secrets
import copy

# 샘플용 비밀키 (실제 서비스에서는 .pem 또는 환경변수 사용)
SECRET_KEY = os.environ.get("JWS_SECRET", "mysecretkey")
ALGORITHM = "HS256"

app = FastAPI()

def _canonical_bytes(obj) -> bytes:
    """JCS 유사 정준화(JSON sort+no spaces)로 직렬화한 바이트."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha256_prefixed(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _card_material_for_hash(card: dict) -> dict:
    """해시 계산 시 시그니처 필드 제거한 카드 사본을 반환."""
    material = copy.deepcopy(card)
    if isinstance(material, dict):
        material.pop("signatures", None)
    return material


# JWS 생성 (JWT 형태로) — 표준 페이로드 스키마 구성
@app.post("/sign")
async def sign_payload(request: Request):
    body = await request.json()

    # 입력 파라미터 (기본값 포함)
    iss = body.get("iss") or os.environ.get("JWS_ISS", "ans-registry.example")
    sub = body.get("sub")  # 필수
    version_id = body.get("version_id") if isinstance(body.get("version_id"), int) else 1
    policy_version = body.get("policy_version") or os.environ.get("POLICY_VERSION", "registry.policy.v3")
    ttl_seconds = body.get("exp_seconds") if isinstance(body.get("exp_seconds"), int) and body.get("exp_seconds") > 0 else 600

    # card_hash 계산: card 객체가 오면 정준화 → SHA-256, 없으면 body.card_hash 사용
    card_hash = None
    if isinstance(body.get("card"), dict):
        material = _card_material_for_hash(body["card"])  # signatures 제외
        card_hash = _sha256_prefixed(_canonical_bytes(material))
    elif isinstance(body.get("card_hash"), str):
        card_hash = body.get("card_hash")

    if not isinstance(sub, str) or not sub.strip():
        raise HTTPException(status_code=422, detail="'sub' is required")
    if not isinstance(card_hash, str) or not card_hash:
        raise HTTPException(status_code=422, detail="'card' or 'card_hash' is required")

    now = datetime.now(timezone.utc)
    iat = int(now.timestamp())
    exp = int((now + timedelta(seconds=ttl_seconds)).timestamp())
    jti = str(uuid.uuid4())

    # etag 기본 생성: 약한 ETag W/"<version>-<short>"
    short = secrets.token_hex(3)
    etag = body.get("etag") or f"W/\"{version_id}-{short}\""

    payload = {
        "iss": iss,
        "sub": sub,
        "iat": iat,
        "exp": exp,
        "jti": jti,
        "card_hash": card_hash,
        "version_id": version_id,
        "etag": etag,
        "policy_version": policy_version,
    }

    # 헤더에 kid 포함(요청 body 또는 환경변수)
    kid = body.get("kid") or os.environ.get("JWS_KID", "registry-hs256-key-1")
    headers = {"kid": kid}

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM, headers=headers)
    return {"jws": token, "payload": payload}

# JWS 검증 (+ 선택적으로 에이전트 카드/해시 일치 여부 확인)
@app.post("/verify")
async def verify_token(request: Request):
    data = await request.json()
    token = data.get("jws")
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=422, detail="'jws' is required")
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=400, detail=str(e))

    expected_hash = decoded.get("card_hash")

    # 클라이언트가 카드 또는 카드 해시를 함께 보내면, 토큰 내 card_hash 와 일치 여부를 검증
    provided_hash = None
    if isinstance(data.get("card"), dict):
        material = _card_material_for_hash(data["card"])  # signatures 제외
        provided_hash = _sha256_prefixed(_canonical_bytes(material))
    elif isinstance(data.get("card_hash"), str):
        provided_hash = data.get("card_hash")

    hash_verified = False
    if provided_hash is not None:
        if not isinstance(expected_hash, str) or not expected_hash:
            raise HTTPException(status_code=400, detail={
                "code": "TOKEN_MISSING_CARD_HASH",
                "message": "card_hash claim missing in token",
            })
        if provided_hash != expected_hash:
            raise HTTPException(status_code=400, detail={
                "code": "CARD_HASH_MISMATCH",
                "message": "agent card hash does not match token",
                "expected": expected_hash,
                "actual": provided_hash,
            })
        hash_verified = True

    return {"valid": True, "payload": decoded, "hash_verified": hash_verified}


if __name__ == "__main__":
    # 환경변수 PORT로 오버라이드 가능, 기본 8001
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=True)
