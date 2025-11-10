import asyncio
import os
import logging
import sys
# Docker 환경에서는 현재 디렉토리를 PYTHONPATH에 추가
sys.path.insert(0, '.')
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from utils.model_config import get_model_with_fallback
from google.adk.tools import FunctionTool


# 현재 폴더의 .env 파일 로드
load_dotenv()

# redis 관련 툴 함수 불러오기
from tools.redis_item_tools import (
    get_item_details,
    track_item_inventory,
    get_all_warehouse_inventories_for_item,
    # update_item_status,
)

logger = logging.getLogger("item_agent")
logger.setLevel(logging.DEBUG)

# --- 1. Agent 정의 ---
# Gemini 우선, 실패시 로컬 LLM 사용
try:
    model = get_model_with_fallback()
    logger.info(f"ItemAgent 모델 설정 완료: {type(model).__name__ if hasattr(model, '__class__') else model}")
except Exception as e:
    logger.error(f"ItemAgent 모델 설정 실패: {e}")
    # 최후의 fallback
    ollama_host = os.getenv("OLLAMA_HOST", "localhost")
    model = LiteLlm(
        model="ollama_chat/gpt-oss:20b",
        api_base=f"http://{ollama_host}:11434"
    )
    logger.info("ItemAgent 최후 fallback으로 로컬 LLM 사용")

root_agent = LlmAgent(
    model=model,
    name="ItemAgent",
    description="상품 정보를 관리하고, 재고를 추적하며, 상품 관련 작업을 처리하는 에이전트 - Gemini/Local LLM hybrid",
    instruction="""너는 상품 관리 에이전트다.
    - 사용자가 상품 ID를 말하면 반드시 get_item_details 툴을 호출해야 한다.
    - '재고 수량'을 물어보면 track_item_inventory 툴을 호출해야 한다.
    - 만약 지정한 warehouse_id에 상품이 없으면, get_all_warehouse_inventories_for_item을 호출해서 다른 창고에 있는지 확인하라.
    """,
    tools=[
        FunctionTool(get_item_details),
        FunctionTool(track_item_inventory),
        FunctionTool(get_all_warehouse_inventories_for_item),
    ],
)

# --- 2. Runner + 세션 서비스 ---
APP_NAME = "item_management_app"
USER_ID = "user1"
SESSION_ID = "sess1"

session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

# --- 3. 실행 ---
async def main():
    # 세션 생성
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    print(">>> User Input: ITEM001 상품 상세 정보 알려줘")

    final_response = "응답 없음"

    # Content/Part 객체 생성
    user_message = types.Content(
        role="user",
        parts=[types.Part(text="ITEM001 상품 상세 정보 알려줘")]
    )

    # run_async 호출
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=user_message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    print(f"<<< Agent Response: {final_response}")



if __name__ == "__main__":
    asyncio.run(main())
