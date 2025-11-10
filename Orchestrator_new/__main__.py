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
from agent import root_agent as orchestrator_agent
from agent_executor import ADKAgentExecutor


def main(inhost, inport):    # Agent card (metadata)
    agent_card = AgentCard(
        name='Orchestrator Agent',
        description=orchestrator_agent.description,
        url=f'http://{inhost}:{inport}',
        version="1.0.0",
        defaultInputModes=["text", "text/plain"],
        defaultOutputModes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="orchestrator_agent",
                name="orchestrate other agents",
                description="Orchestrate other agents by user requestment",
                tags=["orchestrator"],
                examples=[
                    "What agent should I use to get delivery data for ORD1001",
                ],
            )
        ],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=ADKAgentExecutor(
            agent=orchestrator_agent,
        ),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    uvicorn.run(server.build(), host=inhost, port=inport)


if __name__ == "__main__":
    main("127.0.0.1", 10000)