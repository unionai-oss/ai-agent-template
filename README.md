# Agent Basics - Multi-Agent Workflow System

A multi-agent orchestration system built with Flyte 2.0 demonstrating dynamic and sequential workflows.

## Setup

```bash
# Create virtual environment
uv venv .venv --python 3.11

# Activate the venv
source .venv/bin/activate # macOS/Linux
# or
.venv\Scripts\activate

# Configure Flyte (optional, for remote execution)
flyte create config \
    --endpoint https://demo.hosted.unionai.cloud \
    --auth-type headless \
    --builder remote \
    --domain development \
    --project flytesnacks
```

## Running Workflows

### Dynamic Workflow (Planner-based routing)

The dynamic workflow uses a planner agent to automatically route tasks to appropriate specialist agents.

```bash
# Local execution
python workflows/flyte_dynamic.py --local --request "Your task here"

# Remote execution
python workflows/flyte_dynamic.py --request "Your task here"
```

### Sequential Workflow (Content creation pipeline)

The sequential workflow follows a fixed pipeline: Research → Write → Edit

```bash
# Local execution
python workflows/flyte_sequential.py --local --topic "Your topic here"

# Remote execution
python workflows/flyte_sequential.py --topic "Your topic here"
```

## Example Queries

### Dynamic Workflow Examples

**Simple Math:**
```bash
python workflows/flyte_dynamic.py --local --request "Calculate 5 factorial"
```

**Simple String:**
```bash
python workflows/flyte_dynamic.py --local --request "Count the words in 'The quick brown fox jumps over the lazy dog'"
```

**Multi-agent (parallel execution):**
```bash
python workflows/flyte_dynamic.py --local --request "Calculate 5 times 3, then count the words in 'Hello World'"
```

**Dependencies (sequential with context):**
```bash
python workflows/flyte_dynamic.py --local --request "Calculate 2 plus 3 and 5 plus 6, then add those two results together"
```

**Math and String with dependencies:**
```bash
python workflows/flyte_dynamic.py --local --request "Calculate 10 times 5 and count words in 'Hello World', then multiply the word count by the calculation result"
```

**Web Search:**
```bash
python workflows/flyte_dynamic.py --local --request "Search for recent news about Flyte workflow orchestration"
```

**Code Execution:**
```bash
python -m workflows.flyte_dynamic --local --request "Write Python code to calculate the first 10 Fibonacci numbers"
```

**Weather:**
```bash
python -m workflows.flyte_dynamic --local --request "What's the weather like in Tokyo?"
```

**Parallel Execution (independent tasks):**
```bash
python -m workflows.flyte_dynamic --local --request "Calculate 10 factorial, count words in 'AI is transforming software', and search for latest Flyte 2.0 features"
```

**Context Summarization Demo (shows token savings):**
```bash
python -m workflows.flyte_dynamic --local --request "Search for the current GDP of France, search for the current GDP of Germany, then add those two GDP numbers together"
```

**Complex Multi-agent:**
```bash
python -m workflows.flyte_dynamic --local --request "Calculate 5 factorial, 10 times 10, count words in 'hello world', count letters in 'test', search for 'Python async', search for 'Flyte workflows', calculate 3 plus 7, count words in 'agent orchestration system', then write Python code to sum all the numeric results and concatenate all the text results"
```

### Sequential Workflow Examples

**Tech Topic:**
```bash
python -m workflows.flyte_sequential --local --topic "Machine Learning in Healthcare"
```

**Business Topic:**
```bash
python -m workflows.flyte_sequential --local --topic "Sustainable Energy Solutions"
```

**Website Research:**
```bash
python -m workflows.flyte_sequential --local --topic "flyte.org"
```

## Architecture

- **Dynamic Workflow**: Planner → Parallel Agent Execution with Dependencies
- **Sequential Workflow**: Web Search → Writer → Editor
- **Agents**: math, string, web_search, code, weather, writer, editor
- **Context Summarization**: Automatic truncation of large outputs when passing between agents
