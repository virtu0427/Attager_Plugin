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
from agent import root_agent as item_agent
from agent_executor import ADKAgentExecutor


def main(inhost, inport):
    # Agent card (metadata)
    agent_card = AgentCard(
        name='Item Agent',
        description=item_agent.description,
        url=f'http://{inhost}:{inport}',
        version="1.0.0",
        defaultInputModes=["text", "text/plain"],
        defaultOutputModes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="item_agent",
                name="manage item operations",
                description="Handle item data retrieval, inventory tracking, and item management",
                tags=["item", "inventory", "product"],
                examples=[
                    "Read item details for ITEM001",
                    "Track item inventory",
                    "Check product availability",
                    "Get item status"
                ],
            )
        ],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=ADKAgentExecutor(
            agent=item_agent,
        ),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    uvicorn.run(server.build(), host=inhost, port=inport)


if __name__ == "__main__":
    main("0.0.0.0", 10002)