"""
This module defines the editor_agent, which can review and improve written content.
"""

import json
import sys
from pathlib import Path
import flyte

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import tools to register them
import tools.editor_tools

from utils.decorators import agent, agent_tools
from utils.plan_executor import execute_plan
from dataclasses import dataclass
from config import base_env

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class EditorAgentResult:
    """Result from editor agent execution"""
    final_result: str
    steps: str  # JSON string of steps taken
    error: str = ""  # Empty if no error


# ----------------------------------
# Editor Agent Task Environment
# ----------------------------------
env = base_env


@env.task
@agent("editor")
async def editor_agent(task: str) -> EditorAgentResult:
    """
    Editor agent that reviews and improves written content.

    Args:
        task (str): The editing task to perform.

    Returns:
        EditorAgentResult: The edited content and the steps taken.
    """
    print(f"[Editor Agent] Processing: {task}")

    toolset = agent_tools["editor"]
    tool_list = "\n".join([f"{name}: {fn.__doc__.strip()}" for name, fn in toolset.items()])
    system_msg = f"""
You are a content editor agent. You can review content quality and improve written materials.

Tools:
{tool_list}

CRITICAL: You must respond with ONLY a valid JSON array, nothing else. No markdown, no explanations.
Return a JSON array of tool calls in this exact format:
[
  {{"tool": "review_content", "args": ["Content to review here..."], "reasoning": "Reviewing content quality and providing feedback"}},
  {{"tool": "improve_content", "args": ["previous", "clarity"], "reasoning": "Improving content based on review feedback"}}
]

RULES:
1. Start your response with [ and end with ]
2. No markdown code blocks (no ```)
3. No extra text before or after the JSON
4. Always include a "reasoning" field for each step
5. Use review_content first to analyze the content
6. Use improve_content to make improvements based on review
7. Use "previous" in args to reference the previous step result
"""

    memory_log = []  # No memory persistence for now
    result = await execute_plan(task, agent="editor", system_msg=system_msg)

    print(f"[Editor Agent] Result: {result}")

    return EditorAgentResult(
        final_result=str(result.get("final_result", "")),
        steps=json.dumps(result.get("steps", [])),
        error=result.get("error", "")
    )
