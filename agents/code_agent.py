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
    system_msg = (
        "You are a code execution agent. You can write and execute Python code.\n"
        "For each step, include a 'reasoning' field explaining why this tool is being called.\n\n"
        f"Tools:\n{tool_list}\n\n"
        "Return a list of tool calls like:\n"
        '[\n'
        '  {"tool": "execute_python", "args": ["import math\\nresult = math.factorial(5)\\nprint(result)", 5, "Calculate factorial"], '
        '"reasoning": "Using Python to calculate factorial of 5"}\n'
        ']\n'
        "IMPORTANT: Always include a 'reasoning' field explaining why this tool is being called.\n"
        "IMPORTANT: Store the final result in a variable named 'result' in your code.\n"
        "IMPORTANT: Use \\n for newlines in multi-line code strings.\n"
        "Available modules: math, json, re, datetime, statistics\n"
    )

    memory_log = []  # No memory persistence for now
    result = await execute_plan(task, agent="code", system_msg=system_msg)

    print(f"[Code Agent] Result: {result}")

    return CodeAgentResult(
        final_result=str(result.get("final_result", "")),
        steps=json.dumps(result.get("steps", [])),
        error=result.get("error", "")
    )