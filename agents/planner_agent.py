"""
This module defines the planner_agent, which routes requests to appropriate specialist agents.
"""

import json
import sys
from pathlib import Path
import flyte
from openai import AsyncOpenAI
from dataclasses import dataclass
from typing import List

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import OPENAI_API_KEY
from utils.decorators import agent, agent_registry
from config import base_env

# Import all agents to populate registry (don't need to use them, just import)
import agents.math_agent
import agents.string_agent
import agents.web_search_agent
import agents.code_agent

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class AgentStep:
    """Single step in the execution plan"""
    agent: str
    task: str
    dependencies: List[int] = None  # List of step indices this step depends on (0-indexed)

    def __post_init__(self):
        # Default to empty list if None
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class PlannerDecision:
    """Decision from planner agent - can contain multiple steps"""
    steps: List[AgentStep]


# ----------------------------------
# Planner Agent Task Environment
# ----------------------------------
env = base_env
# env = flyte.TaskEnvironment(
#     name="planner_agent_env",
#     image=flyte.Image.from_debian_base().with_requirements("requirements.txt"),
#     secrets=[
#         flyte.Secret(key="OPENAI_API_KEY", as_env_var="OPENAI_API_KEY"),
#     ],
#     # Planner is lightweight, doesn't need much compute
#     # resources=flyte.Resources(cpu=1, mem="1Gi")
# )


@env.task
@agent("planner")
async def planner_agent(user_request: str) -> PlannerDecision:
    """
    Planner agent that analyzes requests and creates execution plans.

    Args:
        user_request (str): The user's request to analyze and route.

    Returns:
        PlannerDecision: Plan with one or more agent steps.
    """
    print(f"[Planner Agent] Processing request: {user_request}")

    memory_log = []  # No memory persistence for now
    context = "\n".join([f"- {q} → {r}" for q, r in memory_log[-5:]]) or "No history."
    available_agents = [a for a in agent_registry if a != "planner"]
    agent_list = "\n".join([f"- {a}" for a in available_agents])

    system_msg = (
        f"You are a routing agent.\nAvailable agents:\n{agent_list}\n\n"
        f"Recent memory:\n{context}\n\n"
        f"Analyze the user's request and decide which agent(s) to use.\n\n"
        f"DEPENDENCIES: Use 'dependencies' to specify which steps must complete before this step.\n"
        f"- dependencies is a list of step indices (0-indexed)\n"
        f"- Empty list [] means the step can run immediately (no dependencies)\n"
        f"- Steps with no dependencies can run in PARALLEL\n"
        f"- Steps with dependencies will wait for those steps to complete\n\n"
        f"Examples:\n\n"
        f"INDEPENDENT TASKS (can run in parallel):\n"
        f"{{\"steps\": [\n"
        f"  {{\"agent\": \"math\", \"task\": \"Calculate 5 factorial\", \"dependencies\": []}},\n"
        f"  {{\"agent\": \"string\", \"task\": \"Count words in 'Hello World'\", \"dependencies\": []}},\n"
        f"  {{\"agent\": \"web_search\", \"task\": \"Search for Python tutorials\", \"dependencies\": []}}\n"
        f"]}}\n\n"
        f"DEPENDENT TASKS (step 1 must complete before step 2):\n"
        f"{{\"steps\": [\n"
        f"  {{\"agent\": \"math\", \"task\": \"Calculate 5 times 3\", \"dependencies\": []}},\n"
        f"  {{\"agent\": \"math\", \"task\": \"Add 10 to the previous result\", \"dependencies\": [0]}}\n"
        f"]}}\n\n"
        f"MIXED (steps 0 and 1 run in parallel, step 2 waits for both):\n"
        f"{{\"steps\": [\n"
        f"  {{\"agent\": \"math\", \"task\": \"Calculate 5 factorial\", \"dependencies\": []}},\n"
        f"  {{\"agent\": \"string\", \"task\": \"Count letters in 'test'\", \"dependencies\": []}},\n"
        f"  {{\"agent\": \"code\", \"task\": \"Combine the results\", \"dependencies\": [0, 1]}}\n"
        f"]}}\n\n"
        f"IMPORTANT: Always include 'dependencies' field for each step, even if empty []."
    )

    res = await client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_request}
        ]
    )

    result = json.loads(res.choices[0].message.content)
    print(f"[Planner Agent] Raw result: {result}")

    # Handle old format (single step without "steps" wrapper)
    if "agent" in result and "task" in result:
        print(f"[Planner Agent] Converting old format to new format")
        result = {"steps": [{"agent": result["agent"], "task": result["task"]}]}

    # Convert to dataclass
    steps = [
        AgentStep(
            agent=step["agent"],
            task=step["task"],
            dependencies=step.get("dependencies", [])
        )
        for step in result["steps"]
    ]

    print(f"[Planner Agent] Plan has {len(steps)} step(s)")
    for i, step in enumerate(steps, 1):
        deps_str = f" (depends on: {step.dependencies})" if step.dependencies else " (no dependencies)"
        print(f"[Planner Agent]   Step {i}: {step.agent} - {step.task}{deps_str}")

    return PlannerDecision(steps=steps)