# Evaluation Plan

## 1. Objective

Evaluate whether a structured human-in-the-loop review workflow improves task outcomes while balancing review effort and unnecessary interruptions.

The evaluation will compare a basic approval-or-stop workflow with the proposed review workflow.

## 2. Research Question

How does a calibrated human-in-the-loop review mechanism affect task success, rework, review effort, and human understanding when supervising an AI coding agent, compared with a basic approval-or-stop interaction model?

This is a proposed project research question, not an approved university research question.

## 3. Evaluation Conditions

### Condition A: Baseline

A basic workflow in which a human can approve or stop a proposed agent action.

### Condition B: Proposed Review Workflow

A workflow that exposes assumptions, supports clarification and revision, uses risk-based review checkpoints, and records human decisions.

Both conditions should use the same predefined tasks and comparable task success criteria.

## 4. Initial Evaluation Tasks

Create a small, reproducible set of software engineering tasks covering:

- A straightforward, low-risk task.
- A task with an incorrect or unsupported assumption.
- A task proposing an action with security implications.
- A task requiring clarification because information is missing.
- A task in which a proposed action should be rejected and revised.

Use deterministic mock-agent behavior initially so that the same scenarios can be repeated.

## 5. Metrics

### Task Success Rate

Percentage of evaluated tasks that satisfy their predefined success criteria.

### Error Count and Severity

Number of observed errors, classified using documented severity categories.

### Intervention Count

Number of human review interventions required per task.

### Review Time

Time spent inspecting proposals and making review decisions, measured consistently across conditions.

### Rework

Number of revisions or repeated work attempts needed to reach the required outcome.

### Incorrect Assumptions Detected

Number of predefined incorrect assumptions identified before they cause an unsuccessful or unsafe outcome.

### Human Understanding

If an appropriate study design is approved, assess whether participants can correctly explain important agent assumptions, decisions, and outcomes.

## 6. Measurement Rules

Define each metric and its calculation before collecting evaluation results.

Use the same task definitions and success criteria across comparison conditions.

Record actual observations and distinguish measured results from simulated demonstration data.

Do not infer causal improvements from a small or uncontrolled comparison.

## 7. Experimental Procedure

1. Define the task set and expected outcomes.
2. Specify the baseline and proposed workflows.
3. Define measurement rules before collecting results.
4. Execute repeatable scenarios.
5. Record outcomes, errors, interventions, review time, and rework.
6. Compare results using appropriate descriptive summaries.
7. Discuss limitations and alternative explanations.
8. Report only results supported by collected evidence.

## 8. Human Participants and Privacy

The initial evaluation can use deterministic simulated tasks without human participants.

If a later study involves people, obtain appropriate supervisory approval, informed consent, and privacy safeguards before collecting participant data.

Do not collect unnecessary personal information.

## 9. Threats to Validity

Potential limitations include:

- Small numbers of evaluation tasks.
- Scenarios that do not represent real-world agent behavior.
- Differences in task difficulty.
- Measurement bias.
- Mock-agent behavior that is more predictable than a real LLM.
- Learning effects between evaluation conditions.

Document these limitations alongside the results.

## 10. Reporting Requirements

Report the evaluation setup, task definitions, metrics, observed results, and limitations.

Do not fabricate participants, measurements, performance improvements, or statistical significance.

Clearly label mock results, sample data, and actual measurements.

## 11. Acceptance Criteria

- Baseline and proposed conditions are defined.
- Repeatable evaluation tasks are specified.
- Metrics and measurement rules are documented.
- Data collection and analysis procedures are described.
- Limitations and privacy considerations are documented.
- No unsupported claims of effectiveness are made.