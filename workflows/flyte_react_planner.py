"""
Hybrid ReAct + Planner workflow - Best of both worlds!

This workflow combines:
- ReAct's adaptive reasoning (react to results, change strategy)
- Planner's parallel execution (run independent tasks simultaneously)

At each iteration:
1. Reason about the current state
2. Create a MINI-PLAN with potentially multiple steps
3. Execute the plan with parallel execution where possible
4. Reflect on ALL results
5. Decide: Continue or Done?

This is more efficient than pure ReAct (no waiting for sequential tasks)
and more adaptive than pure planner (can adjust based on results)!

Usage:
    python -m workflows.flyte_react_planner --local --request "Your goal here"
"""

import sys
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, field
import flyte
import asyncio
import json

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import agents and planner types
from agents.math_agent import math_agent
from agents.string_agent import string_agent
from agents.web_search_agent import web_search_agent
from agents.code_agent import code_agent
from agents.weather_agent import weather_agent
from agents.planner_agent import AgentStep
from config import base_env, OPENAI_API_KEY
from utils.logger import Logger
from openai import AsyncOpenAI

# Initialize logger
logger = Logger(path="react_planner_trace_log.jsonl", verbose=False)

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class HybridIteration:
    """Single iteration of the hybrid workflow"""
    iteration_number: int
    thought: str                      # Reasoning about what to do
    plan_steps: List[AgentStep]       # Mini-plan for this iteration
    step_results: List[Dict]          # Results from each step
    reflection: str                   # Analysis of all results
    goal_achieved: bool = False


@dataclass
class HybridResult:
    """Final result from hybrid workflow"""
    goal: str
    iterations: List[HybridIteration]
    final_answer: str
    total_iterations: int
    total_steps_executed: int
    goal_achieved: bool


# ----------------------------------
# Hybrid ReAct + Planner Orchestrator
# ----------------------------------

env = base_env

@env.task
async def hybrid_workflow(user_goal: str, max_iterations: int = 10) -> HybridResult:
    """
    Hybrid ReAct + Planner workflow.

    At each iteration, the agent:
    1. Thinks about what needs to be done
    2. Creates a mini-plan (1-5 steps) that can execute in parallel
    3. Executes the plan efficiently
    4. Reflects on results
    5. Decides if goal is achieved or continues

    Args:
        user_goal: The user's goal to accomplish
        max_iterations: Maximum iterations to prevent infinite loops

    Returns:
        HybridResult: Complete execution trace and final answer
    """
    print("=" * 80)
    print(f"HYBRID ReAct + Planner WORKFLOW - Goal: {user_goal}")
    print("=" * 80)

    # Initialize OpenAI client
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    # Track execution state
    iterations: List[HybridIteration] = []
    context_history = []
    goal_achieved = False
    total_steps_executed = 0

    available_agents = ["math", "string", "web_search", "code", "weather"]

    for iter_num in range(1, max_iterations + 1):
        print(f"\n{'='*80}")
        print(f"ITERATION {iter_num}")
        print(f"{'='*80}")

        # Build context from previous iterations
        if context_history:
            history_text = "\n\n".join([
                f"Iteration {h['iteration']}:\n"
                f"Thought: {h['thought']}\n"
                f"Executed {len(h['plan_steps'])} step(s)\n"
                f"Results: {h['summary']}\n"
                f"Reflection: {h['reflection']}"
                for h in context_history[-2:]  # Last 2 iterations
            ])
        else:
            history_text = "No previous iterations."

        # Ask agent to reason and create a mini-plan
        system_msg = f"""You are a hybrid ReAct + Planner agent.

Goal: {user_goal}

Available agents:
{chr(10).join([f"- {agent}" for agent in available_agents])}

Previous iterations:
{history_text}

Your task: Think about what to do next, then create a MINI-PLAN.

Respond in JSON format:
{{
  "thought": "Your reasoning about the current state and what's needed",
  "goal_achieved": false,
  "plan_steps": [
    {{"agent": "agent_name", "task": "specific task", "dependencies": []}},
    {{"agent": "agent_name", "task": "another task", "dependencies": []}}
  ],
  "final_answer": null
}}

OR if the goal is achieved:
{{
  "thought": "Why the goal is now achieved",
  "goal_achieved": true,
  "plan_steps": [],
  "final_answer": "The complete answer to the user's goal"
}}

MINI-PLAN RULES:
- Include 1-5 steps maximum per iteration
- Steps with empty dependencies [] run in PARALLEL
- Use dependencies: [0] to make step 1 wait for step 0
- Be strategic: group independent tasks to leverage parallelism
- You can do more steps in the NEXT iteration if needed

IMPORTANT:
- Think step-by-step about the current state
- Only set goal_achieved=true when you have the final answer
- Use dependencies wisely to enable parallelism
"""

        print("\n[Hybrid] Reasoning and planning...")
        response = await client.chat.completions.create(
            model="gpt-4o",
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Goal: {user_goal}\n\nWhat should we do in this iteration?"}
            ]
        )

        # Parse decision with robust JSON extraction
        raw_response = response.choices[0].message.content

        try:
            decision = json.loads(raw_response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_response, re.DOTALL)
            if json_match:
                decision = json.loads(json_match.group(1))
            else:
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_response, re.DOTALL)
                if json_match:
                    decision = json.loads(json_match.group(0))
                else:
                    print(f"[ERROR] Could not parse JSON from response: {raw_response}")
                    raise ValueError(f"LLM did not return valid JSON. Response: {raw_response[:200]}")

        thought = decision["thought"]
        goal_achieved = decision["goal_achieved"]

        print(f"\n💭 Thought: {thought}")

        # Check if goal is achieved
        if goal_achieved:
            final_answer = decision["final_answer"]
            print(f"\n✅ Goal achieved!")
            print(f"📝 Final answer: {final_answer}")

            # Record this iteration
            iterations.append(HybridIteration(
                iteration_number=iter_num,
                thought=thought,
                plan_steps=[],
                step_results=[],
                reflection="Goal achieved",
                goal_achieved=True
            ))
            break

        # Parse the mini-plan
        plan_steps = [
            AgentStep(
                agent=step["agent"],
                task=step["task"],
                dependencies=step.get("dependencies", [])
            )
            for step in decision["plan_steps"]
        ]

        print(f"\n📋 Mini-plan: {len(plan_steps)} step(s)")
        for i, step in enumerate(plan_steps):
            deps_str = f" (depends on: {step.dependencies})" if step.dependencies else " (parallel)"
            print(f"  Step {i}: {step.agent} - {step.task}{deps_str}")

        # Execute the mini-plan with dependency-aware parallelism
        print(f"\n🚀 Executing mini-plan...")
        step_results = await execute_mini_plan(plan_steps)
        total_steps_executed += len(plan_steps)

        # Show results
        print(f"\n📊 Results:")
        for i, result in enumerate(step_results):
            print(f"  Step {i}: {result['observation'][:100]}{'...' if len(result['observation']) > 100 else ''}")

        # Reflect on ALL results
        results_summary = "\n".join([
            f"Step {i} ({r['agent']}): {r['observation']}"
            for i, r in enumerate(step_results)
        ])

        reflection_prompt = f"""Reflect on the results of this iteration:

Goal: {user_goal}
Thought: {thought}
Steps executed: {len(step_results)}

Results:
{results_summary}

Provide a brief reflection (2-3 sentences):
1. What did we learn from these results?
2. Are we closer to the goal?
3. What should we do next (or are we done)?"""

        reflection_response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=200,
            messages=[
                {"role": "user", "content": reflection_prompt}
            ]
        )

        reflection = reflection_response.choices[0].message.content.strip()
        print(f"\n🤔 Reflection: {reflection}")

        # Record this iteration
        iteration_record = HybridIteration(
            iteration_number=iter_num,
            thought=thought,
            plan_steps=plan_steps,
            step_results=step_results,
            reflection=reflection,
            goal_achieved=False
        )
        iterations.append(iteration_record)

        # Add to context history
        context_history.append({
            "iteration": iter_num,
            "thought": thought,
            "plan_steps": plan_steps,
            "summary": results_summary[:300],
            "reflection": reflection
        })

        # Log to file
        await logger.log(
            iteration=iter_num,
            thought=thought,
            steps_count=len(plan_steps),
            results=results_summary[:500],
            reflection=reflection
        )

    # If we exited the loop without achieving goal
    if not goal_achieved:
        print(f"\n⚠️  Reached maximum iterations ({max_iterations}) without achieving goal")
        final_answer = f"Could not achieve goal in {max_iterations} iterations. Last results: {results_summary[:200]}"

    print(f"\n{'='*80}")
    print(f"WORKFLOW COMPLETE")
    print(f"Iterations: {len(iterations)}")
    print(f"Total steps executed: {total_steps_executed}")
    print(f"{'='*80}")

    return HybridResult(
        goal=user_goal,
        iterations=iterations,
        final_answer=final_answer,
        total_iterations=len(iterations),
        total_steps_executed=total_steps_executed,
        goal_achieved=goal_achieved
    )


async def execute_mini_plan(plan_steps: List[AgentStep]) -> List[Dict]:
    """
    Execute a mini-plan with dependency-aware parallel execution.

    This is similar to the dynamic workflow's orchestrator but simplified
    for a single iteration of the hybrid workflow.
    """
    completed_results: Dict[int, Dict] = {}
    pending_steps = list(enumerate(plan_steps))

    while pending_steps:
        # Find steps that can execute now (dependencies satisfied)
        ready_steps = []
        remaining_steps = []

        for step_idx, step in pending_steps:
            deps_satisfied = all(dep_idx in completed_results for dep_idx in step.dependencies)

            if deps_satisfied:
                ready_steps.append((step_idx, step))
            else:
                remaining_steps.append((step_idx, step))

        if not ready_steps:
            print("[ERROR] No steps ready but pending steps remain (circular dependency?)")
            break

        print(f"  Executing {len(ready_steps)} step(s) in parallel...")

        # Execute ready steps in parallel
        async def execute_step(step_idx: int, step: AgentStep) -> tuple:
            # If this step has dependencies, augment task with results
            task = step.task
            if step.dependencies:
                dep_results = []
                for dep_idx in step.dependencies:
                    dep_result = completed_results[dep_idx]
                    dep_results.append(f"Result from step {dep_idx}: {dep_result['observation']}")
                task = f"Context:\n" + "\n".join(dep_results) + f"\n\nYour task: {task}"

            # Route to appropriate agent
            if step.agent == "math":
                result = await math_agent(task)
                observation = result.final_result
            elif step.agent == "string":
                result = await string_agent(task)
                observation = result.final_result
            elif step.agent == "web_search":
                result = await web_search_agent(task)
                observation = getattr(result, 'summary', result.final_result)
            elif step.agent == "code":
                result = await code_agent(task)
                observation = result.final_result
            elif step.agent == "weather":
                result = await weather_agent(task)
                observation = result.final_result
            else:
                observation = f"ERROR: Unknown agent '{step.agent}'"

            return step_idx, {
                "agent": step.agent,
                "task": step.task,
                "observation": observation
            }

        # Execute in parallel
        results = await asyncio.gather(*[execute_step(idx, step) for idx, step in ready_steps])

        # Store completed results
        for step_idx, result in results:
            completed_results[step_idx] = result

        # Update pending steps
        pending_steps = remaining_steps

    # Return results in original order
    return [completed_results[i] for i in range(len(plan_steps))]


# ----------------------------------
# CLI Entry Point
# ----------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Hybrid ReAct + Planner workflow",
        epilog="Example: python -m workflows.flyte_react_planner --local --request 'Find GDP of France and Germany, compare them'"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run workflow locally using flyte.init() instead of remote execution"
    )
    parser.add_argument(
        "--request",
        type=str,
        required=True,
        help="Your goal/request"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum iterations (default: 10)"
    )

    args = parser.parse_args()

    # Initialize Flyte based on local/remote flag
    if args.local:
        print("Running workflow LOCALLY with flyte.init()")
        flyte.init()
    else:
        print("Running workflow REMOTELY with flyte.init_from_config()")
        flyte.init_from_config(".flyte/config.yaml")

    print(f"\n=== Hybrid ReAct + Planner Workflow ===")
    print(f"Goal: {args.request}")
    print(f"Max iterations: {args.max_iterations}\n")

    # Execute the workflow
    execution = flyte.run(
        hybrid_workflow,
        user_goal=args.request,
        max_iterations=args.max_iterations
    )

    print(f"\n{'='*80}")
    print(f"Execution: {execution.name}")
    print(f"URL: {execution.url}")
    print("Click the link above to view execution details in the Flyte UI")
    print(f"{'='*80}\n")