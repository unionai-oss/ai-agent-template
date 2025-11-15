"""
This module defines the math_agent, which is responsible for solving arithmetic, powers, and multi-step problems.
"""

import json
import sys
from pathlib import Path
import flyte


# Import tools to register them
import tools.math_tools

from utils.decorators import agent, agent_tools
from utils.plan_executor import execute_plan
from dataclasses import dataclass
from config import base_env

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class MathAgentResult:
    """Result from math agent execution"""
    final_result: str
    steps: str  # JSON string of steps taken
    error: str = ""  # Empty if no error


# ----------------------------------
# Math Agent Task Environment
# ----------------------------------
env = base_env
# env = flyte.TaskEnvironment(
#     name="math_agent_env",
#     image=flyte.Image.from_debian_base().with_requirements("requirements.txt"),
#     secrets=[
#         flyte.Secret(key="OPENAI_API_KEY", as_env_var="OPENAI_API_KEY"),
#     ],
#     # Future: Add math-specific resources
#     # resources=flyte.Resources(cpu=2, mem="4Gi")
# )


@env.task
@agent("math")
async def math_agent(task: str) -> MathAgentResult:
    """
    Math agent that processes user prompts to solve arithmetic and multi-step problems.

    Args:
        task (str): The math task to solve.

    Returns:
        MathAgentResult: The result of the computation and the steps taken.
    """
    print(f"[Math Agent] Processing: {task}")

    toolset = agent_tools["math"]
    tool_list = "\n".join([f"{name}: {fn.__doc__.strip()}" for name, fn in toolset.items()])
    system_msg = f"""
You are a math agent that can solve arithmetic, powers, and multi-step problems.

Tools:
{tool_list}

CRITICAL: You must respond with ONLY a valid JSON array, nothing else. No markdown, no explanations.
Return a JSON array of tool calls in this exact format:
[
  {{"tool": "add", "args": [2, 3], "reasoning": "Adding 2 and 3 to compute the sum."}},
  {{"tool": "multiply", "args": ["previous", 5], "reasoning": "Multiplying previous result by 5."}}
]

RULES:
1. Start your response with [ and end with ]
2. No markdown code blocks (no ```)
3. No extra text before or after the JSON
4. Always include a "reasoning" field for each step
5. Use "previous" in args to reference the previous step result
"""

    memory_log = []  # No memory persistence for now
    result = await execute_plan(task, agent="math", system_msg=system_msg)

    print(f"[Math Agent] Result: {result}")

    return MathAgentResult(
        final_result=str(result.get("final_result", "")),
        steps=json.dumps(result.get("steps", [])),
        error=result.get("error", "")
    )