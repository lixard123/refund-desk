# Refund Desk

October cohort assignment OCT1. Implement `src/refund_ops.py`. The entrypoint stays as written.

## Run

```bash
pip install -r requirements.txt
python main.py
```

Do not commit `.env`. Copy `.env.example` if you want a local key file for optional experiments. This assignment is graded without an API key.

## What you implement

Messages, a prompt template, a refund estimate tool, LangGraph food and support graphs, a draft review loop, a human-in-the-loop refund graph, a SQLite checkpointer, and a FastMCP server. See the assignment brief for the exact contracts.

## Reflection

1. Why do graph nodes return a partial update instead of appending to `state["log"]` in place?
2. Why must `interrupt()` run only after work that is safe to repeat?
3. Why does the refund fee live in a tool instead of asking the model to do the arithmetic?
