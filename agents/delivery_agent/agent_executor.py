import logging
from uuid import uuid4
from contextvars import ContextVar

request_token_var: ContextVar[str | None] = ContextVar("request_token", default=None)

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, TextPart, Part, Role
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

logger = logging.getLogger(__name__)
_DEFAULT_USER_ERROR = "요청을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."


class ADKAgentExecutor(AgentExecutor):
    def __init__(self, agent, app_name="orchestrator_app", user_id="user1", session_id="sess1", plugins=None):
        self.agent = agent
        self.app_name = app_name
        self.user_id = user_id
        self.session_id = session_id
        self.plugins = plugins or []
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name=self.app_name,
            session_service=self.session_service,
            plugins=self.plugins
        )

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # 레이스 컨디션 방지용 동적 세션 ID
        current_session_id = getattr(context, "request_id", None) or str(uuid4())

        try:
            # 세션 생성
            try:
                await self.session_service.create_session(
                    app_name=self.app_name, user_id=self.user_id, session_id=current_session_id
                )
            except Exception as session_error:
                if "already exists" not in str(session_error):
                    raise

            # =================================================================
            # [토큰 주입] ContextVar에서 토큰을 꺼내 세션에 주입
            # =================================================================
            auth_token = ""
            if context.metadata:
                auth_token = context.metadata.get("Authorization") or context.metadata.get("authorization")
            
            if not auth_token:
                auth_token = request_token_var.get()
                # [지뢰 3] ContextVar 확인
                print(f"🔥🔥 [2. Executor] ContextVar 조회 결과: {bool(auth_token)} 🔥🔥", flush=True)

            if auth_token:
                session = await self.session_service.get_session(
                    app_name=self.app_name,
                    user_id=self.user_id,
                    session_id=current_session_id
                )
                
                if session:
                    if not hasattr(session, "state") or session.state is None:
                        session.state = {}
                    session.state["auth_token"] = auth_token
                    # [지뢰 4] 세션 주입 성공
                    print(f"🔥🔥 [2. Executor] 세션(ID:{current_session_id})에 토큰 주입 완료! 🔥🔥", flush=True)
            else:
                print("🔥🔥 [2. Executor] ⚠️ 실패: 주입할 토큰이 없습니다. 🔥🔥", flush=True)
            # =================================================================

            # 사용자 입력 추출
            user_input = ""
            if context.message and context.message.parts:
                user_input = " ".join(
                    getattr(p.root, "text", "")
                    for p in context.message.parts
                    if hasattr(p.root, "text")
                )

            user_message = types.Content(role="user", parts=[types.Part(text=user_input)])

            callback_context = self._build_callback_context(context)

            for plugin in self.plugins:
                try:
                    plugin._capture_auth_from_context(callback_context)
                    plugin.fetch_policy(tool_context=callback_context)
                except Exception:
                    logger.exception("플러그인 사전 준비 중 오류")

            final_response = None

            # Runner 실행
            async for event in self.runner.run_async(
                user_id=self.user_id,
                session_id=current_session_id,
                new_message=user_message,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            final_response = part.text

            if not final_response:
                final_response = "응답 없음"

            msg = Message(
                role=Role.agent,
                parts=[Part(root=TextPart(text=final_response))],
                messageId=uuid4().hex,
            )
            await event_queue.enqueue_event(msg)

        except Exception as e:
            logger.exception("ADKAgentExecutor.execute 오류")
            safe_error = self._format_user_error(str(e))
            error_msg = Message(
                role=Role.agent,
                parts=[Part(root=TextPart(text=safe_error))],
                messageId=uuid4().hex,
            )
            await event_queue.enqueue_event(error_msg)
        
        finally:
            # 세션 정리 (여기서도 인자 다 넣어주는 게 안전합니다)
            try:
                await self.session_service.delete_session(
                    app_name=self.app_name,
                    session_id=current_session_id
                )
            except Exception:
                pass

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return

    def _build_callback_context(self, context: RequestContext) -> dict:
        headers = {}
        state = {}
        if getattr(context, "call_context", None):
            state = getattr(context.call_context, "state", {}) or {}
            headers = state.get("headers") or {}

        message = getattr(context, "message", None)
        message_metadata = {}
        task_id = None
        message_id = None
        if message is not None:
            message_metadata = getattr(message, "metadata", {}) or {}
            task_id = getattr(message, "taskId", None) or message_metadata.get("taskId")
            message_id = getattr(message, "messageId", None)

        return {
            "headers": headers,
            "metadata": getattr(context, "metadata", {}) or {},
            "state": state,
            "message": {
                "metadata": message_metadata,
                "taskId": task_id,
                "messageId": message_id,
            },
        }

    def _format_user_error(self, raw_message: str) -> str:
        message = raw_message or ""
        for plugin in self.plugins:
            sanitizer = getattr(plugin, "sanitize_error_message", None)
            if callable(sanitizer):
                try:
                    return sanitizer(message)
                except Exception:  # pragma: no cover
                    logger.exception("에러 메시지 정제 실패")
        condensed = message.strip()
        if condensed:
            if len(condensed) > 200:
                condensed = condensed[:200] + "..."
            return f"{_DEFAULT_USER_ERROR}\n세부 정보: {condensed}"
        return _DEFAULT_USER_ERROR
