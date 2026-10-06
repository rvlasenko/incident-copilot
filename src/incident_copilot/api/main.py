"""Production wiring: the only place that reads settings and talks to a real LLM.

Kept out of app.py so importing the app factory in tests never needs an API key.
"""

import logging

from incident_copilot.agent.graph import build_graph
from incident_copilot.agent.planner import LLMPlanner
from incident_copilot.api.app import create_app
from incident_copilot.config import AgentSettings, LLMSettings
from incident_copilot.llm.openai_provider import OpenAIProvider

logging.basicConfig(level=logging.INFO)

planner = LLMPlanner(OpenAIProvider(LLMSettings()))

app = create_app(
    build_graph(planner=planner),
    run_timeout_seconds=AgentSettings().run_timeout_seconds,
)
