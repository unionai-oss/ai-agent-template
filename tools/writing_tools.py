from utils.decorators import tool
import flyte

@tool(agent="writer")
@flyte.trace
async def write_content(topic: str, research_context: str, word_count: int = 300) -> str:
    """
    Writes content on a given topic using provided research context.

    Args:
        topic (str): The topic to write about
        research_context (str): Research information to base the content on
        word_count (int): Target word count (default: 300)

    Returns:
        str: The written content
    """
    print(f"TOOL CALL: Writing content about '{topic}' (target: {word_count} words)")

    # In a real implementation, this would use an LLM to generate content
    # For now, we'll create a structured output based on the research

    content = f"""# {topic}

Based on recent research, here's what you need to know about {topic}:

{research_context}

This overview provides key insights into {topic}, synthesizing the most important information from current sources.
"""

    return content


@tool(agent="writer")
@flyte.trace
async def add_section(existing_content: str, section_title: str, section_content: str) -> str:
    """
    Adds a new section to existing content.

    Args:
        existing_content (str): The current content
        section_title (str): Title for the new section
        section_content (str): Content for the new section

    Returns:
        str: Updated content with new section added
    """
    print(f"TOOL CALL: Adding section '{section_title}' to content")

    new_section = f"\n\n## {section_title}\n\n{section_content}"
    return existing_content + new_section
