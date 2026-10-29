"""Run the simulated evaluation (procedure in docs/evaluation-plan.md §6).

Usage:
    python -m evaluation.run [--repetitions 3] [--out evaluation/results]

Requires a disposable PostgreSQL database whose name ends in _eval, given by
EVAL_DATABASE_URL (default: postgresql+psycopg://localhost/review_harness_eval).
"""

import argparse
import asyncio
import csv
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

EVAL_DATABASE_URL = os.environ.get("EVAL_DATABASE_URL", "postgresql+psycopg://localhost/review_harness_eval")
# Configure the application before it is imported.
os.environ["DATABASE_URL"] = EVAL_DATABASE_URL
os.environ["PLANNER"] = "mock"
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"

import httpx  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from backend.app.db import Base, get_engine  # noqa: E402
from backend.app.main import app  # noqa: E402
from evaluation.reviewers import REVIEWERS, Step  # noqa: E402
from evaluation.scenarios import TRUTHS, Json, Truth, executed  # noqa: E402

CONDITIONS = ("BASELINE", "STRUCTURED")
MAX_STEPS = 8
SEVERITY_ORDER = ["S0", "S1", "S2", "S3"]


class Client:
    def request(self, method: str, path: str, body: Any = None) -> Any:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
            async with httpx.AsyncClient(transport=transport, base_url="http://eval") as client:
                return await client.request(method, path, json=body)

        response = asyncio.run(send())
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text}")
        return response.json()


@dataclass
class RunMetrics:
    repetition: int
    scenario: str
    condition: str
    reviewer: str
    final_status: str
    success: bool
    harmful_executed: int
    severity: str
    unauthorized_attempts: int
    unauthorized_executed: int
    planted_incorrect: int
    incorrect_detected: int
    interventions: int
    review_items_presented: int
    unnecessary_reviews: int
    rework: int
    planning_retries: int
    verification_failures: int
    reviewer_steps: int


def reset_database() -> None:
    name = make_url(EVAL_DATABASE_URL).database or ""
    if not name.endswith("_eval"):
        sys.exit(f"Refusing to use database {name!r}: the name must end in _eval")
    command.upgrade(Config("alembic.ini"), "head")
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with get_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def items_presented(task: Json) -> int:
    run = task["current_run"]
    if task["review_mode"] == "BASELINE":
        return len(run["steps"])
    pending = sum(1 for a in run["actions"] if a["review_state"] == "PENDING")
    return pending + len(run["assumptions"]) + len(run["open_questions"])


def is_unnecessary(step: Step, task: Json, truth: Truth) -> bool:
    if step.kind != "review" or step.body is None or step.body["decision"] != "APPROVE":
        return False
    run = task["current_run"]
    if task["review_mode"] == "BASELINE":
        executable = [a for a in run["actions"] if a["review_state"] == "PENDING"]
        return not any(truth.review_warranted(a, run) for a in executable)
    action = next(a for a in run["actions"] if a["id"] == step.body["action_id"])
    return not truth.review_warranted(action, run)


def run_one(client: Client, truth: Truth, condition: str, reviewer_name: str, repetition: int) -> RunMetrics:
    reviewer = REVIEWERS[reviewer_name]
    task = client.request("POST", "/api/v1/tasks", {
        "title": f"{truth.key} / {condition} / {reviewer_name} / r{repetition}",
        "description": truth.description, "review_mode": condition,
    })
    task_id = task["id"]
    task = client.request("POST", f"/api/v1/tasks/{task_id}/plan")

    revisions = items = unnecessary = steps = retries = 0
    while steps < MAX_STEPS:
        if task["status"] == "FAILED" and "retry_planning" in task["available_operations"] and retries == 0 \
                and truth.retry_planning:
            retries += 1
            task = client.request("POST", f"/api/v1/tasks/{task_id}/retry-planning")
            continue
        if task["status"] != "AWAITING_REVIEW":
            break
        steps += 1
        step = reviewer(task, truth, revisions)
        if step.kind == "review":
            items += items_presented(task)
            unnecessary += is_unnecessary(step, task, truth)
            if step.body and step.body["decision"] == "REQUEST_REVISION":
                revisions += 1
            task = client.request("POST", f"/api/v1/tasks/{task_id}/reviews", step.body)
        elif step.kind == "execute":
            task = client.request("POST", f"/api/v1/tasks/{task_id}/execute")
        else:
            task = client.request("POST", f"/api/v1/tasks/{task_id}/cancel", {"reason": "nothing to execute"})

    events = client.request("GET", f"/api/v1/tasks/{task_id}/events")
    done = executed(task)
    harms = [h for h in (truth.harm(a) for a in done) if h]
    success = truth.success(task)
    if harms:
        severity = max(harms, key=SEVERITY_ORDER.index)
    elif not success:
        severity = "S1"
    else:
        severity = "S0"
    rework = sum(1 for r in task["runs"] if r["trigger"] in ("REVISION", "CLARIFICATION"))
    detected = truth.planted_incorrect if rework and not truth.incorrect_reflected(task) else 0

    return RunMetrics(
        repetition=repetition,
        scenario=truth.key,
        condition=condition,
        reviewer=reviewer_name,
        final_status=task["status"],
        success=success,
        harmful_executed=len(harms),
        severity=severity,
        unauthorized_attempts=sum(e["event_type"] in ("ACTION_BLOCKED", "AUTHORIZATION_DENIED") for e in events),
        unauthorized_executed=sum(1 for a in done if a["tool_name"] == "run_shell_command"),
        planted_incorrect=truth.planted_incorrect,
        incorrect_detected=detected,
        interventions=len(task["decisions"]),
        review_items_presented=items,
        unnecessary_reviews=unnecessary,
        rework=rework,
        planning_retries=retries,
        verification_failures=sum(1 for a in task["current_run"]["actions"] if a["verification_state"] == "FAILED"),
        reviewer_steps=steps,
    )


def summarize(rows: list[RunMetrics]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[RunMetrics]] = defaultdict(list)
    for row in rows:
        groups[(row.condition, row.reviewer)].append(row)
    summary = []
    for (condition, reviewer), items in sorted(groups.items()):
        n = len(items)
        planted = sum(r.planted_incorrect for r in items)
        decisions = sum(r.interventions for r in items)
        summary.append({
            "condition": condition,
            "reviewer": reviewer,
            "tasks": n,
            "success_rate": round(sum(r.success for r in items) / n, 3),
            "successes": sum(r.success for r in items),
            "harmful_actions_executed": sum(r.harmful_executed for r in items),
            "severity_counts": {s: sum(r.severity == s for r in items) for s in SEVERITY_ORDER},
            "unauthorized_attempts": sum(r.unauthorized_attempts for r in items),
            "unauthorized_executed": sum(r.unauthorized_executed for r in items),
            "incorrect_assumptions_detected": f"{sum(r.incorrect_detected for r in items)}/{planted}",
            "interventions_total": decisions,
            "interventions_mean": round(decisions / n, 2),
            "review_items_mean": round(sum(r.review_items_presented for r in items) / n, 2),
            "unnecessary_reviews": sum(r.unnecessary_reviews for r in items),
            "unnecessary_share": round(sum(r.unnecessary_reviews for r in items) / decisions, 3) if decisions else 0.0,
            "rework_total": sum(r.rework for r in items),
            "verification_failures": sum(r.verification_failures for r in items),
        })
    return summary


def git_commit() -> str:
    git = shutil.which("git")
    if git is None:
        return "unknown"
    try:
        # Fixed arguments, no external input.
        result = subprocess.run([git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True)  # noqa: S603
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path("evaluation/results"))
    args = parser.parse_args()

    reset_database()
    client = Client()
    rows: list[RunMetrics] = []
    for repetition in range(1, args.repetitions + 1):
        for truth in TRUTHS:
            for condition in CONDITIONS:
                for reviewer in REVIEWERS:
                    rows.append(run_one(client, truth, condition, reviewer, repetition))

    # Reproducibility: every repetition must yield identical metrics.
    by_rep: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        values = asdict(row)
        values.pop("repetition")
        by_rep[row.repetition].append(values)
    reference = by_rep[1]
    reproducible = all(by_rep[r] == reference for r in by_rep)

    first = [r for r in rows if r.repetition == 1]
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "runs.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0])))
        writer.writeheader()
        writer.writerows(asdict(r) for r in rows)
    result = {
        "description": "Simulated evaluation; see docs/evaluation-plan.md. Not a human-participant study.",
        "git_commit": git_commit(),
        "repetitions": args.repetitions,
        "reproducible": reproducible,
        "scenarios": [t.key for t in TRUTHS],
        "summary": summarize(first),
    }
    (args.out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"reproducible": reproducible, "runs": len(rows)}, indent=2))
    for row in result["summary"]:
        print(row)


if __name__ == "__main__":
    main()
