import logging
from uuid import uuid4
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, TextPart, Part, Role
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

logger = logging.getLogger(__name__)


class ADKAgentExecutor(AgentExecutor):
    def __init__(self, agent, app_name="orchestrator_app", user_id="user1", session_id="sess1"):
        self.agent = agent
        self.app_name = app_name
        self.user_id = user_id
        self.session_id = session_id
        self.session_service = InMemorySessionService()
        self.runner = Runner(agent=self.agent, app_name=self.app_name, session_service=self.session_service)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        try:
            # 세션 보장
            await self.session_service.create_session(
                app_name=self.app_name, user_id=self.user_id, session_id=self.session_id
            )

            # 사용자 입력 추출
            user_input = ""
            if context.message and context.message.parts:
                user_input = " ".join(
                    getattr(p.root, "text", "")
                    for p in context.message.parts
                    if hasattr(p.root, "text")
                )

            user_message = types.Content(role="user", parts=[types.Part(text=user_input)])

            final_response = None

            # Runner 실행 → 이벤트 스트림 수집
            async for event in self.runner.run_async(
                user_id=self.user_id,
                session_id=self.session_id,
                new_message=user_message,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            final_response = part.text

            if not final_response:
                final_response = "응답 없음"

            # 결과 Message 반환 (messageId 필수)
            msg = Message(
                role=Role.agent,
                parts=[Part(root=TextPart(text=final_response))],
                messageId=uuid4().hex,
            )
            await event_queue.enqueue_event(msg)

        except Exception as e:
            logger.exception("ADKAgentExecutor.execute 오류")
            error_msg = Message(
                role=Role.agent,
                parts=[Part(root=TextPart(text=f"[Error] {str(e)}"))],
                messageId=uuid4().hex,
            )
            await event_queue.enqueue_event(error_msg)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return
