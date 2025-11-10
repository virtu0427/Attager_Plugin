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
from tools.redis_quality_tools import (
    get_items_for_return_qc,
    get_return_item_disposition,
    get_recall_items_list,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)   

# --- 1. Agent 정의 ---
# Gemini 우선, 실패시 로컬 LLM 사용
try:
    model = get_model_with_fallback()
    logger.info(f"QualityAgent 모델 설정 완료: {type(model).__name__ if hasattr(model, '__class__') else model}")
except Exception as e:
    logger.error(f"QualityAgent 모델 설정 실패: {e}")
    # 최후의 fallback
    ollama_host = os.getenv("OLLAMA_HOST", "localhost")
    model = LiteLlm(
        model="ollama_chat/gpt-oss:20b",
        api_base=f"http://{ollama_host}:11434"
    )
    logger.info("QualityAgent 최후 fallback으로 로컬 LLM 사용")

root_agent = LlmAgent(
    model=model,
    name="QualityAgent",
    description=(
        "반품·리콜 상품의 품질 검사를 수행하고 격리/처분을 결정하며, "
        "검사 결과에 따라 판매 가능 재고 상태를 관리하는 에이전트 - Gemini/Local LLM hybrid"
    ),
    instruction="""너는 품질 관리 에이전트다.\
    - '품질 검사가 필요한 반품 상품'을 요청하면 get_items_for_return_qc 툴을 호출해야 한다.\
    - '반품 상품의 최종 처분'을 조회하려면 get_return_item_disposition 툴을 호출해야 한다.\
    - '특정 제품 ID의 리콜 대상 상품 리스트'를 요청하면 get_recall_items_list 툴을 호출해야 한다.
    """,
    tools=[
        FunctionTool(get_items_for_return_qc),
        FunctionTool(get_return_item_disposition),
        FunctionTool(get_recall_items_list),
    ],
)

# --- 2. Runner + 세션 서비스 ---
APP_NAME = "quality_management_app"
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

    print(">>> User Input: 반품 상품 ITEM002 품질 검사 결과 good, 처분 재판매로 해줘")

    final_response = "응답 없음"

    # Content/Part 객체 생성
    user_message = types.Content(
        role="user",
        parts=[types.Part(text="반품 상품 ITEM002 품질 검사 결과 good, 처분 재판매로 해줘")]
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
