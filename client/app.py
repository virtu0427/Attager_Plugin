import asyncio
import os
import uuid
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
STATIC_DIR = BASE_DIR / "static"

ORCHESTRATOR_RPC_URL = os.getenv("ORCHESTRATOR_RPC_URL", "http://localhost:10000/").rstrip("/") + "/"

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


@app.get("/", response_class=FileResponse)
async def serve_index() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html")


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


async def _send_rpc(payload: dict) -> dict:
    try:
        response = await asyncio.to_thread(
            requests.post,
            ORCHESTRATOR_RPC_URL,
            json=payload,
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
async def send_message(body: ChatRequest) -> ChatResponse:
    user_message = body.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    payload = _build_rpc_payload(user_message)
    rpc_result = await _send_rpc(payload)

    result_obj = rpc_result.get("result") or rpc_result.get("root", {}).get("result")
    reply_text = _extract_reply_from_result(result_obj) if result_obj else ""

    if not reply_text:
        reply_text = "오케스트레이터 응답을 해석하지 못했습니다."

    return ChatResponse(reply=reply_text, raw_response=rpc_result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("client.app:app", host="0.0.0.0", port=8010, reload=True)
