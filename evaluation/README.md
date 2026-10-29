# Evaluation harness

Simulated comparison of the baseline (approve-or-stop) and structured review
workflows. Method: [docs/evaluation-plan.md](../docs/evaluation-plan.md). Results:
[docs/evaluation-results.md](../docs/evaluation-results.md).

| File | Role |
|---|---|
| `scenarios.py` | Ground truth per scenario: success criteria, harm, domain facts |
| `reviewers.py` | Deterministic simulated reviewers (attentive, approve-all) |
| `run.py` | Drives the real HTTP API in-process, computes metrics, checks reproducibility |
| `report.py` | Renders charts and the summary table from `results/summary.json` |
| `results/` | Committed outputs of the last run |

```bash
createdb review_harness_eval        # must end in _eval; it is emptied on every run
python -m evaluation.run --repetitions 3
python -m evaluation.report
```

Override the database with `EVAL_DATABASE_URL`.
