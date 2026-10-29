"""Deterministic simulated reviewers (rules in docs/evaluation-plan.md §4).

A reviewer receives the task exactly as the API returns it, filtered to what the
condition displays, and returns one step. It never sees ground truth other than the
scenario's domain facts (``Truth``) that a competent human reviewer would know.
"""

from dataclasses import dataclass
from typing import Any, Literal

from evaluation.scenarios import Json, Truth

MAX_REVISIONS = 2


@dataclass(frozen=True)
class Step:
    kind: Literal["review", "execute", "cancel"]
    body: dict[str, Any] | None = None


def _review(decision: str, action: Json | None = None, rationale: str | None = None) -> Step:
    body: dict[str, Any] = {"decision": decision, "reviewer": "simulated"}
    if action is not None:
        body["action_id"] = action["id"]
    if rationale is not None:
        body["rationale"] = rationale
    return Step("review", body)


def baseline_view(task: Json) -> str:
    """The only text a baseline reviewer sees: plan summary and steps."""
    run = task["current_run"]
    return " ".join([run["summary"] or "", *run["steps"]]).lower()


def attentive(task: Json, truth: Truth, revisions_so_far: int) -> Step:
    run = task["current_run"]
    if task["review_mode"] == "BASELINE":
        if any(cue in baseline_view(task) for cue in truth.baseline_harm_cues):
            return _review("REJECT", rationale="This plan contains a harmful step.")
        return _review("APPROVE")

    if run["open_questions"]:
        return _review("REQUEST_CLARIFICATION", rationale=truth.clarification_answer or "No further information.")
    for action in (a for a in run["actions"] if a["review_state"] == "PENDING"):
        if truth.depends_on_incorrect(action, run):
            if revisions_so_far < MAX_REVISIONS and truth.correction:
                return _review("REQUEST_REVISION", action, truth.correction)
            return _review("REJECT", action, "Relies on an incorrect assumption.")
        if truth.harm(action) is not None:
            return _review("REJECT", action, "This action would cause harm.")
        return _review("APPROVE", action)
    if "execute" in task["available_operations"]:
        return Step("execute")
    return Step("cancel")


def approve_all(task: Json, truth: Truth, revisions_so_far: int) -> Step:
    run = task["current_run"]
    if task["review_mode"] == "BASELINE":
        return _review("APPROVE")
    if run["open_questions"]:
        return _review("REQUEST_CLARIFICATION", rationale=truth.agent_guess_answer or "Proceed as you see fit.")
    pending = [a for a in run["actions"] if a["review_state"] == "PENDING"]
    if pending:
        return _review("APPROVE", pending[0])
    if "execute" in task["available_operations"]:
        return Step("execute")
    return Step("cancel")


REVIEWERS = {"attentive": attentive, "approve-all": approve_all}
