import asyncio
import contextlib
import os
import secrets
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
STATIC_DIR = BASE_DIR / "static"

ORCHESTRATOR_RPC_URL = os.getenv("ORCHESTRATOR_RPC_URL", "http://localhost:10000/").rstrip("/") + "/"
JWT_SERVER_URL = os.getenv("JWT_SERVER_URL", "http://localhost:8011").rstrip("/")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "chat_session")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {
    "1",
    "true",
    "yes",
}
SESSION_COOKIE_MAX_AGE = int(os.getenv("SESSION_COOKIE_MAX_AGE", "3600"))

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


class SessionData(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserProfile


SessionStore = Dict[str, SessionData]
_SESSIONS: SessionStore = {}
_SESSION_LOCK = threading.Lock()


def _session_cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "secure": SESSION_COOKIE_SECURE,
        "samesite": "lax",
        "max_age": SESSION_COOKIE_MAX_AGE,
        "path": "/",
    }


def _set_session(session_id: str, data: SessionData) -> None:
    with _SESSION_LOCK:
        _SESSIONS[session_id] = data


def _get_session(session_id: str) -> SessionData | None:
    with _SESSION_LOCK:
        return _SESSIONS.get(session_id)


def _delete_session(session_id: str) -> None:
    with _SESSION_LOCK:
        _SESSIONS.pop(session_id, None)


def _extract_session(request: Request) -> Tuple[str, SessionData | None]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not session_id:
        return "", None
    return session_id, _get_session(session_id)


def _require_session(request: Request) -> Tuple[str, SessionData]:
    session_id, session = _extract_session(request)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다.")
    return session_id, session


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def _require_session_dependency(request: Request) -> SessionData:
    """FastAPI dependency to ensure a valid session exists."""

    _, session = _require_session(request)
    return session


@app.get("/")
async def redirect_root() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/login", response_class=FileResponse)
async def serve_login() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "login.html")


@app.get("/chat")
async def serve_chat(request: Request) -> Response:
    try:
        _require_session(request)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
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


def _issue_session(
    response: Response, token: str, token_type: str, user_profile: UserProfile
) -> None:
    session_id = secrets.token_urlsafe(32)
    _set_session(
        session_id,
        SessionData(token=token, token_type=token_type, user=user_profile),
    )
    response.set_cookie(SESSION_COOKIE_NAME, session_id, **_session_cookie_kwargs())


@app.post("/api/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response) -> LoginResponse:
    token_payload = _request_jwt_token(body.email, body.password)
    access_token = token_payload.get("access_token")
    token_type = str(token_payload.get("token_type") or "bearer")
    if not access_token:
        raise HTTPException(status_code=502, detail="JWT 토큰을 발급받지 못했습니다")

    user_payload = _request_jwt_profile(access_token)
    email = user_payload.get("email")
    tenants = _normalize_tenants(user_payload.get("tenant"))
    if not email:
        raise HTTPException(status_code=502, detail="JWT 서버가 사용자 정보를 반환하지 않았습니다")

    user_profile = UserProfile(email=email, tenants=tenants)
    _issue_session(response, access_token, token_type, user_profile)
    return LoginResponse(access_token=access_token, token_type=token_type, user=user_profile)


@app.post("/api/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> None:
    session_id, _ = _extract_session(request)
    if session_id:
        _delete_session(session_id)
    _clear_session_cookie(response)


@app.get("/api/session", response_model=LoginResponse)
def session_info(session: SessionData = Depends(_require_session_dependency)) -> LoginResponse:
    return LoginResponse(
        access_token=session.token,
        token_type=session.token_type,
        user=session.user,
    )


async def _send_rpc(payload: dict, session: SessionData | None = None) -> dict:
    headers = {}
    if session:
        token_type = (session.token_type or "bearer").strip()
        scheme = token_type.capitalize() if token_type.lower() == "bearer" else token_type
        headers = {
            "Authorization": f"{scheme} {session.token}",
            "X-User-Email": session.user.email,
        }
    try:
        response = await asyncio.to_thread(
            requests.post,
            ORCHESTRATOR_RPC_URL,
            json=payload,
            headers=headers or None,
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


@app.post("/api/chat", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    _session: SessionData = Depends(_require_session_dependency),
) -> ChatResponse:
    user_message = body.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    payload = _build_rpc_payload(user_message)
    rpc_result = await _send_rpc(payload, session=_session)

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
