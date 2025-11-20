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
from Orchestrator_plugin.agent import (
    plugin as policy_plugin,
    root_agent as orchestrator_agent,
)
from Orchestrator_plugin.agent_executor import ADKAgentExecutor


def main(inhost: str, inport: int):
    """Launch the orchestrator agent server."""
    agent_card = AgentCard(
        name="Orchestrator Agent",
        description=orchestrator_agent.description,
        url=f"http://{inhost}:{inport}",
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
            agent=orchestrator_agent, plugins=[policy_plugin]
        ),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    uvicorn.run(server.build(), host=inhost, port=inport)


@click.command()
@click.option("--host", "inhost", default="0.0.0.0", help="Host to bind the orchestrator server.")
@click.option("--port", "inport", default=10000, type=int, help="Port to bind the orchestrator server.")
def cli(inhost: str, inport: int):
    main(inhost, inport)


if __name__ == "__main__":
    cli()
