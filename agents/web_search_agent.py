"""
This module defines the web_search_agent, which can search the web and fetch content from pages.
"""

import json
import sys
from pathlib import Path
import flyte

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import tools to register them
import tools.web_search_tools

from utils.decorators import agent, agent_tools
from utils.plan_executor import execute_plan
from dataclasses import dataclass
from config import base_env

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class WebSearchAgentResult:
    """Result from web search agent execution"""
    final_result: str
    steps: str  # JSON string of steps taken
    error: str = ""  # Empty if no error


# ----------------------------------
# Web Search Agent Task Environment
# ----------------------------------
env = base_env
# Future: If we need web-specific dependencies like playwright, we can extend:
# env = flyte.TaskEnvironment(
#     name="web_search_agent_env",
#     image=base_env.image.with_pip_packages(["playwright"]),
#     secrets=base_env.secrets,
#     resources=flyte.Resources(cpu=1, mem="2Gi")
# )


@env.task
@agent("web_search")
async def web_search_agent(task: str) -> WebSearchAgentResult:
    """
    Web search agent that can search DuckDuckGo and fetch webpage content.

    Args:
        task (str): The web search task to perform.

    Returns:
        WebSearchAgentResult: The result of the search and the steps taken.
    """
    print(f"[Web Search Agent] Processing: {task}")

    toolset = agent_tools["web_search"]
    tool_list = "\n".join([f"{name}: {fn.__doc__.strip()}" for name, fn in toolset.items()])
    system_msg = f"""
You are a web search agent. You can search the web and fetch content from URLs.

Tools:
{tool_list}

CRITICAL: You must respond with ONLY a valid JSON array, nothing else. No markdown, no explanations.
Return a JSON array of tool calls in this exact format:
[
  {{"tool": "duck_duck_go", "args": ["Python async tutorial", 5, "us-en", "moderate", "w"], "reasoning": "Searching for recent Python async tutorials from the past week"}},
  {{"tool": "fetch_webpage", "args": ["https://example.com", 3000], "reasoning": "Fetching content from the first result to extract details"}}
]

RULES:
1. Start your response with [ and end with ]
2. No markdown code blocks (no ```)
3. No extra text before or after the JSON
4. Always include a "reasoning" field for each step
5. When using fetch_webpage, use the "href" from search results as the URL argument
"""

    memory_log = []  # No memory persistence for now
    result = await execute_plan(task, agent="web_search", system_msg=system_msg)

    print(f"[Web Search Agent] Result: {result}")

    return WebSearchAgentResult(
        final_result=str(result.get("final_result", "")),
        steps=json.dumps(result.get("steps", [])),
        error=result.get("error", "")
    )