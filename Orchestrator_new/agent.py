import os
from typing import List
import logging
import httpx
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from a2a.types import (
    AgentCard,
    Message,
    Role,
    Part,
    TextPart,
    MessageSendParams,
)
import sys
# Docker 환경에서는 현재 디렉토리를 PYTHONPATH에 추가
sys.path.insert(0, '.')
from utils.model_config import get_model_with_fallback

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- 1. AgentCard 로더 ---

def load_agent_cards(tool_context) -> List[str]:
    """
    레지스트리 서버에서 에이전트 카드 목록을 조회해서 state에 저장,
    에이전트 이름 리스트 반환
    """
    url = "http://localhost:8000/agents"
    resp = httpx.get(url)
    resp.raise_for_status()
    agents_data = resp.json()  # 레지스트리에서 내려주는 JSON 배열

    cards = {}
    for data in agents_data:
        # ✅ dict → AgentCard 변환 (pydantic v1/v2 호환)
        if hasattr(AgentCard, "model_validate"):   # pydantic v2
            card = AgentCard.model_validate(data)
        else:  # pydantic v1
            card = AgentCard.parse_obj(data)

        name = getattr(card, "name", None) or card.url or "unknown_agent"
        cards[name] = card

    # state에 저장
    tool_context.state["cards"] = cards
    return list(cards.keys())


# --- 2. Remote Agent 호출 ---

import uuid
import httpx
from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    Message,
    TextPart,
    Part,
    Role,
    MessageSendParams,
    SendMessageRequest,
)


async def call_remote_agent(tool_context, agent_name: str, task: str):
    """
    A2A SDK 0.3.5 기준, 공식 튜토리얼 non-streaming 방식
    """

    # 1. 에이전트 카드 조회
    cards: dict[str, AgentCard] = tool_context.state.get("cards", {})
    card = cards.get(agent_name)
    if not card:
        return {"error": f"Agent {agent_name} not found"}

    # 2. 클라이언트 준비
    async with httpx.AsyncClient(timeout=30.0) as httpx_client:
        client = A2AClient(httpx_client=httpx_client, agent_card=card)

        # 3. 요청 메시지 (messageId 필드명 주의)
        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=task))],
            messageId=uuid.uuid4().hex,  # ✅ message_id → messageId
        )
        send_params = MessageSendParams(message=message)
        request = SendMessageRequest(id=str(uuid.uuid4()), params=send_params)

        # 4. 서버 호출
        resp = await client.send_message(request)

        # 5. 결과를 JSON으로 덤프
        return resp.model_dump(mode="json", exclude_none=True)


# --- 3. 응답 집계 ---

def return_result(tool_context: ToolContext, result: str) -> str:
    """
    최종 결과를 사용자에게 전달하는 도구.
    이 도구를 호출하면 더 이상 다른 도구를 호출하지 않고,
    LLM이 이 결과를 최종 응답으로 반환한다.
    """
    # state에 저장해둘 수도 있음 (선택 사항)
    tool_context.state["final_result"] = result
    return result

# --- Root Agent 정의 ---
# Gemini 우선, 실패시 로컬 LLM 사용
try:
    model = get_model_with_fallback()
    logger.info(f"모델 설정 완료: {type(model).__name__ if hasattr(model, '__class__') else model}")
except Exception as e:
    logger.error(f"모델 설정 실패: {e}")
    # 최후의 fallback
    ollama_host = os.getenv("OLLAMA_HOST", "localhost")
    model = LiteLlm(
        model="ollama_chat/gpt-oss:20b",
        api_base=f"http://{ollama_host}:11434",
        temperature=0.7,
    )
    logger.info("최후 fallback으로 로컬 LLM 사용")

root_agent = LlmAgent(
    name="root_orchestrator",
    model=model,
    instruction=(
        "너는 Root Orchestrator Agent야.\n"
        "너의 임무는 사용자 요청에 맞는 에이전트를 선택해서 작업을 위임하고 결과를 집계해서 사용자에게 반환하는 것이야.\n"
        "'load_agent_cards'는 에이전트 카드를 불러오는 도구이다\n"
        "'call_remote_agent'는 에이전트를 호출하는 도구이다\n"
        "   (에이전트 카드에서 agent_name과 task를 파라미터로 넣어 호출해야 한다)\n"
        "'return_result'에는 너가 사용자에게 응답할 내용을 적고 사용자에게 반환해\n"
    ),
    description="LLM 기반 Root Orchestrator Agent (multi-agent coordination) - Gemini/Local LLM hybrid",
    tools=[FunctionTool(load_agent_cards), FunctionTool(call_remote_agent), FunctionTool(return_result)],
)

