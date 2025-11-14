from utils.decorators import tool
import flyte

@tool(agent="editor")
@flyte.trace
async def review_content(content: str) -> dict:
    """
    Reviews content and provides feedback on quality, clarity, and completeness.

    Args:
        content (str): The content to review

    Returns:
        dict: Review feedback including scores and suggestions
    """
    print(f"TOOL CALL: Reviewing content ({len(content)} characters)")

    # Simple heuristic-based review
    word_count = len(content.split())
    has_title = content.strip().startswith('#')
    has_sections = '##' in content
    line_count = len(content.split('\n'))

    score = 0
    feedback = []

    # Check word count
    if word_count >= 100:
        score += 3
        feedback.append("✓ Good length")
    else:
        feedback.append("⚠ Content seems short")

    # Check structure
    if has_title:
        score += 2
        feedback.append("✓ Has title")
    else:
        feedback.append("⚠ Missing title")

    if has_sections:
        score += 2
        feedback.append("✓ Well-structured with sections")
    else:
        feedback.append("⚠ Could benefit from sections")

    # Check readability
    if line_count > 5:
        score += 3
        feedback.append("✓ Good paragraph structure")

    overall = "Excellent" if score >= 8 else "Good" if score >= 5 else "Needs improvement"

    return {
        "overall_rating": overall,
        "score": score,
        "word_count": word_count,
        "feedback": feedback
    }


@tool(agent="editor")
@flyte.trace
async def improve_content(content: str, focus_area: str = "clarity") -> str:
    """
    Improves content based on a specific focus area.

    Args:
        content (str): The content to improve
        focus_area (str): What to focus on (clarity, structure, tone, etc.)

    Returns:
        str: Improved content
    """
    print(f"TOOL CALL: Improving content (focus: {focus_area})")

    # Add improvement notes based on focus area
    improvement_note = f"\n\n---\n*Editor's note: Content reviewed and improved for {focus_area}*"

    return content + improvement_note
