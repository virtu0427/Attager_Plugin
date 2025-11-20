import asyncio
import contextlib
import os
import uuid
from pathlib import Path
from typing import List

import requests
from fastapi import Cookie, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
STATIC_DIR = BASE_DIR / "static"

ORCHESTRATOR_RPC_URL = os.getenv("ORCHESTRATOR_RPC_URL", "http://localhost:10000/").rstrip("/") + "/"
JWT_SERVER_URL = os.getenv("JWT_SERVER_URL", "http://localhost:8011").rstrip("/")
JWT_COOKIE_NAME = os.getenv("JWT_COOKIE_NAME", "access_token")
JWT_COOKIE_MAX_AGE = int(os.getenv("JWT_COOKIE_MAX_AGE", "3600"))
JWT_COOKIE_SECURE = os.getenv("JWT_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}

app = FastAPI(title="Orchestrator Chat Client")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    raw_response: dict


class MetaResponse(BaseModel):
    orchestrator_url: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserProfile(BaseModel):
    email: str
    tenants: List[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserProfile


class SessionResponse(BaseModel):
    authenticated: bool
    user: UserProfile | None = None


@app.get("/", include_in_schema=False)
async def redirect_root() -> RedirectResponse:
    return RedirectResponse(url="/login")


@app.get("/login", response_class=FileResponse)
async def serve_login() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "login.html")


@app.get("/chat", response_class=FileResponse)
async def serve_chat() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "chat.html")


@app.get("/api/meta", response_model=MetaResponse)
async def meta() -> MetaResponse:
    return MetaResponse(orchestrator_url=ORCHESTRATOR_RPC_URL)


def _build_rpc_payload(user_message: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": user_message,
                    }
                ],
            }
        },
    }


def _combine_parts(message_obj: dict) -> str:
    if not isinstance(message_obj, dict):
        return ""

    parts = message_obj.get("parts") or []
    texts: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        candidate = part.get("text")
        if not candidate and isinstance(part.get("root"), dict):
            candidate = part["root"].get("text")
        if candidate:
            texts.append(str(candidate))
    return "\n".join(texts).strip()


def _extract_reply_from_result(result_obj: dict) -> str:
    if not isinstance(result_obj, dict):
        return ""

    candidates: list[dict] = [result_obj]
    latest = result_obj.get("latest_output_message")
    if isinstance(latest, dict):
        candidates.append(latest)

    messages = result_obj.get("messages")
    if isinstance(messages, list):
        candidates.extend(msg for msg in messages if isinstance(msg, dict))

    for candidate in candidates:
        text = _combine_parts(candidate)
        if text:
            return text
    return ""


def _normalize_tenants(candidate: object) -> List[str]:
    if isinstance(candidate, str):
        return [candidate]
    if isinstance(candidate, list):
        return [str(item) for item in candidate if isinstance(item, (str, int, float))]
    return []


def _request_jwt_token(email: str, password: str) -> dict:
    try:
        response = requests.post(
            f"{JWT_SERVER_URL}/token",
            data={"username": email, "password": password},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"JWT 서버 요청 실패: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text
        with contextlib.suppress(ValueError):
            detail = response.json()
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="JWT 서버 응답이 JSON이 아닙니다") from exc


def _request_jwt_profile(token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(
            f"{JWT_SERVER_URL}/users/me",
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"JWT 서버 요청 실패: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text
        with contextlib.suppress(ValueError):
            detail = response.json()
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="JWT 서버 응답이 JSON이 아닙니다") from exc


@app.post("/api/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response) -> LoginResponse:
    token_payload = _request_jwt_token(body.email, body.password)
    access_token = token_payload.get("access_token")
    token_type = token_payload.get("token_type", "bearer")
    if not access_token:
        raise HTTPException(status_code=502, detail="JWT 토큰을 발급받지 못했습니다")

    user_payload = _request_jwt_profile(access_token)
    email = user_payload.get("email")
    tenants = _normalize_tenants(user_payload.get("tenant"))
    if not email:
        raise HTTPException(status_code=502, detail="JWT 서버가 사용자 정보를 반환하지 않았습니다")

    user_profile = UserProfile(email=email, tenants=tenants)

    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=JWT_COOKIE_SECURE,
        samesite="lax",
        max_age=JWT_COOKIE_MAX_AGE,
        path="/",
    )

    return LoginResponse(access_token=access_token, token_type=token_type, user=user_profile)


@app.post("/api/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(
        key=JWT_COOKIE_NAME,
        path="/",
        samesite="lax",
        secure=JWT_COOKIE_SECURE,
        httponly=True,
    )
    return {"message": "logged_out"}


@app.get("/api/session", response_model=SessionResponse)
def session_state(access_token: str | None = Cookie(default=None)) -> SessionResponse:
    token = _extract_token(access_token)
    if not token:
        return SessionResponse(authenticated=False, user=None)

    user_payload = _request_jwt_profile(token)
    email = user_payload.get("email")
    tenants = _normalize_tenants(user_payload.get("tenant"))
    if not email:
        return SessionResponse(authenticated=False, user=None)

    return SessionResponse(authenticated=True, user=UserProfile(email=email, tenants=tenants))


async def _send_rpc(payload: dict, headers: dict | None = None) -> dict:
    try:
        response = await asyncio.to_thread(
            requests.post,
            ORCHESTRATOR_RPC_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as exc:  # pragma: no cover - runtime safety
        raise HTTPException(status_code=502, detail=f"오케스트레이터 요청 실패: {exc}") from exc

    if response.status_code >= 400:
        try:
            error_detail = response.json()
        except ValueError:
            error_detail = response.text
        raise HTTPException(
            status_code=502,
            detail=f"오케스트레이터 응답 오류({response.status_code}): {error_detail}",
        )

    try:
        return response.json()
    except ValueError as exc:  # pragma: no cover - runtime safety
        raise HTTPException(status_code=502, detail="오케스트레이터 응답이 JSON이 아닙니다") from exc


def _extract_token(raw: str | None) -> str:
    if not raw:
        return ""
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return raw.strip()


def _bearer_header(raw_token: str) -> str:
    token = raw_token.strip()
    if not token:
        return ""
    return token if token.lower().startswith("bearer ") else f"Bearer {token}"


@app.post("/api/chat", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    authorization: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    access_token: str | None = Cookie(default=None, alias=JWT_COOKIE_NAME),
) -> ChatResponse:
    token = _extract_token(authorization) or _extract_token(access_token)
    if not token:
        raise HTTPException(status_code=401, detail="로그인 후 이용해 주세요.")

    # 보조 헤더가 비어 있을 경우 토큰에서 사용자 이메일을 복구한다.
    if not x_user_email:
        with contextlib.suppress(HTTPException):
            profile = _request_jwt_profile(token)
            recovered_email = profile.get("email")
            if recovered_email:
                x_user_email = str(recovered_email)

    user_message = body.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    payload = _build_rpc_payload(user_message)
    auth_header = _bearer_header(authorization or token)
    # 메타데이터로도 토큰/사용자 정보를 전달하여 서버 측 플러그인이 초기 페치 단계에서 활용할 수 있다.
    payload["params"].setdefault("metadata", {})
    payload["params"]["metadata"].update(
        {
            "authorization": auth_header,
            "user_email": x_user_email or "",
        }
    )
    rpc_result = await _send_rpc(
        payload,
        headers={
            "Authorization": auth_header,
            "X-User-Email": x_user_email or "",
        },
    )

    result_obj = rpc_result.get("result") or rpc_result.get("root", {}).get("result")
    reply_text = _extract_reply_from_result(result_obj) if result_obj else ""

    if not reply_text:
        reply_text = "오케스트레이터 응답을 해석하지 못했습니다."

    return ChatResponse(reply=reply_text, raw_response=rpc_result)


if __name__ == "__main__":
    import uvicorn

    # When executed as a script, prefer the local module path (`app:app`) so we
    # don't depend on the parent directory name being importable as `client`.
    uvicorn.run("app:app", host="0.0.0.0", port=8010, reload=True)
