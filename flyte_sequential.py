"""
Sequential workflow for content creation pipeline.
This workflow demonstrates a real-world use case: researching a topic, writing content,
and then editing/improving that content.

Pipeline: Web Search -> Writer -> Editor

Takes a single topic as input and produces polished content as output.
"""

import sys
from pathlib import Path
from dataclasses import dataclass
import flyte

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import agents
from agents.web_search_agent import web_search_agent, WebSearchAgentResult
from agents.writer_agent import writer_agent, WriterAgentResult
from agents.editor_agent import editor_agent, EditorAgentResult
from config import base_env

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class ContentCreationResult:
    """Result from content creation pipeline"""
    research_summary: str
    draft_content: str
    final_content: str
    editor_feedback: str


# ----------------------------------
# Content Creation Sequential Workflow
# ----------------------------------

@base_env.task
async def content_creation_pipeline(topic: str) -> ContentCreationResult:
    """
    Sequential content creation workflow that takes a topic and produces polished content.

    Pipeline:
    1. Research: Search the web for information about the topic
    2. Write: Create initial content draft based on research
    3. Edit: Review and improve the content

    Args:
        topic (str): The topic to create content about

    Returns:
        ContentCreationResult: The final polished content and intermediate results
    """
    print(f"\n{'='*60}")
    print(f"[Content Pipeline] Starting content creation for: {topic}")
    print(f"{'='*60}\n")

    # Step 1: Research the topic
    print(f"[Content Pipeline] Step 1/3: Researching '{topic}'...")
    research_task = f"Search for recent information about {topic}"
    research_result = await web_search_agent(research_task)
    research_summary = research_result.final_result
    print(f"[Content Pipeline] Research complete: {len(research_summary)} characters")
    print(f"[Content Pipeline] Research preview: {research_summary[:150]}...")

    # Step 2: Write content based on research
    print(f"\n[Content Pipeline] Step 2/3: Writing content about '{topic}'...")
    writing_task = f"Write content about {topic}. Use this research: {research_summary}"
    draft_result = await writer_agent(writing_task)
    draft_content = draft_result.final_result
    print(f"[Content Pipeline] Draft complete: {len(draft_content)} characters")
    print(f"[Content Pipeline] Draft preview: {draft_content[:150]}...")

    # Step 3: Edit and improve the content
    print(f"\n[Content Pipeline] Step 3/3: Editing and improving content...")
    editing_task = f"Review and improve this content: {draft_content}"
    editor_result = await editor_agent(editing_task)
    final_content = editor_result.final_result
    print(f"[Content Pipeline] Editing complete: {len(final_content)} characters")

    print(f"\n{'='*60}")
    print(f"[Content Pipeline] Pipeline complete!")
    print(f"{'='*60}\n")

    return ContentCreationResult(
        research_summary=research_summary,
        draft_content=draft_content,
        final_content=final_content,
        editor_feedback="Content reviewed and improved"
    )


# ----------------------------------
# Local Execution Helper
# ----------------------------------

if __name__ == "__main__":
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Flyte content creation pipeline")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run workflow locally using flyte.init() instead of remote execution"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="Flyte workflow orchestration",
        help="Topic to create content about"
    )
    args = parser.parse_args()

    # Initialize Flyte based on local/remote flag
    if args.local:
        print("Running workflow LOCALLY with flyte.init()")
        flyte.init()
    else:
        print("Running workflow REMOTELY with flyte.init_from_config()")
        flyte.init_from_config(".flyte/config.yaml")

    print(f"\n=== Content Creation Pipeline ===")
    print(f"Topic: {args.topic}\n")

    execution = flyte.run(
        content_creation_pipeline,
        topic=args.topic
    )

    print(f"\n{'='*60}")
    print(f"Execution: {execution.name}")
    print(f"URL: {execution.url}")
    print("Click the link above to view execution details in the Flyte UI")
    print(f"{'='*60}\n")
