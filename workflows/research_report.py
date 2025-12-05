"""
DEMO: Research Report Generator with Quality Control

This is a showcase workflow that demonstrates Flyte 2.0's orchestration capabilities:
- ✨ Dynamic parallel research (fanout pattern)
- ✨ Map-reduce synthesis
- ✨ Multi-agent collaboration
- ✨ Quality-driven iteration (reflexion loop)
- ✨ Rich execution visualization

Perfect for demos because you can SEE:
- Tasks running in parallel in Flyte UI
- Tool execution traces in logs
- LLM critique iterations with quality scores
- Beautiful execution graph with branching/merging

Usage:
    python -m workflows.research_report --local --topic "async Python frameworks"
"""

import sys
from pathlib import Path
from typing import List
from dataclasses import dataclass
import flyte
import flyte.report
import asyncio
import json

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import agents
from agents.web_search_agent import web_search_agent
from agents.writer_agent import writer_agent
from agents.editor_agent import editor_agent
from config import base_env, OPENAI_API_KEY
from utils.logger import Logger
from openai import AsyncOpenAI

# Initialize logger
logger = Logger(path="research_report_log.jsonl", verbose=True)

# ----------------------------------
# Data Models
# ----------------------------------

@dataclass
class ResearchResult:
    """Result from a single research task"""
    subtopic: str
    findings: str
    summary: str

@dataclass
class QualityIteration:
    """Single quality improvement iteration"""
    iteration_number: int
    quality_score: float
    critique: str
    content: str

@dataclass
class ResearchWorkflowResult:
    """Final result from research workflow"""
    topic: str
    research_plan: str
    research_results: List[ResearchResult]
    quality_iterations: List[QualityIteration]
    final_report: str
    final_quality_score: float
    total_research_tasks: int
    total_quality_iterations: int


# ----------------------------------
# Demo Workflow
# ----------------------------------

env = base_env

@env.task(report=True)
async def research_report_workflow(
    topic: str,
    quality_threshold: float = 8.0,
    max_quality_iterations: int = 3
) -> ResearchWorkflowResult:
    """
    Demo workflow: Research Report Generator with Quality Control

    This workflow showcases:
    1. Intelligent planning (planner agent identifies subtopics)
    2. Parallel research (dynamic fanout - all searches run simultaneously)
    3. Map-reduce synthesis (combine all findings)
    4. Multi-agent collaboration (writer + editor + critic)
    5. Quality iteration (reflexion loop with visible scores)

    Args:
        topic: Main topic to research and write about
        quality_threshold: Minimum quality score (0-10) to achieve
        max_quality_iterations: Maximum refinement iterations

    Returns:
        ResearchWorkflowResult: Complete execution trace and final report
    """

    print("=" * 80)
    print("🎬 RESEARCH REPORT GENERATOR")
    print("=" * 80)
    print(f"📋 Topic: {topic}")
    print(f"🎯 Quality Target: {quality_threshold}/10")
    print("=" * 80)

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    # ----------------------------------
    # PHASE 1: INTELLIGENT PLANNING
    # ----------------------------------
    print(f"\n{'='*80}")
    print("PHASE 1: INTELLIGENT PLANNING 🧠")
    print(f"{'='*80}")

    planning_prompt = f"""Analyze this research topic and identify 3-4 specific subtopics to research:

Topic: {topic}

Create a research plan with specific subtopics that will provide comprehensive coverage.

Example - If topic is "async Python frameworks":
- Subtopic 1: asyncio library features and use cases
- Subtopic 2: Alternative frameworks (Trio, Curio)
- Subtopic 3: Performance comparison and benchmarks
- Subtopic 4: Best practices and common patterns

Respond in JSON format:
{{
  "subtopics": [
    "Subtopic 1 description",
    "Subtopic 2 description",
    "Subtopic 3 description"
  ],
  "research_approach": "Brief description of the research strategy"
}}
"""

    print("\n🤔 Planning research strategy...")

    planning_response = await client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        messages=[{"role": "user", "content": planning_prompt}]
    )

    # Parse planning response
    raw_plan = planning_response.choices[0].message.content

    try:
        plan_data = json.loads(raw_plan)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_plan, re.DOTALL)
        if json_match:
            plan_data = json.loads(json_match.group(1))
        else:
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_plan, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group(0))
            else:
                raise ValueError("Could not parse planning response")

    subtopics = plan_data["subtopics"]
    research_approach = plan_data.get("research_approach", "Comprehensive research")

    print(f"\n✅ Research plan created!")
    print(f"📊 Approach: {research_approach}")
    print(f"📚 Subtopics to research ({len(subtopics)}):")
    for i, subtopic in enumerate(subtopics, 1):
        print(f"   {i}. {subtopic}")

    await logger.log(
        phase="planning",
        subtopics_count=len(subtopics),
        subtopics=subtopics,
        approach=research_approach
    )

    # ----------------------------------
    # PHASE 2: PARALLEL RESEARCH (Dynamic Fanout!)
    # ----------------------------------
    print(f"\n{'='*80}")
    print("PHASE 2: PARALLEL RESEARCH 🔍 (Dynamic Fanout)")
    print(f"{'='*80}")
    print(f"🚀 Launching {len(subtopics)} research tasks IN PARALLEL...")
    print("   (Watch the Flyte UI to see them execute simultaneously!)")

    async def research_subtopic(subtopic: str, index: int) -> ResearchResult:
        """Research a single subtopic"""
        print(f"\n   🔎 [{index}] Starting: {subtopic[:50]}...")

        search_query = f"{topic}: {subtopic}"
        result = await web_search_agent(search_query)

        print(f"   ✅ [{index}] Complete: {len(result.summary)} chars")

        await logger.log(
            phase="research",
            subtopic_index=index,
            subtopic=subtopic,
            findings_length=len(result.final_result),
            summary_length=len(result.summary)
        )

        return ResearchResult(
            subtopic=subtopic,
            findings=result.final_result,
            summary=result.summary
        )

    research_results = await asyncio.gather(*[
        research_subtopic(subtopic, i)
        for i, subtopic in enumerate(subtopics, 1)
    ])

    print(f"\n✅ All {len(research_results)} research tasks completed!")

    # Update report with research results
    research_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px;">
            🔍 Research Results
        </h1>
        <div style="background: #ecf0f1; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h2 style="color: #34495e; margin-top: 0;">Topic: {topic}</h2>
            <p><strong>Subtopics researched:</strong> {len(research_results)}</p>
            <p><strong>Research approach:</strong> {research_approach}</p>
        </div>
"""

    for i, result in enumerate(research_results, 1):
        research_html += f"""
        <div style="background: white; border-left: 4px solid #3498db; padding: 15px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h3 style="color: #2980b9; margin-top: 0;">
                {i}. {result.subtopic}
            </h3>
            <div style="color: #555; line-height: 1.6;">
                {result.summary[:500]}{'...' if len(result.summary) > 500 else ''}
            </div>
            <p style="color: #7f8c8d; font-size: 0.9em; margin-top: 10px;">
                ✓ {len(result.findings)} characters of research data
            </p>
        </div>
"""

    research_html += "</div>"

    await flyte.report.replace.aio(research_html)
    await flyte.report.flush.aio()
    print("📊 Research results added to Flyte report!")

    # ----------------------------------
    # PHASE 3: SYNTHESIS (Map-Reduce Pattern)
    # ----------------------------------
    print(f"\n{'='*80}")
    print("PHASE 3: SYNTHESIS 🔗 (Map-Reduce)")
    print(f"{'='*80}")

    # Combine all research findings
    combined_research = "\n\n".join([
        f"## {r.subtopic}\n{r.summary}"
        for r in research_results
    ])

    print(f"📊 Combined research: {len(combined_research)} characters")
    print(f"📝 Creating structured synthesis...")

    synthesis_prompt = f"""Synthesize this research into a structured outline for a report:

Topic: {topic}

Research Findings:
{combined_research}

Create a structured outline with key points. Respond in JSON:
{{
  "main_themes": ["Theme 1", "Theme 2", "Theme 3"],
  "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
  "suggested_structure": ["Section 1", "Section 2", "Section 3"]
}}
"""

    synthesis_response = await client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        messages=[{"role": "user", "content": synthesis_prompt}]
    )

    raw_synthesis = synthesis_response.choices[0].message.content

    try:
        synthesis_data = json.loads(raw_synthesis)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_synthesis, re.DOTALL)
        if json_match:
            synthesis_data = json.loads(json_match.group(1))
        else:
            synthesis_data = {"main_themes": [], "key_findings": [], "suggested_structure": []}

    print(f"✅ Synthesis complete!")
    print(f"   Main themes: {len(synthesis_data.get('main_themes', []))}")
    print(f"   Key findings: {len(synthesis_data.get('key_findings', []))}")

    # ----------------------------------
    # PHASE 4: CONTENT GENERATION
    # ----------------------------------
    print(f"\n{'='*80}")
    print("PHASE 4: CONTENT GENERATION ✍️")
    print(f"{'='*80}")

    writing_task = f"""Write a comprehensive research report about: {topic}

Research Findings:
{combined_research}

Main Themes: {', '.join(synthesis_data.get('main_themes', []))}

Requirements:
- Engaging title
- Well-structured sections
- 500-700 words
- Include key findings from research
- Professional tone
- Proper markdown formatting
"""

    print("\n✍️  Generating initial report...")
    draft_result = await writer_agent(writing_task)
    current_content = draft_result.final_result

    print(f"✅ Draft complete: {len(current_content)} characters")
    print(f"\n📄 Draft preview:\n{current_content[:200]}...\n")

    # ----------------------------------
    # PHASE 5: QUALITY ITERATION (Reflexion Loop!)
    # ----------------------------------
    print(f"\n{'='*80}")
    print("PHASE 5: QUALITY ITERATION 🔄 (Reflexion Loop)")
    print(f"{'='*80}")
    print("   (Watch quality scores improve with each iteration!)")

    quality_iterations: List[QualityIteration] = []
    final_quality_score = 0.0

    for iter_num in range(1, max_quality_iterations + 1):
        print(f"\n{'─'*80}")
        print(f"Iteration {iter_num}/{max_quality_iterations}")
        print(f"{'─'*80}")

        # Critique the content
        critique_prompt = f"""Evaluate this research report:

{current_content}

Rate on these criteria (0-10):
1. Clarity - Easy to understand?
2. Structure - Well organized?
3. Completeness - Covers topic thoroughly?
4. Accuracy - Information correct?
5. Engagement - Interesting to read?

Respond in JSON:
{{
  "overall_score": 8.5,
  "clarity_score": 9.0,
  "structure_score": 8.0,
  "completeness_score": 8.5,
  "accuracy_score": 9.0,
  "engagement_score": 8.0,
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "specific_improvements": "Detailed suggestions..."
}}
"""

        print("🔍 Critiquing content...")

        critique_response = await client.chat.completions.create(
            model="gpt-4o",
            temperature=0.3,
            messages=[{"role": "user", "content": critique_prompt}]
        )

        raw_critique = critique_response.choices[0].message.content

        try:
            critique_data = json.loads(raw_critique)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_critique, re.DOTALL)
            if json_match:
                critique_data = json.loads(json_match.group(1))
            else:
                critique_data = {
                    "overall_score": 7.0,
                    "strengths": [],
                    "weaknesses": [],
                    "specific_improvements": "Could not parse critique"
                }

        quality_score = critique_data.get("overall_score", 7.0)
        strengths = critique_data.get("strengths", [])
        weaknesses = critique_data.get("weaknesses", [])
        improvements = critique_data.get("specific_improvements", "")

        print(f"\n📊 Quality Score: {quality_score}/10")
        print(f"✅ Strengths: {', '.join(strengths)}")
        print(f"⚠️  Weaknesses: {', '.join(weaknesses)}")
        print(f"💡 Improvements: {improvements[:100]}...")

        critique_text = f"""Score: {quality_score}/10
Strengths: {', '.join(strengths)}
Weaknesses: {', '.join(weaknesses)}
Improvements: {improvements}"""

        # Record iteration
        quality_iterations.append(QualityIteration(
            iteration_number=iter_num,
            quality_score=quality_score,
            critique=critique_text,
            content=current_content
        ))

        final_quality_score = quality_score

        await logger.log(
            phase="quality_iteration",
            iteration=iter_num,
            quality_score=quality_score,
            strengths=strengths,
            weaknesses=weaknesses
        )

        # Check if threshold met
        if quality_score >= quality_threshold:
            print(f"\n✅ Quality threshold met! ({quality_score} >= {quality_threshold})")
            break

        # If not done, revise
        if iter_num < max_quality_iterations:
            print(f"\n🔄 Revising content (target: {quality_threshold}/10)...")

            revision_task = f"""Improve this content:

{current_content}

Critique:
{critique_text}

Address all weaknesses and apply suggestions. Return ONLY the improved content.
"""

            revision_result = await editor_agent(revision_task)
            current_content = revision_result.final_result

            print(f"✅ Revision complete")

    # ----------------------------------
    # FINAL OUTPUT
    # ----------------------------------
    print(f"\n{'='*80}")
    print("🎉 WORKFLOW COMPLETE!")
    print(f"{'='*80}")
    print(f"📊 Research Tasks: {len(research_results)}")
    print(f"🔄 Quality Iterations: {len(quality_iterations)}")
    print(f"⭐ Final Quality Score: {final_quality_score}/10")
    print(f"{'='*80}")

    print(f"\n{'='*80}")
    print("📄 FINAL REPORT:")
    print(f"{'='*80}")
    print(current_content)
    print(f"{'='*80}\n")

    await logger.log(
        phase="completion",
        total_research_tasks=len(research_results),
        total_quality_iterations=len(quality_iterations),
        final_quality_score=final_quality_score,
        final_report_length=len(current_content)
    )

    # Create comprehensive final report with quality tracking
    quality_tab = flyte.report.get_tab("Quality Iterations")

    quality_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #2c3e50; border-bottom: 3px solid #e74c3c; padding-bottom: 10px;">
            📊 Quality Improvement Tracking
        </h1>
        <div style="background: #ecf0f1; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h2 style="color: #34495e; margin-top: 0;">Quality Progression</h2>
            <p><strong>Target threshold:</strong> {quality_threshold}/10</p>
            <p><strong>Total iterations:</strong> {len(quality_iterations)}</p>
            <p><strong>Final score:</strong> <span style="color: #27ae60; font-size: 1.3em; font-weight: bold;">{final_quality_score}/10</span></p>
            <p><strong>Status:</strong> {'✅ Threshold met!' if final_quality_score >= quality_threshold else '⚠️ Max iterations reached'}</p>
        </div>
"""

    for iteration in quality_iterations:
        critique_data = {}
        for line in iteration.critique.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                critique_data[key.strip()] = value.strip()

        score = iteration.quality_score
        color = "#27ae60" if score >= quality_threshold else "#e74c3c" if score < 7 else "#f39c12"

        quality_html += f"""
        <div style="background: white; border-left: 4px solid {color}; padding: 15px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h3 style="color: #2c3e50; margin-top: 0;">
                Iteration {iteration.iteration_number}
                <span style="float: right; color: {color}; font-size: 1.2em;">{score}/10</span>
            </h3>
            <div style="margin: 10px 0;">
                <p style="margin: 5px 0;"><strong>Strengths:</strong> {critique_data.get('Strengths', 'N/A')}</p>
                <p style="margin: 5px 0;"><strong>Weaknesses:</strong> {critique_data.get('Weaknesses', 'N/A')}</p>
                <p style="margin: 5px 0;"><strong>Improvements:</strong> {critique_data.get('Improvements', 'N/A')[:200]}...</p>
            </div>
        </div>
"""

    quality_html += "</div>"
    quality_tab.log(quality_html)

    # Create final report tab with markdown content
    report_tab = flyte.report.get_tab("Final Report")

    # Convert markdown to basic HTML for better display
    import re
    html_content = current_content
    # Convert # headers
    html_content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
    # Convert paragraphs
    html_content = re.sub(r'\n\n', r'</p><p>', html_content)
    html_content = f"<p>{html_content}</p>"

    final_report_html = f"""
    <div style="font-family: Georgia, serif; max-width: 800px; margin: 0 auto; padding: 20px; background: white;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; margin: -20px -20px 20px -20px;">
            <h1 style="margin: 0; font-size: 2em;">📄 Research Report</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Topic: {topic}</p>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">Quality Score: {final_quality_score}/10 | {len(research_results)} sources researched</p>
        </div>
        <div style="line-height: 1.8; color: #333;">
            {html_content}
        </div>
        <div style="margin-top: 40px; padding: 20px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #667eea;">
            <h3 style="margin-top: 0;">Workflow Statistics</h3>
            <ul style="list-style: none; padding: 0;">
                <li>🔍 <strong>Research Tasks:</strong> {len(research_results)} parallel searches</li>
                <li>📊 <strong>Quality Iterations:</strong> {len(quality_iterations)} refinement cycles</li>
                <li>⭐ <strong>Final Score:</strong> {final_quality_score}/10</li>
                <li>📝 <strong>Content Length:</strong> {len(current_content)} characters</li>
            </ul>
        </div>
    </div>
"""

    report_tab.log(final_report_html)

    await flyte.report.flush.aio()
    print("📊 Final report with quality tracking added to Flyte UI!")

    return ResearchWorkflowResult(
        topic=topic,
        research_plan=research_approach,
        research_results=research_results,
        quality_iterations=quality_iterations,
        final_report=current_content,
        final_quality_score=final_quality_score,
        total_research_tasks=len(research_results),
        total_quality_iterations=len(quality_iterations)
    )


# ----------------------------------
# CLI Entry Point
# ----------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="RESEARCH REPORT GENERATOR - Showcases Flyte 2.0 orchestration",
        epilog='Example: python -m workflows.research_report --local --topic "async Python frameworks"'
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run locally with flyte.init()"
    )
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help="Topic to research and write about"
    )
    parser.add_argument(
        "--quality-threshold",
        type=float,
        default=9.0,
        help="Quality score target (0-10, default: 8.0)"
    )
    parser.add_argument(
        "--max-quality-iterations",
        type=int,
        default=3,
        help="Maximum quality refinement iterations (default: 3)"
    )

    args = parser.parse_args()

    # Initialize Flyte
    if args.local:
        print("🏠 Running LOCALLY with flyte.init()")
        flyte.init()
    else:
        print("☁️  Running REMOTELY with flyte.init_from_config()")
        flyte.init_from_config(".flyte/config.yaml")

    print(f"\n{'='*80}")
    print("🎬 DEMO: RESEARCH REPORT GENERATOR")
    print(f"{'='*80}")
    print(f"📋 Topic: {args.topic}")
    print(f"🎯 Quality Target: {args.quality_threshold}/10")
    print(f"🔄 Max Iterations: {args.max_quality_iterations}")
    print(f"{'='*80}\n")

    # Execute the workflow
    execution = flyte.run(
        research_report_workflow,
        topic=args.topic,
        quality_threshold=args.quality_threshold,
        max_quality_iterations=args.max_quality_iterations
    )

    print(f"\n{'='*80}")
    print(f"✅ Execution: {execution.name}")
    print(f"🔗 URL: {execution.url}")
    print("👆 Click the link above to view execution in Flyte UI!")
    print(f"{'='*80}\n")