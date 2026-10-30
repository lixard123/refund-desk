"""Offline demo for the October cohort Refund Desk assignment."""
from __future__ import annotations

from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver

from src.refund_ops import (
    build_food_graph,
    build_refund_graph,
    build_review_loop,
    build_support_graph,
)


def main() -> int:
    load_dotenv()

    food = build_food_graph().invoke({"city": "Mysore"})
    support = build_support_graph().invoke(
        {"text": "My computer is not working. It's urgent.", "log": []}
    )
    review = build_review_loop().invoke({"draft": "", "attempts": 0, "history": []})
    refund = build_refund_graph(InMemorySaver()).invoke(
        {
            "request_id": "r-auto",
            "amount": 500,
            "reason": "Goodwill",
            "audit": [],
        },
        {"configurable": {"thread_id": "demo-auto"}},
    )

    print("=== REFUND DESK REPORT ===")
    print(f"Food (Mysore): {food['favorite_food']}")
    print(f"Support priority: {support['priority']}")
    print(f"Review attempts: {review['attempts']}")
    print(f"Auto refund status: {refund['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
