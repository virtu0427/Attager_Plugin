import logging

from collections.abc import Callable

import httpx

from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    SendMessageRequest,
    SendMessageResponse,
    Task,
    Message,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
    TaskState,
)
from dotenv import load_dotenv


load_dotenv()

TaskCallbackArg = Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent
TaskUpdateCallback = Callable[[TaskCallbackArg, AgentCard], Task]

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


from a2a.client import ClientFactory

class RemoteAgentConnections:
    """A class to hold the connections to the remote agents."""

    def __init__(self, client_factory: ClientFactory, agent_card: AgentCard):
        self.card: AgentCard = agent_card
        # ✅ a2a-sdk 0.3.5에서는 이렇게 생성해야 함
        self.agent_client = client_factory.create(agent_card)
        self.pending_tasks = set()

    def get_agent(self) -> AgentCard:
        return self.card

    async def send_message(self, message: Message) -> Task | Message | None:
        last_task: Task | None = None
        async for event in self.agent_client.send_message(message,stream=False):
            if isinstance(event, Message):
                return event
            if self.is_terminal_or_interrupted(event[0]):
                return event[0]
            last_task = event[0]
        return last_task

    def is_terminal_or_interrupted(self, task: Task) -> bool:
        return task.status.state in [
            TaskState.completed,
            TaskState.canceled,
            TaskState.failed,
            TaskState.input_required,
            TaskState.unknown,
        ]
