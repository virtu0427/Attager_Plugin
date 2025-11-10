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
from tools.redis_vehicle_tools import (
    get_fleet_availability,
    get_vehicle_status,
    filter_available_vehicles,
    get_vehicles_on_maintenance,
    get_assigned_recall_vehicles,
    get_vehicle_capacity,
    recommend_optimal_vehicles,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- 1. Agent 정의 ---
# Gemini 우선, 실패시 로컬 LLM 사용
try:
    model = get_model_with_fallback()
    logger.info(f"VehicleAgent 모델 설정 완료: {type(model).__name__ if hasattr(model, '__class__') else model}")
except Exception as e:
    logger.error(f"VehicleAgent 모델 설정 실패: {e}")
    # 최후의 fallback
    ollama_host = os.getenv("OLLAMA_HOST", "localhost")
    model = LiteLlm(
        model="ollama_chat/gpt-oss:20b",
        api_base=f"http://{ollama_host}:11434"
    )
    logger.info("VehicleAgent 최후 fallback으로 로컬 LLM 사용")

root_agent = LlmAgent(
    model=model,
    name="VehicleAgent",
    description=(
        "운행가능 차량과 배송 투입 차량의 가용 여부 및 운행 상태를 관리하는 에이전트. "
        "차량 상태 조회/업데이트, 배정·해제, 정비 스케줄 반영을 수행합니다. - Gemini/Local LLM hybrid"
    ),
    instruction="""너는 배차/차량 운영 에이전트다.\
    - '전체 가용 현황'을 요청하면 get_fleet_availability 툴을 호출해야 한다.\
    - '차량 상태 조회'를 요청하면 get_vehicle_status 툴을 호출해야 한다.\
    - '운행 가능 차량 필터링'을 요청하면 filter_available_vehicles 툴을 호출해야 한다.\
    - '현재 정비 중인 차량'을 요청하면 get_vehicles_on_maintenance 툴을 호출해야 한다.\
    - '리콜에 배정된 차량 리스트'를 요청하면 get_assigned_recall_vehicles 툴을 호출해야 한다.\
    - '차량 적재 용량'을 조회하려면 get_vehicle_capacity 툴을 호출해야 한다.\
    - '최적 차량 추천'을 요청하면 recommend_optimal_vehicles 툴을 호출해야 한다.
    """,
    tools=[
        FunctionTool(get_fleet_availability),
        FunctionTool(get_vehicle_status),
        FunctionTool(filter_available_vehicles),
        FunctionTool(get_vehicles_on_maintenance),
        FunctionTool(get_assigned_recall_vehicles),
        FunctionTool(get_vehicle_capacity),
        FunctionTool(recommend_optimal_vehicles),
    ],

)

# --- 2. Runner + 세션 서비스 ---
APP_NAME = "vehicle_management_app"
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

    print(">>> User Input: 전체 차량 가용 현황 알려줘")

    final_response = "응답 없음"

    # Content/Part 객체 생성
    user_message = types.Content(
        role="user",
        parts=[types.Part(text="전체 차량 가용 현황 알려줘")]
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
