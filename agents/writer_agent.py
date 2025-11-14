"""
This module defines the writer_agent, which can create written content based on research.
"""

import json
import sys
from pathlib import Path
import flyte

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import tools to register them
import tools.writing_tools

from utils.decorators import agent, agent_tools
from utils.plan_executor import execute_plan
from dataclasses import dataclass
from config import base_env

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class WriterAgentResult:
    """Result from writer agent execution"""
    final_result: str
    steps: str  # JSON string of steps taken
    error: str = ""  # Empty if no error


# ----------------------------------
# Writer Agent Task Environment
# ----------------------------------
env = base_env


@env.task
@agent("writer")
async def writer_agent(task: str) -> WriterAgentResult:
    """
    Writer agent that creates content based on research and requirements.

    Args:
        task (str): The writing task to perform.

    Returns:
        WriterAgentResult: The written content and the steps taken.
    """
    print(f"[Writer Agent] Processing: {task}")

    toolset = agent_tools["writer"]
    tool_list = "\n".join([f"{name}: {fn.__doc__.strip()}" for name, fn in toolset.items()])
    system_msg = f"""
You are a content writing agent. You can create written content based on topics and research.

Tools:
{tool_list}

CRITICAL: You must respond with ONLY a valid JSON array, nothing else. No markdown, no explanations.
Return a JSON array of tool calls in this exact format:
[
  {{"tool": "write_content", "args": ["AI and Machine Learning", "Research context here...", 300], "reasoning": "Creating initial content draft based on research"}}
]

RULES:
1. Start your response with [ and end with ]
2. No markdown code blocks (no ```)
3. No extra text before or after the JSON
4. Always include a "reasoning" field for each step
5. Use write_content to create the main content
6. Use add_section to add additional sections if needed
"""

    memory_log = []  # No memory persistence for now
    result = await execute_plan(task, agent="writer", system_msg=system_msg)

    print(f"[Writer Agent] Result: {result}")

    return WriterAgentResult(
        final_result=str(result.get("final_result", "")),
        steps=json.dumps(result.get("steps", [])),
        error=result.get("error", "")
    )
