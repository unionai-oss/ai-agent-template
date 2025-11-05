"""
Dynamic workflow example using the planner agent for intelligent task routing.
This workflow demonstrates how the planner can dynamically choose which agent to use for different tasks.

Each agent (planner, math, string) is now a standalone Flyte task with its own TaskEnvironment,
allowing independent scaling, resource allocation, and container configuration.
"""

import sys
from pathlib import Path
from typing import List
from dataclasses import dataclass
import flyte

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import agents (they are now Flyte tasks with their own environments)
from agents.planner_agent import planner_agent, PlannerDecision, AgentStep
from agents.math_agent import math_agent, MathAgentResult
from agents.string_agent import string_agent, StringAgentResult
from agents.web_search_agent import web_search_agent, WebSearchAgentResult
from agents.code_agent import code_agent, CodeAgentResult
from config import base_env

# ----------------------------------
# Data Models for Orchestrator
# ----------------------------------

@dataclass
class AgentExecution:
    """Single agent execution with its result"""
    agent: str
    task: str
    result_summary: str
    error: str = ""


@dataclass
class TaskResult:
    """Final result from dynamic task execution"""
    planner_decision_summary: str
    agent_executions: List[AgentExecution]
    final_result: str  # Combined final result


# ----------------------------------
# Orchestrator Task Environment
# ----------------------------------
env = base_env
# orchestrator_env = flyte.TaskEnvironment(
#     name="orchestrator_env",
#     image=flyte.Image.from_debian_base().with_requirements("requirements.txt"),
#     secrets=[
#         flyte.Secret(key="OPENAI_API_KEY", as_env_var="OPENAI_API_KEY"),
#     ],
# )


# ----------------------------------
# Main Orchestration Task
# ----------------------------------

@env.task
async def execute_dynamic_task(user_request: str) -> TaskResult:
    """
    Execute a task dynamically by first asking the planner which agent(s) to use.
    This is the main orchestration task that calls other agent tasks sequentially.

    Args:
        user_request (str): The user's request

    Returns:
        TaskResult: Combined result from all agent executions
    """
    print(f"[Orchestrator] User request: {user_request}")

    # Step 1: Call planner task to create execution plan
    print("[Orchestrator] Step 1: Calling planner agent...")
    planner_decision = await planner_agent(user_request)

    print(f"[Orchestrator] Planner created plan with {len(planner_decision.steps)} step(s)")

    # Step 2: Execute each agent task in sequence
    agent_executions = []
    final_results = []

    for i, step in enumerate(planner_decision.steps, 1):
        print(f"[Orchestrator] Step {i+1}: Calling {step.agent} agent...")
        print(f"[Orchestrator]   Task: {step.task}")

        # Route to appropriate agent task
        if step.agent == "math":
            agent_result = await math_agent(step.task)
            result_summary = agent_result.final_result
            error = agent_result.error
        elif step.agent == "string":
            agent_result = await string_agent(step.task)
            result_summary = agent_result.final_result
            error = agent_result.error
        elif step.agent == "web_search":
            agent_result = await web_search_agent(step.task)
            result_summary = agent_result.final_result
            error = agent_result.error
        elif step.agent == "code":
            agent_result = await code_agent(step.task)
            result_summary = agent_result.final_result
            error = agent_result.error
        else:
            # Fallback for unknown agent
            print(f"[Orchestrator] WARNING: Unknown agent '{step.agent}'")
            result_summary = ""
            error = f"Unknown agent: {step.agent}"

        print(f"[Orchestrator]   Result: {result_summary}")

        # Store execution
        agent_executions.append(AgentExecution(
            agent=step.agent,
            task=step.task,
            result_summary=result_summary,
            error=error
        ))

        # Collect results
        if result_summary and not error:
            final_results.append(f"{step.agent}: {result_summary}")

    # Combine all results
    combined_result = " | ".join(final_results) if final_results else "No results"
    print(f"[Orchestrator] All agents completed. Combined result: {combined_result}")

    # Create summary of planner decision
    planner_summary = f"{len(planner_decision.steps)} step(s): " + ", ".join(
        [f"{s.agent}" for s in planner_decision.steps]
    )

    return TaskResult(
        planner_decision_summary=planner_summary,
        agent_executions=agent_executions,
        final_result=combined_result
    )


# ----------------------------------
# Local Execution Helper
# ----------------------------------

if __name__ == "__main__":
    # This allows local testing but won't break remote execution
    flyte.init_from_config(".flyte/config.yaml")

    # Test prompts - uncomment the one you want to test:

    # Simple math test
    # user_request = "Calculate 5 factorial"

    # Simple string test
    # user_request = "Count the words in 'The quick brown fox jumps over the lazy dog'"

    # Multi-agent test (math + string)
    # user_request = "Calculate 5 times 3, then count the words in 'Hello World'"

    # Web search test
    # user_request = "Search for recent news about Flyte workflow orchestration"

    # Code execution test
    user_request = "Write Python code to calculate the first 10 Fibonacci numbers"

    # Complex multi-agent test (all agents)
    # user_request = "Calculate 10 factorial, count words in 'AI is transforming software', and search for latest Flyte 2.0 features"

    execution = flyte.run(
        execute_dynamic_task,
        user_request=user_request
    )

    print(f"\n{'='*60}")
    print(f"Execution: {execution.name}")
    print(f"URL: {execution.url}")
    print("Click the link above to view execution details in the Flyte UI 👆")
    print(f"{'='*60}\n")