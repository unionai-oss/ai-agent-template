"""
This module defines the string_agent, which is responsible for string analysis and text processing.
"""

import json
import sys
from pathlib import Path
import flyte

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import tools to register them
import tools.string_tools

from utils.decorators import agent, agent_tools
from utils.plan_executor import execute_plan
from dataclasses import dataclass
from config import base_env

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

    toolset = agent_tools["string"]
    tool_list = "\n".join([f"{name}: {fn.__doc__.strip()}" for name, fn in toolset.items()])
    system_msg = (
        "You are a string analysis agent. You can count letters, words, and analyze text.\n"
        "For each step, include a 'reasoning' field explaining why this tool is being called.\n\n"
        f"Tools:\n{tool_list}\n\n"
        "Return a list of tool calls like:\n"
        '[\n'
        '  {"tool": "word_count", "args": ["hello world"], "reasoning": "Counting words in the input string."},\n'
        '  {"tool": "letter_count", "args": ["previous"], "reasoning": "Counting letters in the previous result."}\n'
        ']\n'
        "IMPORTANT: Always include a 'reasoning' field explaining why this tool is being called."
    )

    memory_log = []  # No memory persistence for now
    result = await execute_plan(task, agent="string", system_msg=system_msg)

    print(f"[String Agent] Result: {result}")

    return StringAgentResult(
        final_result=str(result.get("final_result", "")),
        steps=json.dumps(result.get("steps", [])),
        error=result.get("error", "")
    )