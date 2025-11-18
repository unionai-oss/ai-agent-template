# Multi-Agent Workflow System - A Flyte 2.0 Template

A flexible multi-agent orchestration system built with **Flyte 2.0** that demonstrates intelligent task routing, parallel execution, and dependency management. Perfect for learning how to build production-grade agentic systems.

## 🎯 What Is This?

This is Agent template that uses specialized AI agents to solve complex tasks:

- **Planner Agent**: Analyzes requests and creates execution plans
- **Specialist Agents**: Each agent excels at specific tasks (math, web search, code execution, etc.)
- **Smart Orchestration**: Executes agents in parallel when possible, sequentially when needed
- **Intelligent Context Passing**: Summarizes large outputs before passing between agents

### Two Workflow Patterns

1. **Dynamic Workflow**: Planner routes tasks to appropriate agents based on user intent
2. **Sequential Workflow**: Fixed pipeline for content creation (Research → Write → Edit)

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- Flyte 2.0 cluster for remote execution (optional) ([Sign up here](https://www.union.ai/beta))

### Installation

```bash
# Clone the repository
git clone https://github.com/unionai-oss/ai-agent-template
cd agent-basics

# Create virtual environment
python -m venv .venv

# Activate the venv
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file with your API key
echo "OPENAI_API_KEY=your-key-here" > .env
```

### Your First Agent Workflow

Note: you need to run as a python module for the imports to work correctly. `python -m workflows.flyte_dynamic`

```bash
# Simple math task
python -m workflows.flyte_dynamic --local --request "Calculate 15 times 7"

# Web search task
python -m workflows.flyte_dynamic --local --request "Search for the latest news about AI agents"

# Multi-step with dependencies
python -m workflows.flyte_dynamic --local --request "Search for the GDP of Japan, then multiply it by 2"
```
---

## 🚢 Remote Execution with Flyte

Run workflows on Flyte clusters for scale:

```bash
# Configure Flyte connection
flyte create config \
    --endpoint https://your-flyte-cluster.com \
    --auth-type headless \
    --builder remote \
    --domain development \
    --project your-project

# Run remotely (omit --local flag)
python -m workflows.flyte_dynamic --request "Your task"
```

Benefits:
- **Scalability**: Run hundreds of workflows in parallel
- **Resource isolation**: Each agent gets dedicated containers
- **Observability**: Flyte UI for monitoring
- **Reproducibility**: Versioned workflows and data lineage
---

## 📚 Understanding the System

### Available Agents

| Agent | Purpose | Model | Example Use |
|-------|---------|-------|-------------|
| **Planner** | Routes tasks to specialist agents | gpt-4 | Analyzes "Calculate 5+3 and search for Python" |
| **Math** | Arithmetic, powers | gpt-4o-mini | add(5, 3), multiply(10, 20) |
| **String** | Text analysis | gpt-4o-mini | word_count("hello world") |
| **Web Search** | DuckDuckGo search + fetch | gpt-4o | Search recent articles |
| **Code** | Python execution | gpt-4o | Calculate fibonacci(10) |
| **Weather** | Location weather | gpt-4o-mini | Get Tokyo weather |
| **Writer** | Content creation | gpt-4o | Write article from research |
| **Editor** | Content improvement | gpt-4o | Polish and improve draft |

### How It Works

```
User Request
    ↓
Planner Agent (analyzes request)
    ↓
Creates Execution Plan with Dependencies
    ↓
Orchestrator executes agents in optimal order
    ├─→ Independent tasks run in PARALLEL
    └─→ Dependent tasks run SEQUENTIALLY
    ↓
Results combined and returned
```

### Example Execution Flow

**Request:** "Calculate 2+3 and 5+6, then multiply the results"

```
Step 0: Math Agent → add(2, 3) = 5          ┐
Step 1: Math Agent → add(5, 6) = 11         ├─ Run in PARALLEL
                                            ┘
Step 2: Math Agent → multiply(5, 11) = 55   ← Depends on Steps 0 & 1
```

---

## 🎮 Usage Examples

### Dynamic Workflow

The planner intelligently routes tasks to the right agents:

**Simple Tasks:**
```bash
# Math
python -m workflows.flyte_dynamic --local --request "What is 2 to the power of 8?"

# String analysis
python -m workflows.flyte_dynamic --local --request "How many words in 'The quick brown fox'?"

# Weather
python -m workflows.flyte_dynamic --local --request "What's the weather in London?"

# complex multi-task execution with parallelism, dependency management, and context passing
python -m workflows.flyte_dynamic --local --request "Calculate 5 factorial, 10 times 10, count words in 'hello world', count letters in 'test', search for 'Python async', search for 'Flyte workflows', calculate 3 plus 7, count words in 'agent orchestration system', then write Python code to sum all the numeric results and concatenate all the text results"
```

**Multi-Agent Tasks:**
```bash
# Search + Math (sequential with dependency)
python -m workflows.flyte_dynamic --local --request \
  "Search for the current population of India, then multiply it by 2"

# Parallel execution (independent tasks)
python -m workflows.flyte_dynamic --local --request \
  "Calculate 10 factorial, count words in 'Hello World', and search for Flyte documentation"
```

**Complex Tasks:**
```bash
# Multi-step with multiple dependencies
python -m workflows.flyte_dynamic --local --request \
  "Search for France GDP and Germany GDP, then add them together and multiply by 1.1"
```

### Sequential Workflow

Fixed pipeline for content creation:

```bash
# Research a topic, write an article, then edit it
python -m workflows.flyte_sequential --local --topic "Quantum Computing Applications"

# Create content about a website
python -m workflows.flyte_sequential --local --topic "flyte.org"
```

---

## 🏗️ Project Structure

```
agent-basics/
├── agents/                  # Agent implementations
│   ├── planner_agent.py    # Routes tasks to specialists
│   ├── math_agent.py       # Arithmetic operations
│   ├── string_agent.py     # Text analysis
│   ├── web_search_agent.py # Web search + fetch
│   ├── code_agent.py       # Python code execution
│   ├── weather_agent.py    # Weather info
│   ├── writer_agent.py     # Content creation
│   └── editor_agent.py     # Content improvement
│
├── tools/                   # Tool implementations
│   ├── math_tools.py       # add, multiply, power
│   ├── string_tools.py     # word_count, letter_count
│   ├── web_search_tools.py # duck_duck_go, fetch_webpage
│   ├── code_tools.py       # execute_python
│   └── weather_tools.py    # get_weather
│
├── utils/                   # Utilities
│   ├── decorators.py       # @agent and @tool decorators
│   ├── plan_executor.py    # Tool plan execution
│   ├── summarizer.py       # LLM-based context summarization
│   └── logger.py           # Execution logging
│
├── workflows/               # Workflow orchestrations
│   ├── flyte_dynamic.py    # Planner-based routing
│   └── flyte_sequential.py # Fixed pipeline
│
├── config.py               # Configuration & environment
├── requirements.txt        # Dependencies
└── README.md              # This file
```

---

## 🔧 How to Extend

### Adding a New Tool

Tools are discrete operations that agents can use.

**1. Create the tool function:**

```python
# tools/my_new_tools.py
from utils.decorators import tool

@tool("my_agent")
async def my_operation(param1: str, param2: int) -> str:
    """Short description of what this tool does"""
    # Your implementation
    result = f"Processed {param1} with {param2}"
    return result
```

**2. Import in your agent:**

```python
# agents/my_agent.py
import tools.my_new_tools  # Registers tools automatically
```

**3. The tool is now available in your agent's toolset!**

### Adding a New Agent

Agents orchestrate tools to accomplish tasks.

**1. Create the agent file:**

```python
# agents/my_new_agent.py
import json
import flyte
from openai import AsyncOpenAI
from dataclasses import dataclass

import tools.my_new_tools  # Import tools to register them

from utils.decorators import agent, agent_tools
from utils.plan_executor import execute_tool_plan, parse_plan_from_response
from config import base_env, OPENAI_API_KEY

# Agent-Specific Configuration
MY_AGENT_CONFIG = {
    "model": "gpt-4o-mini",  # Choose based on complexity
    "temperature": 0.0,       # Adjust for creativity
    "max_tokens": 500,
}

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

@dataclass
class MyAgentResult:
    """Result from my agent execution"""
    final_result: str
    steps: str  # JSON string of steps taken
    error: str = ""

env = base_env

@env.task
@agent("my_agent")
async def my_agent(task: str) -> MyAgentResult:
    """
    My new agent that does X, Y, and Z.
    """
    print(f"[My Agent] Processing: {task}")

    # Build system message
    toolset = agent_tools["my_agent"]
    tool_list = "\n".join([f"{name}: {fn.__doc__.strip()}"
                           for name, fn in toolset.items()])

    system_msg = f"""
You are a specialized agent for [your domain].

Tools:
{tool_list}

Return a JSON array of tool calls in this format:
[
  {{"tool": "my_operation", "args": ["value", 42], "reasoning": "Why this step"}}
]
"""

    # Call LLM to create plan
    response = await client.chat.completions.create(
        model=MY_AGENT_CONFIG["model"],
        temperature=MY_AGENT_CONFIG["temperature"],
        max_tokens=MY_AGENT_CONFIG["max_tokens"],
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": "Example query"},
            {"role": "assistant", "content": '[{"tool": "my_operation", "args": ["example", 1], "reasoning": "Example"}]'},
            {"role": "user", "content": task}
        ]
    )

    # Parse and execute
    raw_plan = response.choices[0].message.content
    plan = parse_plan_from_response(raw_plan)
    result = await execute_tool_plan(plan, agent="my_agent")

    return MyAgentResult(
        final_result=str(result.get("final_result", "")),
        steps=json.dumps(result.get("steps", [])),
        error=result.get("error", "")
    )
```

**2. Register in planner:**

```python
# agents/planner_agent.py
import agents.my_new_agent  # Add this import

# Update planner's system message to include your new agent
```

**3. Add to orchestrator routing:**

```python
# workflows/flyte_dynamic.py
from agents.my_new_agent import my_agent, MyAgentResult

# In execute_dynamic_task, add routing:
elif step.agent == "my_agent":
    agent_result = await my_agent(task)
    result_full = agent_result.final_result
    result_summary = agent_result.final_result
    error = agent_result.error
```

### Configuring Model Usage

Each agent has its own configuration for cost optimization:

```python
# In any agent file, adjust these settings:
AGENT_CONFIG = {
    "model": "gpt-4o-mini",  # Options: gpt-4o-mini, gpt-4o, gpt-4
    "temperature": 0.0,       # 0.0 (deterministic) to 1.0 (creative)
    "max_tokens": 500,        # Control output length
}
```

**Model Selection Guide:**
- **gpt-4o-mini**: Simple tasks (math, string, weather) - Very cheap
- **gpt-4o**: Complex reasoning (code, web search) - Balanced
- **gpt-4**: Highest quality (planner) - Expensive

---

## 🎓 Key Concepts

### 1. Tool-Based vs Direct LLM Agents

**Tool-Based Agents** (math, string, web_search, code, weather):
- Break tasks into discrete tool calls
- Chain operations: "add 2+3, then multiply by 5"
- Reference previous results with "previous"
- Best for decomposable tasks

**Direct LLM Agents** (writer, editor):
- Single-shot generation
- Creative/holistic tasks
- No intermediate steps
- Best for content creation

### 2. Dependency Management

The planner can specify dependencies between steps:

```python
{
  "steps": [
    {"agent": "math", "task": "add 2 and 3", "dependencies": []},
    {"agent": "math", "task": "multiply previous by 5", "dependencies": [0]}
  ]
}
```

Step 1 depends on Step 0, so they run sequentially with context passing.

### 3. Intelligent Context Summarization

When passing large outputs between agents (e.g., web search → math), the system:
1. Checks if content > 800 characters
2. If yes: Uses gpt-4o-mini to intelligently summarize
3. Preserves URLs, numbers, key facts
4. Falls back to sentence-aware truncation if LLM fails

This prevents token bloat and information loss!

### 4. Parallel Execution

Independent tasks automatically run in parallel:

```bash
# These 3 tasks run simultaneously:
"Calculate 10 factorial, count words in 'Hello', and search for Python"
```

The orchestrator detects no dependencies and uses `asyncio.gather()` for speed.

---

## 🔍 Monitoring & Debugging

### Execution Logs

All agent executions are logged to `agent_trace_log.jsonl`:

```json
{
  "step_idx": 0,
  "agent": "web_search",
  "input_task": "Search for Python tutorials",
  "output_full": "...",
  "output_summary": "...",
  "output_full_length": 2431,
  "output_summary_length": 487,
  "dependencies": []
}
```

### Verbose Output

Enable detailed logging in agents:

```python
logger = Logger(path="agent_trace_log.jsonl", verbose=True)
```


---

## 🤝 Contributing

Ideas for enhancements:

- [ ] Add more agent types (database, file operations, API calls)
- [ ] Implement retry logic with exponential backoff
- [ ] Better Structured Outputs (OpenAI, BAML, Instructor)
- [ ] Create a web UI for workflow visualization
- [ ] Support other LLM providers (Anthropic, Gemini)
- [ ] Add caching for repeated tool calls
- [ ] Implement human-in-the-loop for approvals

---

## 📖 Learn More

- **Flyte Documentation**: [docs.flyte.org](https://docs.flyte.org)
- **OpenAI API**: [platform.openai.com/docs](https://platform.openai.com/docs)
- **Multi-Agent Systems**: [LangGraph](https://github.com/langchain-ai/langgraph), [AutoGen](https://github.com/microsoft/autogen)

---


## 🙏 Acknowledgments

Built with Flyte 2.0 and OpenAI. Inspired by the growing field of agentic AI systems.

---

**Ready to build something amazing?** Start with the Quick Start guide above and experiment with different agent combinations!