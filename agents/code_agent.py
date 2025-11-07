"""
This module defines the code_agent, which can write and execute Python code.
"""

import json
import sys
from pathlib import Path
import flyte

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import tools to register them
import tools.code_tools

from utils.decorators import agent, agent_tools
from utils.plan_executor import execute_plan
from dataclasses import dataclass
from config import base_env

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class CodeAgentResult:
    """Result from code agent execution"""
    final_result: str
    steps: str  # JSON string of steps taken
    error: str = ""  # Empty if no error


# ----------------------------------
# Code Agent Task Environment
# ----------------------------------
env = base_env
# Future: If we need code-specific dependencies, we can extend:
# env = flyte.TaskEnvironment(
#     name="code_agent_env",
#     image=base_env.image.with_pip_packages(["numpy", "pandas"]),
#     secrets=base_env.secrets,
#     resources=flyte.Resources(cpu=2, mem="4Gi")
# )


@env.task
@agent("code")
async def code_agent(task: str) -> CodeAgentResult:
    """
    Code agent that can write and execute Python code.

    Args:
        task (str): The coding task to perform.

    Returns:
        CodeAgentResult: The result of code execution and the steps taken.
    """
    print(f"[Code Agent] Processing: {task}")

    toolset = agent_tools["code"]
    tool_list = "\n".join([f"{name}: {fn.__doc__.strip()}" for name, fn in toolset.items()])
    system_msg = f"""
You are a code execution agent. You can write and execute Python code.

Tools:
{tool_list}

CRITICAL: You MUST respond with ONLY a valid JSON array. NO exceptions, NO explanations, NO questions.
Even if the task is unclear, make your best attempt and return JSON.

Return a JSON array of tool calls in this exact format:
[
  {{"tool": "execute_python", "args": ["import math\\nresult = math.factorial(5)\\nprint(result)", 5, "Calculate factorial"], "reasoning": "Using Python to calculate factorial of 5"}}
]

STRICT RULES - NO EXCEPTIONS:
1. ALWAYS start your response with [ and end with ]
2. NEVER use markdown code blocks (no ```)
3. NEVER add extra text before or after the JSON
4. NEVER ask questions - just return JSON
5. Always include a "reasoning" field for each step
6. Store the final result in a variable named "result" in your code
7. Use \\n for newlines in multi-line code strings

Available modules: math, json, re, datetime, statistics
"""

    memory_log = []  # No memory persistence for now
    result = await execute_plan(task, agent="code", system_msg=system_msg)

    print(f"[Code Agent] Result: {result}")

    return CodeAgentResult(
        final_result=str(result.get("final_result", "")),
        steps=json.dumps(result.get("steps", [])),
        error=result.get("error", "")
    )