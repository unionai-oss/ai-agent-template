"""
Reflexion workflow - Iterative improvement through critique and refinement.

This workflow implements the Reflexion pattern where the system:
1. Researches a topic (web search)
2. Writes initial content (writer agent)
3. Critiques the content (critic LLM)
4. Revises based on critique (editor agent)
5. Repeats until quality threshold is met or max iterations reached

This is perfect for content creation where quality improvement through
iteration is more important than speed.

Usage:
    python -m workflows.flyte_reflexion --local --topic "Your topic here"
"""

import sys
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
import flyte
import asyncio
import json

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import agents
from agents.web_search_agent import web_search_agent
from agents.writer_agent import writer_agent
from agents.editor_agent import editor_agent
from config import base_env, OPENAI_API_KEY
from utils.logger import Logger
from openai import AsyncOpenAI

# Initialize logger
logger = Logger(path="reflexion_trace_log.jsonl", verbose=False)

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class ReflexionIteration:
    """Single iteration of the reflexion workflow"""
    iteration_number: int
    content: str                # Current version of content
    critique: str               # Critique of this version
    quality_score: float        # 0-10 score
    improvements_made: str      # What was improved
    meets_threshold: bool = False

@dataclass
class ReflexionResult:
    """Final result from reflexion workflow"""
    topic: str
    research_summary: str       # Initial research
    iterations: List[ReflexionIteration]
    final_content: str
    total_iterations: int
    final_quality_score: float
    quality_threshold_met: bool


# ----------------------------------
# Reflexion Workflow
# ----------------------------------

env = base_env

@env.task
async def reflexion_workflow(
    topic: str,
    quality_threshold: float = 8.0,
    max_iterations: int = 5
) -> ReflexionResult:
    """
    Reflexion workflow that iteratively improves content through critique.

    Args:
        topic: The topic to write about
        quality_threshold: Quality score (0-10) to aim for
        max_iterations: Maximum refinement iterations

    Returns:
        ReflexionResult: Complete execution trace and final content
    """
    print("=" * 80)
    print(f"REFLEXION WORKFLOW - Topic: {topic}")
    print(f"Quality Threshold: {quality_threshold}/10")
    print("=" * 80)

    # Initialize OpenAI client
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    # Track execution state
    iterations: List[ReflexionIteration] = []
    quality_threshold_met = False

    # ----------------------------------
    # PHASE 1: Research
    # ----------------------------------
    print(f"\n{'='*80}")
    print(f"PHASE 1: RESEARCH")
    print(f"{'='*80}")

    research_task = f"Search for information about: {topic}"
    print(f"\n📚 Researching: {topic}")

    research_result = await web_search_agent(research_task)
    research_summary = research_result.summary

    print(f"✅ Research complete: {len(research_summary)} characters")
    print(f"Preview: {research_summary[:200]}...")

    # ----------------------------------
    # PHASE 2: Initial Draft
    # ----------------------------------
    print(f"\n{'='*80}")
    print(f"PHASE 2: INITIAL DRAFT")
    print(f"{'='*80}")

    writing_task = f"""Write a blog post about: {topic}

Research context:
{research_summary}

Requirements:
- Engaging title
- Well-structured with sections
- 300-500 words
- Clear and informative
"""

    print(f"\n✍️  Writing initial draft...")
    draft_result = await writer_agent(writing_task)
    current_content = draft_result.final_result

    print(f"✅ Draft complete: {len(current_content)} characters")
    print(f"\nDraft preview:\n{current_content[:300]}...\n")

    # ----------------------------------
    # PHASE 3: Iterative Refinement
    # ----------------------------------
    print(f"\n{'='*80}")
    print(f"PHASE 3: ITERATIVE REFINEMENT")
    print(f"{'='*80}")

    for iter_num in range(1, max_iterations + 1):
        print(f"\n{'='*80}")
        print(f"ITERATION {iter_num}")
        print(f"{'='*80}")

        # Critique the current content
        critique_prompt = f"""You are a content quality critic. Evaluate this content:

{current_content}

Evaluate on these criteria (rate 0-10 for each):
1. Clarity - Is it easy to understand?
2. Structure - Is it well-organized?
3. Engagement - Is it interesting to read?
4. Completeness - Does it cover the topic well?
5. Accuracy - Is the information correct?

Respond in JSON format:
{{
  "overall_score": 8.5,
  "clarity_score": 9.0,
  "structure_score": 8.0,
  "engagement_score": 8.5,
  "completeness_score": 8.0,
  "accuracy_score": 9.0,
  "strengths": ["Clear writing", "Good structure"],
  "weaknesses": ["Could be more engaging", "Missing examples"],
  "specific_improvements": "Add concrete examples. Use more vivid language in the introduction.",
  "meets_threshold": true
}}
"""

        print(f"\n🔍 Critiquing content...")

        critique_response = await client.chat.completions.create(
            model="gpt-4o",
            temperature=0.3,
            messages=[
                {"role": "user", "content": critique_prompt}
            ]
        )

        # Parse critique with robust JSON extraction
        raw_critique = critique_response.choices[0].message.content

        try:
            critique_data = json.loads(raw_critique)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_critique, re.DOTALL)
            if json_match:
                critique_data = json.loads(json_match.group(1))
            else:
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_critique, re.DOTALL)
                if json_match:
                    critique_data = json.loads(json_match.group(0))
                else:
                    print(f"[ERROR] Could not parse critique JSON: {raw_critique}")
                    raise ValueError(f"LLM did not return valid JSON")

        quality_score = critique_data["overall_score"]
        strengths = critique_data.get("strengths", [])
        weaknesses = critique_data.get("weaknesses", [])
        specific_improvements = critique_data.get("specific_improvements", "")

        print(f"\n📊 Quality Score: {quality_score}/10")
        print(f"✅ Strengths: {', '.join(strengths)}")
        print(f"⚠️  Weaknesses: {', '.join(weaknesses)}")
        print(f"💡 Improvements: {specific_improvements}")

        # Format critique for storage
        critique_text = f"""Quality Score: {quality_score}/10

Strengths: {', '.join(strengths)}
Weaknesses: {', '.join(weaknesses)}

Specific Improvements:
{specific_improvements}"""

        # Check if threshold met
        meets_threshold = quality_score >= quality_threshold

        # Record this iteration
        iteration_record = ReflexionIteration(
            iteration_number=iter_num,
            content=current_content,
            critique=critique_text,
            quality_score=quality_score,
            improvements_made=specific_improvements,
            meets_threshold=meets_threshold
        )
        iterations.append(iteration_record)

        # Log to file
        await logger.log(
            iteration=iter_num,
            quality_score=quality_score,
            strengths=strengths,
            weaknesses=weaknesses,
            improvements=specific_improvements
        )

        # Check if we've met the threshold
        if meets_threshold:
            print(f"\n✅ Quality threshold met! ({quality_score} >= {quality_threshold})")
            quality_threshold_met = True
            break

        # If not at max iterations, revise the content
        if iter_num < max_iterations:
            print(f"\n🔄 Revising content based on critique...")

            revision_task = f"""Review and improve this content:

{current_content}

Critique:
{critique_text}

Apply the suggested improvements to enhance the content. Maintain the overall structure and key information, but address all weaknesses mentioned in the critique.

Return ONLY the improved content."""

            revision_result = await editor_agent(revision_task)
            current_content = revision_result.final_result

            print(f"✅ Revision complete: {len(current_content)} characters")

    # If we exited the loop without meeting threshold
    if not quality_threshold_met:
        print(f"\n⚠️  Reached maximum iterations ({max_iterations}) without meeting threshold")
        print(f"Final score: {quality_score}/{quality_threshold}")

    print(f"\n{'='*80}")
    print(f"WORKFLOW COMPLETE")
    print(f"Iterations: {len(iterations)}")
    print(f"Final Quality Score: {quality_score}/10")
    print(f"Threshold Met: {quality_threshold_met}")
    print(f"{'='*80}")

    print(f"\n{'='*80}")
    print(f"FINAL CONTENT:")
    print(f"{'='*80}")
    print(current_content)
    print(f"{'='*80}\n")

    return ReflexionResult(
        topic=topic,
        research_summary=research_summary,
        iterations=iterations,
        final_content=current_content,
        total_iterations=len(iterations),
        final_quality_score=quality_score,
        quality_threshold_met=quality_threshold_met
    )


# ----------------------------------
# CLI Entry Point
# ----------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Reflexion workflow - iterative content improvement",
        epilog="Example: python -m workflows.flyte_reflexion --local --topic 'Benefits of async programming in Python'"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run workflow locally using flyte.init() instead of remote execution"
    )
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help="The topic to write about"
    )
    parser.add_argument(
        "--quality-threshold",
        type=float,
        default=8.0,
        help="Quality score threshold (0-10) to aim for (default: 8.0)"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum refinement iterations (default: 5)"
    )

    args = parser.parse_args()

    # Initialize Flyte based on local/remote flag
    if args.local:
        print("Running workflow LOCALLY with flyte.init()")
        flyte.init()
    else:
        print("Running workflow REMOTELY with flyte.init_from_config()")
        flyte.init_from_config(".flyte/config.yaml")

    print(f"\n=== Reflexion Content Creation Workflow ===")
    print(f"Topic: {args.topic}")
    print(f"Quality Threshold: {args.quality_threshold}/10")
    print(f"Max Iterations: {args.max_iterations}\n")

    # Execute the workflow
    execution = flyte.run(
        reflexion_workflow,
        topic=args.topic,
        quality_threshold=args.quality_threshold,
        max_iterations=args.max_iterations
    )

    print(f"\n{'='*80}")
    print(f"Execution: {execution.name}")
    print(f"URL: {execution.url}")
    print("Click the link above to view execution details in the Flyte UI")
    print(f"{'='*80}\n")