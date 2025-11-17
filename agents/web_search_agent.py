"""
This module defines the web_search_agent, which can search the web and fetch content from pages.
"""

import json
import sys
from pathlib import Path
import flyte
from openai import AsyncOpenAI

# Import tools to register them
import tools.web_search_tools

from utils.decorators import agent, agent_tools
from utils.plan_executor import execute_tool_plan, parse_plan_from_response
from dataclasses import dataclass
from config import base_env, OPENAI_API_KEY

# ----------------------------------
# Agent-Specific Configuration
# ----------------------------------
WEB_SEARCH_AGENT_CONFIG = {
    "model": "gpt-4o",        # Needs good reasoning for search queries
    "temperature": 0.3,       # Slight creativity for search terms
    "max_tokens": 1000,
}

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class WebSearchAgentResult:
    """Result from web search agent execution"""
    final_result: str
    steps: str  # JSON string of steps taken
    summary: str = ""  # Concise summary for passing to other agents
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

    # Call LLM to create plan using agent-specific config
    response = await client.chat.completions.create(
        model=WEB_SEARCH_AGENT_CONFIG["model"],
        temperature=WEB_SEARCH_AGENT_CONFIG["temperature"],
        max_tokens=WEB_SEARCH_AGENT_CONFIG["max_tokens"],
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": "Search for Python async tutorials from the past week"},
            {"role": "assistant", "content": '[{"tool": "duck_duck_go", "args": ["Python async tutorial", 5, "us-en", "moderate", "w"], "reasoning": "Searching for recent Python async tutorials"}]'},
            {"role": "user", "content": task}
        ]
    )

    # Parse and execute the plan
    raw_plan = response.choices[0].message.content
    plan = parse_plan_from_response(raw_plan)
    result = await execute_tool_plan(plan, agent="web_search")

    print(f"[Web Search Agent] Result: {result}")

    full_result = str(result.get("final_result", ""))

    # Create a concise summary (first 500 chars or first paragraph)
    summary = full_result[:500] + "..." if len(full_result) > 500 else full_result

    print(f"[Web Search Agent] Summary: {summary[:100]}...")

    return WebSearchAgentResult(
        final_result=full_result,
        steps=json.dumps(result.get("steps", [])),
        summary=summary,
        error=result.get("error", "")
    )