import json
import asyncio
from openai import AsyncOpenAI
from config import OPENAI_API_KEY
from utils.logger import Logger
from utils.decorators import agent_tools, tool_registry

logger = Logger()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def execute_plan(user_prompt, verbose=False, agent=None, system_msg=None):
    toolset = agent_tools.get(agent, tool_registry)
    tool_list = "\n".join([f"{name}: {fn.__doc__.strip()}" for name, fn in toolset.items()])
    # ----------------------------------
    # Default system message (General agent) if none provided
    # ----------------------------------
    if not system_msg:
        system_msg = (
            "You are a reasoning agent. Use tools from the list below to accomplish your tasks.\n"
            f"Tools:\n{tool_list}\n\n"
            "CRITICAL: You must respond with ONLY a valid JSON array, nothing else. No markdown, no explanations.\n"
            "Return a JSON array of tool calls in this exact format:\n"
            '[\n'
            '  {"tool": "example_tool", "args": [1, 2], "reasoning": "Explain why this tool is called."},\n'
            '  {"tool": "another_tool", "args": ["previous"], "reasoning": "Explain why using the previous result."}\n'
            ']\n'
            'RULES:\n'
            '1. Start your response with [ and end with ]\n'
            '2. No markdown code blocks (no ```)\n'
            '3. No extra text before or after the JSON\n'
            '4. Always include a "reasoning" field for each step\n'
            '5. Use "previous" in args to reference the previous step result'
        )



    # Add a few-shot example to reinforce JSON-only output
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": "Add 2 and 3"},
        {"role": "assistant", "content": '[{"tool": "add", "args": [2, 3], "reasoning": "Adding 2 and 3 to get the sum"}]'},
        {"role": "user", "content": user_prompt}
    ]

    response = await client.chat.completions.create(
        model="gpt-4",
        messages=messages
    )

    raw_plan = response.choices[0].message.content
    if verbose:
        print("\n[LLM PLAN]", raw_plan)

    # Try to parse directly first
    try:
        plan = json.loads(raw_plan)
    except json.JSONDecodeError as e:
        # If that fails, try to extract JSON from markdown code blocks or surrounding text
        import re

        print(f"[WARN] Direct JSON parse failed: {e}")
        print(f"[WARN] Attempting to extract JSON from response...")

        # Try to find JSON within markdown code blocks first
        code_block_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', raw_plan, re.DOTALL)
        if code_block_match:
            try:
                plan = json.loads(code_block_match.group(1))
                print("[INFO] Successfully extracted JSON from markdown code block")
            except json.JSONDecodeError:
                pass

        # If no code block, try to find any JSON array in the text
        if 'plan' not in locals():
            # More greedy pattern that captures the whole array
            json_match = re.search(r'\[(?:[^\[\]]*|\{[^}]*\})*\]', raw_plan, re.DOTALL)
            if json_match:
                try:
                    plan = json.loads(json_match.group(0))
                    print("[INFO] Successfully extracted JSON array from text")
                except json.JSONDecodeError as e2:
                    print(f"[ERROR] Extracted text is not valid JSON: {e2}")
                    print(f"[ERROR] Extracted text:\n{json_match.group(0)}")
                    print(f"[ERROR] Full LLM response:\n{raw_plan}")
                    raise ValueError(f"Could not extract valid JSON array from LLM response")
            else:
                print(f"[ERROR] Could not find JSON array pattern in LLM response:\n{raw_plan}")
                raise ValueError(f"Could not extract valid JSON array from LLM response")

    steps_log = []
    last_result = None

    #----------------------------------
    # Execute the plan
    #----------------------------------
    try:
        for step in plan:
            tool_name = step["tool"]
            args = step["args"]
            reasoning = step.get("reasoning", "")
            args = [last_result if str(a).lower() == "previous" else a for a in args]

            if tool_name in toolset:
                # Tools are now async, so we need to await them
                tool_func = toolset[tool_name]
                if asyncio.iscoroutinefunction(tool_func):
                    result = await tool_func(*args)
                else:
                    result = tool_func(*args)
            else:
                await logger.log(tool=tool_name, args=args, error="Unknown tool", reasoning=reasoning)
                raise ValueError(f"Unknown tool: {tool_name}")

            await logger.log(tool=tool_name, args=args, result=result, reasoning=reasoning)
            steps_log.append({"tool": tool_name, "args": args, "result": result, "reasoning": reasoning})
            last_result = result

        return {"final_result": last_result, "steps": steps_log}

    except Exception as e:
        await logger.log(tool=tool_name if "tool_name" in locals() else "unknown", args=args if "args" in locals() else [], error=str(e))
        return {"error": str(e), "steps": steps_log}