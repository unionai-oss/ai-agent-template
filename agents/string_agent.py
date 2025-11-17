"""
This module defines the string_agent, which is responsible for string analysis and text processing.
"""

import json
import sys
from pathlib import Path
import flyte
from openai import AsyncOpenAI

# Import tools to register them
import tools.string_tools

from utils.decorators import agent, agent_tools
from utils.plan_executor import execute_tool_plan, parse_plan_from_response
from dataclasses import dataclass
from config import base_env, OPENAI_API_KEY

# ----------------------------------
# Agent-Specific Configuration
# ----------------------------------
STRING_AGENT_CONFIG = {
    "model": "gpt-4o-mini",  # Text counting is simple
    "temperature": 0.0,       # Deterministic
    "max_tokens": 300,
}

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class StringAgentResult:
    """Result from string agent execution"""
    final_result: str
    steps: str  # JSON string of steps taken
    error: str = ""  # Empty if no error


# ----------------------------------
# String Agent Task Environment
# ----------------------------------
env = base_env
# env = flyte.TaskEnvironment(
#     name="string_agent_env",
#     image=flyte.Image.from_debian_base().with_requirements("requirements.txt"),
#     secrets=[
#         flyte.Secret(key="OPENAI_API_KEY", as_env_var="OPENAI_API_KEY"),
#     ],
#     # Future: Add string-specific resources if needed
#     # resources=flyte.Resources(cpu=1, mem="2Gi")
# )


@env.task
@agent("string")
async def string_agent(task: str) -> StringAgentResult:
    """
    String analysis agent that can count letters, words, and analyze text.

    Args:
        task (str): The string analysis task to perform.

    Returns:
        StringAgentResult: The result of the analysis and the steps taken.
    """
    print(f"[String Agent] Processing: {task}")

    # Build system message with available tools
    toolset = agent_tools["string"]
    tool_list = "\n".join([f"{name}: {fn.__doc__.strip()}" for name, fn in toolset.items()])
    system_msg = f"""
You are a string analysis agent. You can count letters, words, and analyze text.

Tools:
{tool_list}

CRITICAL: You must respond with ONLY a valid JSON array, nothing else. No markdown, no explanations.
Return a JSON array of tool calls in this exact format:
[
  {{"tool": "word_count", "args": ["hello world"], "reasoning": "Counting words in the input string."}},
  {{"tool": "letter_count", "args": ["previous"], "reasoning": "Counting letters in the previous result."}}
]

RULES:
1. Start your response with [ and end with ]
2. No markdown code blocks (no ```)
3. No extra text before or after the JSON
4. Always include a "reasoning" field for each step
5. Use "previous" in args to reference the previous step result
"""

    # Call LLM to create plan using agent-specific config
    response = await client.chat.completions.create(
        model=STRING_AGENT_CONFIG["model"],
        temperature=STRING_AGENT_CONFIG["temperature"],
        max_tokens=STRING_AGENT_CONFIG["max_tokens"],
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": "Count words in 'hello world'"},
            {"role": "assistant", "content": '[{"tool": "word_count", "args": ["hello world"], "reasoning": "Counting words"}]'},
            {"role": "user", "content": task}
        ]
    )

    # Parse and execute the plan
    raw_plan = response.choices[0].message.content
    plan = parse_plan_from_response(raw_plan)
    result = await execute_tool_plan(plan, agent="string")

    print(f"[String Agent] Result: {result}")

    return StringAgentResult(
        final_result=str(result.get("final_result", "")),
        steps=json.dumps(result.get("steps", [])),
        error=result.get("error", "")
    )