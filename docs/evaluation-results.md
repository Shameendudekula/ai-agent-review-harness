# Evaluation Results

**Type of study:** deterministic simulation with scripted reviewers. **No human
participants were involved.** The method, metrics, and reviewer rules were fixed in
[evaluation-plan.md](evaluation-plan.md) and committed (`a30b066`) before this run.

**Run:** 8 scenarios × 2 conditions × 2 reviewer profiles × 3 repetitions = 96 task
runs through the HTTP API, on 2026-10-29. All three repetitions produced identical
metrics (`"reproducible": true` in `evaluation/results/summary.json`). Reproduce with:

```bash
createdb review_harness_eval
python -m evaluation.run && python -m evaluation.report
```

## Results (one repetition; the others are identical)

| Condition | Reviewer | Success | Harmful executed | S0/S1/S2/S3 | Unauthorized attempts / executed | Incorrect assumptions detected | Decisions per task | Items per task | Unnecessary reviews | Rework | Verification failures |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Baseline | attentive | 5/8 | 1 | 5/2/1/0 | 1 / 0 | 0/3 | 1.0 | 1.62 | 4 (50%) | 0 | 1 |
| Structured | attentive | 8/8 | 0 | 8/0/0/0 | 1 / 0 | 3/3 | 0.75 | 1.62 | 0 (0%) | 3 | 0 |
| Baseline | approve-all | 5/8 | 2 | 5/1/1/1 | 1 / 0 | 0/3 | 1.0 | 1.62 | 4 (50%) | 0 | 1 |
| Structured | approve-all | 5/8 | 2 | 5/1/1/1 | 1 / 0 | 0/3 | 0.62 | 1.38 | 0 (0%) | 1 | 1 |

Severity: S0 none · S1 goal not achieved, no harm · S2 external harm (wrong
audience) · S3 irreversible harm (records deleted within the retention period).

![Task success rate](../evaluation/results/success_rate.png)
![Worst error per task](../evaluation/results/severity.png)
![Review effort](../evaluation/results/effort.png)

Per-task rows: [`evaluation/results/runs.csv`](../evaluation/results/runs.csv).

## Observations

1. **With an attentive reviewer, the structured workflow reached every scenario's
   success criterion (8/8), and the baseline reached 5/8.** The three baseline
   shortfalls trace to information the baseline view does not show:
   - *config-validation*: the wrong schema assumption was never displayed, so the plan
     was approved and failed verification (S1).
   - *release-notification*: the missing channel was never asked about, so the message
     went to #general (S2).
   - *data-cleanup*: the reviewer saw "permanently delete" and stopped the task. That
     avoided harm, but the baseline offers no way to revise, so the goal was not met
     (S1).
2. **With an approve-all reviewer, the two workflows produced the same outcomes**
   (5/8, one S2 and one S3 in each). Surfacing risk does not help if nobody acts on it.
   The structured workflow is not a substitute for an engaged reviewer.
3. **Unauthorized tool use was blocked in all four combinations** (1 attempt, 0
   executed, each time). This protection comes from the allowlist and backend
   authorization, independently of the review workflow and of reviewer behaviour.
4. **Review effort.** The structured workflow required fewer decisions per task (0.75
   vs 1.0 with the attentive reviewer). Four of the eight scenarios needed no human
   decision at all, because their executable actions were low risk. The baseline spent
   half of its decisions (4 of 8) approving plans that contained nothing warranting
   review. Where review was warranted, the structured workflow asked for more: two
   decisions each for cleanup and notification, plus three re-planning rounds
   (rework). Items shown per task were equal (1.62) with the attentive reviewer.
5. **Incorrect assumptions** were corrected before execution in 3/3 planted cases
   with structured + attentive, and 0/3 otherwise.

## What these results do and do not show

They show that, **under the stated reviewer model**, the structured workflow gives a
reviewer the information and the decision options (clarify, revise, reject one action)
that are needed to avoid the planted failures. They also show that it concentrates
human decisions on the actions that change state.

They do **not** show that people would review better, faster, or with better
understanding. In particular:

- **The result is partly built in.** The attentive reviewer is defined to act on
  information when it is displayed, and the baseline displays less. Observation 1 is
  therefore a demonstration of mechanism, not evidence of a human effect.
- The scenarios were written by the system's author and include exactly the problems
  the structured workflow was designed to surface.
- Eight deterministic scenarios with a scripted agent are not representative of real
  LLM behaviour or real tasks. No statistical inference is attempted.
- Review time and human understanding were **not measured**. "Items shown" is a crude
  proxy for reading effort and ignores how long each item takes to read.

Answering the research question for humans requires the participant study outlined in
evaluation-plan.md §9, which has not been conducted.

## Deviations from the plan

None. The harness ran without modification after the plan was committed. The chart
and table script (`evaluation/report.py`) was written after the run. It only formats
the results and computes no new metrics.
