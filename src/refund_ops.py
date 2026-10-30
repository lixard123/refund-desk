"""
LEARNER IMPLEMENTATION — Assignment OCT1 Refund Desk

Implement every function below. The auto-grader imports:
  import src.refund_ops

No API key is required. Do not call a live chat model from these functions.
Do not copy secrets from class demos into this repository.
"""
from __future__ import annotations
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from typing import Any
from pydantic import BaseModel
from langgraph.types import interrupt


from langgraph.checkpoint.memory import InMemorySaver


import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

from fastmcp import FastMCP
from fastmcp.prompts import Message
import json




class RefundEstimate(BaseModel):  # replace with a pydantic BaseModel
    """amount: int, fee: float, net: float, note: str"""
    amount: int
    fee: float
    net: float
    note: str


def estimate_refund(amount: int) -> str:
    """
    Illustrative 2% processing fee.

    fee = round(amount * 0.02, 2)
    net = round(amount - fee, 2)

    Return exactly:
      "Original amount: INR {amount}, illustrative processing fee: INR {fee}, net amount: INR {net}"
    """
    fee = round(amount * 0.02, 2)
    net = round(amount - fee, 2)

    return (
        f"Original amount: INR {amount}, "
        f"illustrative processing fee: INR {fee}, "
        f"net amount: INR {net}"
    )


def estimate_model(amount: int) -> RefundEstimate:
    """
    Return a RefundEstimate for amount.
    fee and net use the same rounding as estimate_refund.
    note must contain the word "hypothetical" (any casing is fine, but include the word).
    """
    fee = round(amount * 0.02, 2)
    net = round(amount - fee, 2)
    return RefundEstimate(
        amount=amount,
        fee=fee,
        net=net,
        note="This is a hypothetical processing fee, not an actual payment."
    )
    


def build_conversation(question: str, answer: str, followup: str) -> list:
    """
    Return four LangChain messages, in this order:
      1. SystemMessage content exactly:
         "You are a helpful assistant that answers every question with a joke."
      2. HumanMessage content = question
      3. AIMessage content = answer
      4. HumanMessage content = followup
    """
    system_message = SystemMessage(
        content="You are a helpful assistant that answers every question with a joke."
    )
    human_message = HumanMessage(content=question)
    ai_message = AIMessage(content=answer)
    followup_message = HumanMessage(content=followup)

    return [
        system_message,
        human_message,
        ai_message,
        followup_message
    ]
    
    
    


def refund_prompt(amount: int, reason: str) -> str:
    """
    Build a ChatPromptTemplate with:
      system: "You are a refund assistant. Explain that the fee is hypothetical."
      human:  "Amount: {amount}\\nReason: {reason}"

    Invoke it with amount and reason. Return one string that contains the
    rendered amount, the reason, and the word "hypothetical".
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a refund assistant. Explain that the fee is hypothetical."),
        ("human", "Amount: {amount}\nReason: {reason}")
    ])

    rendered_prompt = prompt.invoke({
        "amount": amount,
        "reason": reason
    })

    return rendered_prompt.to_string()


def apply_tool_result(tool_name: str, args: dict, tool_call_id: str) -> Any:
    """
    Run a tool and wrap the result in a ToolMessage.

    tool_name "add": content is str(int(args["a"]) + int(args["b"]))
    tool_name "estimate_refund": content is estimate_refund(int(args["amount"]))
    any other name: raise KeyError

    Set tool_call_id on the ToolMessage.
    """
    if tool_name == "add":
        result = str(int(args["a"]) + int(args["b"]))

    elif tool_name == "estimate_refund":
        result = estimate_refund(int(args["amount"]))

    else:
        raise KeyError(tool_name)

    return ToolMessage(
        content=result,
        tool_call_id=tool_call_id
    )
class FoodState(TypedDict):
    city: str
    question: str
    favorite_food: str


def prepare(state: FoodState):
    return {
        "question": f"What is the favorite food of {state['city']}?"
    }


def answer(state: FoodState):
    food_map = {
        "Mumbai": "Vada Pav",
        "Delhi": "Chaat",
        "Mysore": "Mysore Pak"
    }

    return {
        "favorite_food": food_map.get(state["city"], "Unknown")
    }

def build_food_graph():
    """
    Compiled LangGraph.

    State keys: city, question, favorite_food.
    prepare node sets question to "What is the favorite food of {city}?"
    answer node sets favorite_food:
      Mumbai -> Vada Pav
      Delhi -> Chaat
      Mysore -> Mysore Pak
      anything else -> Unknown

    START -> prepare -> answer -> END
    """
    graph = StateGraph(FoodState)

    graph.add_node("prepare", prepare)
    graph.add_node("answer", answer)

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "answer")
    graph.add_edge("answer", END)

    return graph.compile()
  
class SupportState(TypedDict):
    text: str
    priority: str
    response: str
    log: Annotated[list[str], operator.add]
    
def classify(state: SupportState):
    priority = (
        "urgent"
        if "urgent" in state["text"].lower()
        else "normal"
    )
    return {
        "priority": priority,
        "log": [f"Ticket classified as {priority}"]
    }
def urgent_node(state: SupportState):
    return {
        "response": "Ticket has been escalated to the urgent support team.",
        "log": ["Ticket escalated to urgent support"]
    }


def normal_node(state: SupportState):
    return {
        "response": "Thank you for contacting support. We will get back to you shortly.",
        "log": ["Normal support provided"]
    }


def route_by_priority(state: SupportState):
    return state["priority"]



   

def build_support_graph():
    """
    Compiled LangGraph with a list reducer on log.

    State keys: text, priority, response, log.
    log is Annotated[list[str], operator.add].

    classify: priority "urgent" if "urgent" is in text.lower(), else "normal".
    Return log item "Ticket classified as {priority}".
    Do not mutate state["log"] in place.

    conditional edge:
      "urgent" -> urgent support response
        "Ticket has been escalated to the urgent support team."
        log item "Ticket escalated to urgent support"
      "normal" -> normal support response
        "Thank you for contacting support. We will get back to you shortly."
        log item "Normal support provided"

    Callers pass log: [] on invoke.
    """
    graph = StateGraph(SupportState)
    
    graph.add_node("classify", classify)
    graph.add_node("urgent", urgent_node)
    graph.add_node("normal", normal_node)
    
    graph.add_edge(START, "classify")
    
    graph.add_conditional_edges(
          "classify",
            route_by_priority,
            {
                "urgent": "urgent",
                "normal": "normal"
            }
        )
    
    graph.add_edge("urgent", END)
    graph.add_edge("normal", END)
    return graph.compile()     
class ReviewState(TypedDict):
    draft: str
    attempts: int
    history: Annotated[list[str], operator.add]


def write_draft(state: ReviewState):
    attempt = state.get("attempts", 0) + 1

    if attempt == 1:
        draft = "LangGraph"
    else:
        draft = (
            "LangGraph orchestrates stateful AI workflows "
            "with nodes, edges, and checkpointing."
        )

    return {
        "draft": draft,
        "attempts": attempt,
        "history": [f"Draft attempt {attempt}"]
    }


def evaluate_draft(state: ReviewState):
    passed = len(state["draft"].split()) >= 8

    return {
        "history": [f"Quality check passed: {passed}"]
    }


def route_after_evaluation(state: ReviewState):
    passed = len(state["draft"].split()) >= 8

    if passed or state["attempts"] >= 3:
        return END

    return "write"

def build_review_loop():
    """
    Compiled LangGraph review loop.

    State keys: draft, attempts, history.
    history is Annotated[list[str], operator.add].

    write node:
      attempt = attempts + 1 (missing attempts counts as 0)
      attempt 1 draft is exactly "LangGraph"
      later drafts are exactly:
        "LangGraph orchestrates stateful AI workflows with nodes, edges, and checkpointing."
      history item: "Draft attempt {attempt}"

    evaluate node appends history item "Quality check passed: {true/false}"
    where the check is len(draft.split()) >= 8.

    After evaluate:
      finish when the draft has at least 8 words, or attempts >= 3
      otherwise go back to write

    Callers pass draft="", attempts=0, history=[].
    """
    graph = StateGraph(ReviewState)

    graph.add_node("write", write_draft)
    graph.add_node("evaluate", evaluate_draft)

    graph.add_edge(START, "write")
    graph.add_edge("write", "evaluate")

    graph.add_conditional_edges(
        "evaluate",
        route_after_evaluation,
        {
            "write": "write",
            END: END
        }
    )

    return graph.compile()
class RefundState(TypedDict):
    request_id: str
    amount: int
    reason: str
    decision: str
    status: str
    audit: Annotated[list[str], operator.add]


def validate_request(state: RefundState):
    amount = state["amount"]

    if amount <= 0:
        raise ValueError("Refund amount must be greater than 0")

    return {
        "audit": [f"Validation: amount {amount} is valid"]
    }


def route_after_validation(state: RefundState):
    if state["amount"] < 1000:
        return "automatic_approval"

    return "manager_review"


def automatic_approval(state: RefundState):
    amount = state["amount"]

    return {
        "decision": "approved",
        "audit": [f"Automatic Approval: amount {amount} is approved"]
    }


def manager_review(state: RefundState):
    # No external side effects before interrupt().
    human_response = interrupt({
        "question": "Do you approve this refund?",
        "request_id": state["request_id"],
        "amount": state["amount"],
        "reason": state["reason"],
    })

    if (
        isinstance(human_response, dict)
        and human_response.get("manager") == "approved"
    ):
        decision = "approved"
    else:
        decision = "rejected"

    return {
        "decision": decision,
        "audit": [
            f"Manager Review: amount {state['amount']} , Approval is {human_response}"
        ]
    }


def route_after_review(state: RefundState):
    if state["decision"] == "approved":
        return "execute_refund"

    return "reject_refund"


def execute_refund(state: RefundState):
    amount = state["amount"]

    return {
        "status": "completed",
        "audit": [f"Execute Refund: amount {amount} is executed"]
    }


def reject_refund(state: RefundState):
    amount = state["amount"]

    return {
        "status": "rejected",
        "audit": [f"Reject Refund: amount {amount} is rejected"]
    }


def build_refund_graph(checkpointer):
    """
    Compiled refund graph. Pass checkpointer to compile().

    State keys: request_id, amount, reason, decision, status, audit.
    audit is Annotated[list[str], operator.add]. Callers pass audit: [].

    validate_request:
      if amount <= 0: raise ValueError("Refund amount must be greater than 0")
      else audit item "Validation: amount {amount} is valid"

    Route after validate:
      amount < 1000 -> automatic_approval
      else -> manager_review

    automatic_approval:
      decision "approved"
      audit item "Automatic Approval: amount {amount} is approved"
      then execute_refund

    manager_review:
      human_response = interrupt({
        "question": "Do you approve this refund?",
        "request_id": state["request_id"],
        "amount": state["amount"],
        "reason": state["reason"],
      })
      decision "approved" only when human_response is a dict and
      human_response.get("manager") == "approved"; otherwise "rejected"
      audit item "Manager Review: amount {amount} , Approval is {human_response}"

    After manager review:
      approved -> execute_refund
      otherwise -> reject_refund

    execute_refund: status "completed",
      audit item "Execute Refund: amount {amount} is executed"
    reject_refund: status "rejected",
      audit item "Reject Refund: amount {amount} is rejected"

    Do not perform a non-idempotent side effect before interrupt().
    """
    graph = StateGraph(RefundState)

    graph.add_node("validate_request", validate_request)
    graph.add_node("automatic_approval", automatic_approval)
    graph.add_node("manager_review", manager_review)
    graph.add_node("execute_refund", execute_refund)
    graph.add_node("reject_refund", reject_refund)

    graph.add_edge(START, "validate_request")

    graph.add_conditional_edges(
            "validate_request",
            route_after_validation,
            {
                "automatic_approval": "automatic_approval",
                "manager_review": "manager_review",
            }
        )

    graph.add_edge("automatic_approval", "execute_refund")

    graph.add_conditional_edges(
            "manager_review",
            route_after_review,
            {
                "execute_refund": "execute_refund",
                "reject_refund": "reject_refund",
            }
        )

    graph.add_edge("execute_refund", END)
    graph.add_edge("reject_refund", END)

    return graph.compile(checkpointer=checkpointer)


def make_sqlite_checkpointer(db_path: str):
    """
    Return a live SqliteSaver for db_path.
    Use sqlite3.connect(db_path, check_same_thread=False).
    Keep the connection open on the returned saver.
    """
    connection = sqlite3.connect(
        db_path,
        check_same_thread=False
    )

    return SqliteSaver(connection)


def build_mcp_server():
    """
    Return a FastMCP server named "Refund Desk" with:

    Tools
      add(a: int, b: int) -> int
      estimate_refund(amount: int) -> str   (same string as estimate_refund())
      Use @mcp.tool(name="estimate_refund") if the function cannot use that name.

    Resources
      resource://greeting -> "Hello from FastMCP Resources!"
      data://config -> JSON string with "theme": "dark" and features including "tools"

    Prompt
      ask_about_topic(topic: str) -> a string that contains topic
    """
    mcp = FastMCP("Refund Desk")

    # Tool 1: Addition
    @mcp.tool()
    def add(a: int, b: int) -> int:
        return a + b

    # Tool 2: Refund estimate
    # Call the existing module-level estimate_refund function.
    @mcp.tool(name="estimate_refund")
    def estimate_refund_tool(amount: int) -> str:
        return estimate_refund(amount)

    # Resource 1: Greeting
    @mcp.resource("resource://greeting")
    def greeting() -> str:
        return "Hello from FastMCP Resources!"

    # Resource 2: Configuration
    @mcp.resource("data://config")
    def config() -> str:
        return json.dumps({
            "theme": "dark",
            "features": ["tools", "resources", "prompts"]
        })

    # Prompt: Ask about a topic
    @mcp.prompt()
    def ask_about_topic(topic: str) -> str:
        return f"Explain {topic} in simple terms, with a practical example."

    return mcp
