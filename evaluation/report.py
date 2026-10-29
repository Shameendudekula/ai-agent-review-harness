"""Render charts and markdown tables from evaluation/results/summary.json.

Usage: python -m evaluation.report [--results evaluation/results]
"""

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
# Categorical slots 1-2 (validated: CVD ΔE 24.7, all checks pass on the light surface).
CONDITION_COLOR = {"BASELINE": "#2a78d6", "STRUCTURED": "#eb6834"}
CONDITION_LABEL = {"BASELINE": "Baseline (approve-or-stop)", "STRUCTURED": "Structured (risk-based)"}
# Severity is an ordered state, so it uses the reserved status palette with labels.
SEVERITY_COLOR = {"S0": "#0ca30c", "S1": "#fab219", "S2": "#ec835a", "S3": "#d03b3b"}
SEVERITY_LABEL = {
    "S0": "S0 none",
    "S1": "S1 not achieved, no harm",
    "S2": "S2 external harm",
    "S3": "S3 irreversible harm",
}
REVIEWERS = ("attentive", "approve-all")
CONDITIONS = ("BASELINE", "STRUCTURED")


def style(ax: Any, title: str, ylabel: str | None = None) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=TEXT, fontsize=12, fontweight="bold", pad=12)
    if ylabel:
        ax.set_ylabel(ylabel, color=TEXT_SECONDARY, fontsize=10)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def grouped_bars(ax: Any, rows: dict[tuple[str, str], dict[str, Any]], metric: str, fmt: str) -> None:
    width = 0.34
    for i, condition in enumerate(CONDITIONS):
        xs = [r + (i - 0.5) * (width + 0.02) for r in range(len(REVIEWERS))]
        values = [rows[(condition, reviewer)][metric] for reviewer in REVIEWERS]
        bars = ax.bar(xs, values, width, color=CONDITION_COLOR[condition], label=CONDITION_LABEL[condition],
                      edgecolor=SURFACE, linewidth=2)
        for bar, value in zip(bars, values, strict=True):
            ax.annotate(fmt.format(value), (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", color=TEXT, fontsize=9)
    ax.set_xticks(range(len(REVIEWERS)), [f"{r} reviewer" for r in REVIEWERS])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("evaluation/results"))
    args = parser.parse_args()
    data = json.loads((args.results / "summary.json").read_text())
    rows = {(r["condition"], r["reviewer"]): r for r in data["summary"]}
    plt.rcParams.update({"font.family": "sans-serif", "figure.facecolor": SURFACE})

    fig, ax = plt.subplots(figsize=(7, 4))
    grouped_bars(ax, rows, "success_rate", "{:.0%}")
    style(ax, "Task success rate (8 simulated scenarios)", "share of tasks meeting the success criterion")
    ax.set_ylim(0, 1.15)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.legend(frameon=False, fontsize=9, loc="upper right", labelcolor=TEXT)
    fig.tight_layout()
    fig.savefig(args.results / "success_rate.png", dpi=160)

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    labels, lefts = [], [0.0] * 4
    order = [(c, r) for r in REVIEWERS for c in CONDITIONS]
    for key in order:
        labels.append(f"{'Structured' if key[0] == 'STRUCTURED' else 'Baseline'} · {key[1]}")
    for severity in SEVERITY_COLOR:
        counts = [rows[key]["severity_counts"][severity] for key in order]
        bars = ax.barh(range(4), counts, left=lefts, color=SEVERITY_COLOR[severity], label=SEVERITY_LABEL[severity],
                       edgecolor=SURFACE, linewidth=2, height=0.6)
        for bar, count in zip(bars, counts, strict=True):
            if count:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_y() + bar.get_height() / 2, str(count),
                        ha="center", va="center", color=TEXT, fontsize=9)
        lefts = [a + b for a, b in zip(lefts, counts, strict=True)]
    ax.set_yticks(range(4), labels)
    ax.invert_yaxis()
    style(ax, "Worst error per task (count of 8 tasks)")
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_xlim(0, 8)
    ax.legend(frameon=False, fontsize=8, ncols=4, loc="upper center", bbox_to_anchor=(0.45, -0.12), labelcolor=TEXT)
    fig.tight_layout()
    fig.savefig(args.results / "severity.png", dpi=160)

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), sharey=False)
    grouped_bars(axes[0], rows, "interventions_mean", "{:.2f}")
    style(axes[0], "Human decisions per task")
    grouped_bars(axes[1], rows, "review_items_mean", "{:.2f}")
    style(axes[1], "Review items shown per task (effort proxy)")
    for ax in axes:
        ax.set_ylim(0, max(ax.get_ylim()[1], 2.0) * 1.15)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, frameon=False, fontsize=9, ncols=2, loc="lower center", labelcolor=TEXT)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(args.results / "effort.png", dpi=160)

    header = ("| Condition | Reviewer | Success | Harmful executed | S0/S1/S2/S3 | Unauthorized attempts / executed "
              "| Incorrect assumptions detected | Decisions per task | Items per task | Unnecessary reviews | Rework "
              "| Verification failures |")
    lines = [header, "|" + "---|" * 12]
    for (condition, reviewer), r in sorted(rows.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        sev = r["severity_counts"]
        lines.append(
            f"| {condition.title()} | {reviewer} | {r['successes']}/{r['tasks']} | {r['harmful_actions_executed']} "
            f"| {sev['S0']}/{sev['S1']}/{sev['S2']}/{sev['S3']} "
            f"| {r['unauthorized_attempts']} / {r['unauthorized_executed']} "
            f"| {r['incorrect_assumptions_detected']} | {r['interventions_mean']} | {r['review_items_mean']} "
            f"| {r['unnecessary_reviews']} ({r['unnecessary_share']:.0%}) | {r['rework_total']} "
            f"| {r['verification_failures']} |"
        )
    (args.results / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
