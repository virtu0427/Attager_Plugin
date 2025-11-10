import click
import uvicorn

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from agent import root_agent as delivery_agent, plugin
from agent_executor import ADKAgentExecutor


def main(inhost, inport):
    # Agent card (metadata)
    agent_card = AgentCard(
        name='Delivery Agent',
        description=delivery_agent.description,
        url=f'http://{inhost}:{inport}',
        version="1.0.0",
        defaultInputModes=["text", "text/plain"],
        defaultOutputModes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="delivery_agent",
                name="manage delivery operations",
                description="Handle delivery data retrieval, status tracking, and delivery management",
                tags=["delivery", "logistics", "tracking"],
                examples=[
                    "Read delivery data for ORD1001",
                    "Get all deliveries",
                    "Check completed deliveries count",
                    "Track delivery status"
                ],
            )
        ],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=ADKAgentExecutor(
            agent=delivery_agent,
            plugins=[plugin]  # IAM 정책 플러그인 적용
        ),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    uvicorn.run(server.build(), host=inhost, port=inport)


if __name__ == "__main__":
    main("0.0.0.0", 10001)