"""
Dynamic workflow example using the planner agent for intelligent task routing.
This workflow demonstrates how the planner can dynamically choose which agent to use for different tasks.

Each agent (planner, math, string) is now a standalone Flyte task with its own TaskEnvironment,
allowing independent scaling, resource allocation, and container configuration.
"""

import sys
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
import flyte
import asyncio

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

    # Step 2: Execute agent tasks with dependency-aware parallelism
    # Store completed results indexed by step number
    completed_results: Dict[int, AgentExecution] = {}

    # Track which steps are ready to execute (no pending dependencies)
    pending_steps = list(enumerate(planner_decision.steps))

    while pending_steps:
        # Find all steps that can execute now (dependencies satisfied)
        ready_steps = []
        remaining_steps = []

        for step_idx, step in pending_steps:
            # Check if all dependencies are completed
            deps_satisfied = all(dep_idx in completed_results for dep_idx in step.dependencies)

            if deps_satisfied:
                ready_steps.append((step_idx, step))
            else:
                remaining_steps.append((step_idx, step))

        if not ready_steps:
            # This shouldn't happen with valid dependency graphs, but handle it gracefully
            print("[Orchestrator] ERROR: No steps ready to execute, but pending steps remain (circular dependency?)")
            break

        print(f"[Orchestrator] Executing {len(ready_steps)} step(s) in parallel...")

        # Execute all ready steps in parallel
        async def execute_step(step_idx: int, step: AgentStep) -> tuple:
            """Execute a single agent step"""
            print(f"[Orchestrator]   Step {step_idx}: Calling {step.agent} agent...")
            print(f"[Orchestrator]     Task: {step.task}")

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

            print(f"[Orchestrator]   Step {step_idx} completed: {result_summary}")

            return step_idx, AgentExecution(
                agent=step.agent,
                task=step.task,
                result_summary=result_summary,
                error=error
            )

        # Execute all ready steps concurrently
        results = await asyncio.gather(*[execute_step(idx, step) for idx, step in ready_steps])

        # Store completed results
        for step_idx, execution in results:
            completed_results[step_idx] = execution

        # Update pending steps
        pending_steps = remaining_steps

    # Convert to list in original order
    agent_executions = [completed_results[i] for i in range(len(planner_decision.steps))]

    # Collect final results
    final_results = []
    for execution in agent_executions:
        if execution.result_summary and not execution.error:
            final_results.append(f"{execution.agent}: {execution.result_summary}")

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
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Flyte dynamic workflow")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run workflow locally using flyte.init() instead of remote execution"
    )
    args = parser.parse_args()

    # Initialize Flyte based on local/remote flag
    if args.local:
        print("Running workflow LOCALLY with flyte.init()")
        flyte.init()
    else:
        print("Running workflow REMOTELY with flyte.init_from_config()")
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
    # user_request = "Write Python code to calculate the first 10 Fibonacci numbers"

    # Parallel execution test (independent tasks)
    # user_request = "Calculate 10 factorial, count words in 'AI is transforming software', and search for latest Flyte 2.0 features"

    # Dependency test (sequential tasks where later depends on earlier)
    # user_request = "Calculate 5 times 8 and 20 + 5, then add those two results together"
    user_request = """"Calculate 5 factorial, 10 times 10, count words in 'hello world', 
  count letters in 'test', search for 'Python async', search for 'Flyte workflows', 
  calculate 3 plus 7, count words in 'agent orchestration system', then write Python 
  code to sum all the numeric results and concatenate all the text results"""

    # Mixed parallel + dependencies test
    # user_request = "Calculate 5 factorial and count letters in 'hello', then write Python code to multiply those two results together"

    execution = flyte.run(
        execute_dynamic_task,
        user_request=user_request
    )

    print(f"\n{'='*60}")
    print(f"Execution: {execution.name}")
    print(f"URL: {execution.url}")
    print("Click the link above to view execution details in the Flyte UI 👆")
    print(f"{'='*60}\n")