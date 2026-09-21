"""Markdown report renderer for the first benchmark."""

from __future__ import annotations

from typing import Any


def render_hohmann_report(*, run: dict[str, Any], experiment: dict[str, Any], receipt: dict[str, Any] | None = None) -> str:
    gate = experiment["gate"]
    selected = next(item for item in experiment["candidates"] if item["candidate_id"] == experiment["selected_candidate_id"])
    lines = [
        "# Auditable Scientist Lab — Hohmann vertical slice",
        "",
        f"- Run: `{run['run_id']}`",
        f"- Status: `{run['status']}`",
        "- Evidence level: `validated-reproduction` within a committed analytic fixture",
        "- Network: disabled; all calculations are offline",
        "",
        "## Question",
        "",
        "Can a bounded candidate search recover the heliocentric Hohmann transfer time-of-flight expression and pass a fixed holdout and dimensional gate?",
        "",
        "## Candidate result",
        "",
        f"- Candidate: `{selected['candidate_id']}`",
        f"- Expression: `{selected['expression']}`",
        f"- Dimensional status: `{selected['dimensional_status']}`",
        f"- Candidate-set hash: `{experiment['candidate_set_hash']}`",
        f"- Train RMSE (days): `{selected['train_rmse']:.12g}`",
        f"- Holdout RMSE (days): `{selected['holdout_rmse']:.12g}`",
        f"- Holdout threshold (days): `{gate['threshold']:.12g}`",
        f"- Holdout gate: `{gate['passed']}` ({gate['reason']})",
        "",
        "## Candidate ranking",
        "",
        "| Candidate | Dimensional | Complexity | Train RMSE (days) | Holdout RMSE (days) |",
        "|---|---|---:|---:|---:|",
    ]
    for candidate in sorted(experiment["candidates"], key=lambda item: (item["train_rmse"], item["complexity"], item["candidate_id"])):
        lines.append(
            f"| `{candidate['candidate_id']}` | `{candidate['dimensional_status']}` | {candidate['complexity']} | "
            f"{candidate['train_rmse']:.6g} | {candidate['holdout_rmse']:.6g} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- The dataset is a local committed fixture derived from the project-05 analytic baseline; it is not a real-data validation.",
            "- The selected formula reproduces the declared calculation within this input domain; this is not a novelty, production, or publication claim.",
            "- The external symbolic-physics-engine adapter remains blocked pending a path, revision, and license.",
            "",
            "## Replay",
            "",
            f"- Manifest verification: `{receipt['verified'] if receipt else 'pending'}`",
            f"- Checks: `{', '.join(receipt['checks']) if receipt else 'run replay command'}`",
            "",
        ]
    )
    return "\n".join(lines)
