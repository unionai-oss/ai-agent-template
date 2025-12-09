"""
Tutorial 1: Web Search Agent - Your First Tool-Using AI Agent

This is your introduction to AI agents that USE TOOLS!

What you'll learn:
- How to create a Flyte task
- How to call an AI agent
- What makes something an "agent" (tool use!)
- How agents search the web using tools

What this does:
- Takes a question as input
- AI agent uses DuckDuckGo tool to search the web
- Returns a summary of what it found

The key: The agent doesn't just generate text - it USES TOOLS to find real information!

Usage:
    # Run locally for fast iteration
    python -m workflows.websearch_agent --local --query "What is async Python?"

    # Run remotely to see in Flyte UI
    python -m workflows.websearch_agent --query "What is async Python?"
"""

import flyte
from agents.web_search_agent import web_search_agent
from config import base_env

# ----------------------------------
# The Workflow
# ----------------------------------

@base_env.task
async def simple_agent_workflow(query: str) -> str:
    """
    A simple workflow that uses an AI agent to answer questions.

    This is as simple as it gets:
    1. Take a question
    2. Ask the agent to search and answer
    3. Return the answer

    Args:
        query: The question you want answered

    Returns:
        A summary of what the agent found
    """
    print("=" * 80)
    print("🤖 SIMPLE AI AGENT WORKFLOW")
    print("=" * 80)
    print(f"\n📋 Question: {query}\n")

    # Call the web search agent
    # This is what makes it an AGENT - it uses TOOLS!
    # The LLM will decide to use the duck_duck_go tool to search the web
    print("🔍 Agent is searching the web (using DuckDuckGo tool)...")
    result = await web_search_agent(query)

    print(f"\n✅ Search complete!")
    print(f"📊 Found information: {len(result.final_result)} characters")
    print(f"\n💡 Summary of findings:\n{result.summary}\n")
    print("=" * 80)

    return result.summary


# ----------------------------------
# CLI Entry Point
# ----------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Web Search Agent - Your first tool-using AI agent",
        epilog="Example: python -m workflows.websearch_agent --local --query 'What is Flyte?'"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run locally (fast, for testing)"
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="The question you want the agent to answer"
    )

    args = parser.parse_args()

    # Initialize Flyte
    if args.local:
        print("🏠 Running LOCALLY")
        flyte.init()
    else:
        print("☁️  Running REMOTELY (check Flyte UI for results)")
        flyte.init_from_config(".flyte/config.yaml")

    print(f"\n{'='*80}")
    print("Tutorial 1: Simple AI Agent")
    print(f"{'='*80}")
    print(f"Query: {args.query}")
    print(f"Mode: {'Local' if args.local else 'Remote'}")
    print(f"{'='*80}\n")

    # Run the workflow
    execution = flyte.run(
        simple_agent_workflow,
        query=args.query
    )

    # Show execution details
    print(f"\n{'='*80}")
    print("EXECUTION COMPLETE")
    print(f"{'='*80}")

    if args.local:
        # When running locally, the execution already completed
        # The result was printed during execution
        print(f"Execution ID: {execution.name}")
        print("\n✅ Local execution finished!")
        print("   (Result was printed above during execution)")
    else:
        # When running remotely, show the UI link
        print(f"Execution ID: {execution.name}")
        print(f"View in UI: {execution.url}")
        print("\nClick the link above to see:")
        print("  • Execution graph showing the agent task")
        print("  • Logs from the web search")
        print("  • Input and output data")

    print(f"{'='*80}\n")