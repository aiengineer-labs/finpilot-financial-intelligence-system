"""Summarize a Promptfoo red-team results file into FinPilot's committed evaluation evidence.

Usage:
  python summarize_redteam.py RESULTS_JSON REPORT_JSON --evidence EVIDENCE_JSON \
      --dataset-version V --code-version C --target-model M --grader-model G [--container-digest D]

REPORT_JSON (evaluation/reports) keeps counts, rates and short grader reasons for failures.
EVIDENCE_JSON (apps/api/app/evidence) is the subset the governance gate reads. Generated attack
text and full model output stay in the git-ignored results file.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CRITICAL = "critical"


def _rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    results = data.get("results", {})
    rows = results.get("results") if isinstance(results, dict) else results
    if not isinstance(rows, list):
        raise SystemExit("results file has no results list")
    return rows


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in (row.get("testCase", {}).get("metadata"), row.get("metadata")):
        if isinstance(source, dict):
            merged.update(source)
    return merged


def _outcome(row: dict[str, Any]) -> str:
    if row.get("error") and not row.get("gradingResult"):
        return "error"
    return "passed" if row.get("success") else "failed"


def summarize(data: dict[str, Any], digest: str | None) -> dict[str, Any]:
    rows = _rows(data)
    totals: Counter[str] = Counter()
    by_plugin: dict[str, Counter[str]] = defaultdict(Counter)
    by_strategy: dict[str, Counter[str]] = defaultdict(Counter)
    layers: Counter[str] = Counter()
    severities: dict[str, str] = {}
    failures: list[dict[str, Any]] = []
    tokens = Counter()
    for row in rows:
        meta = _meta(row)
        plugin = str(meta.get("pluginId") or "unknown")
        strategy = str(meta.get("strategyId") or "basic")
        severity = str(meta.get("severity") or "unspecified")
        severities[plugin] = severity
        outcome = _outcome(row)
        totals[outcome] += 1
        by_plugin[plugin][outcome] += 1
        by_strategy[strategy][outcome] += 1
        response = row.get("response") or {}
        layer = (response.get("metadata") or {}).get("layer") or ("error" if outcome == "error" else "unknown")
        layers[str(layer)] += 1
        usage = response.get("tokenUsage") or {}
        tokens["target_total"] += int(usage.get("total") or 0)
        if outcome == "failed":
            reason = str((row.get("gradingResult") or {}).get("reason") or "")
            failures.append(
                {
                    "plugin": plugin,
                    "strategy": strategy,
                    "severity": severity,
                    "layer": layer,
                    "verification": (response.get("metadata") or {}).get("verification"),
                    "grader_reason": " ".join(reason.split())[:300],
                }
            )
    graded = totals["passed"] + totals["failed"]
    critical_graded = sum(
        counts["passed"] + counts["failed"]
        for plugin, counts in by_plugin.items()
        if severities.get(plugin) == CRITICAL
    )
    critical_failed = sum(
        counts["failed"] for plugin, counts in by_plugin.items() if severities.get(plugin) == CRITICAL
    )
    stats = data.get("results", {}).get("stats", {}) if isinstance(data.get("results"), dict) else {}
    usage = stats.get("tokenUsage") or {}
    grading = usage.get("assertions") or {}
    return {
        "schema_version": "1.0",
        "evaluation": "FinPilot authorized model-based red team against the live advisor",
        "summarized_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": {"name": "promptfoo", "version": "0.124.1", "container_digest": digest},
        "target": "finpilot-live-advisor (evaluation/promptfoo/live_advice_provider.py)",
        "dataset": "evaluation/datasets/synthetic_household_v1.csv",
        "result": {
            "cases": len(rows),
            "passed": totals["passed"],
            "failed": totals["failed"],
            "errors": totals["error"],
            "attack_success_rate": round(totals["failed"] / graded, 4) if graded else None,
            "critical_cases_graded": critical_graded,
            "critical_failed": critical_failed,
            "critical_attack_success_rate": (
                round(critical_failed / critical_graded, 4) if critical_graded else None
            ),
            "tokens_target": tokens["target_total"],
            "tokens_grading": int(grading.get("total") or 0),
            "duration_ms": int(stats.get("durationMs") or 0),
        },
        "stopping_layer": dict(layers.most_common()),
        "by_plugin": {
            plugin: {"severity": severities.get(plugin), **dict(counts)}
            for plugin, counts in sorted(by_plugin.items())
        },
        "by_strategy": {strategy: dict(counts) for strategy, counts in sorted(by_strategy.items())},
        "failures": failures,
        "scope": (
            "Bounded synthetic probe set; a passing result is evidence for these probes, "
            "not a claim of immunity."
        ),
    }


def findings(report: dict[str, Any]) -> list[str]:
    """One readable line per plugin and strategy where an attack succeeded."""

    grouped: Counter[tuple[str, str, str]] = Counter(
        (item["plugin"], item["strategy"], item["severity"]) for item in report["failures"]
    )
    return [
        f"{plugin} via {strategy} ({severity}): {count} attack{'s' if count != 1 else ''} succeeded"
        for (plugin, strategy, severity), count in sorted(grouped.items())
    ]


def evidence(report: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    result = report["result"]
    return {
        "dataset_version": args.dataset_version,
        "report": args.report,
        "code_version": args.code_version,
        "target_model": args.target_model,
        "grader_model": args.grader_model,
        "sampling_method": (
            f"Promptfoo {report['tool']['version']}: {result['cases']} Mesh-generated probes "
            f"against the live advisor, graded by {args.grader_model}"
        ),
        "duration_ms": result["duration_ms"],
        "metrics": {
            key: result[key]
            for key in (
                "cases", "passed", "failed", "errors", "attack_success_rate",
                "critical_cases_graded", "critical_failed", "critical_attack_success_rate",
            )
        },
        "findings": findings(report),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results")
    parser.add_argument("report")
    parser.add_argument("--evidence")
    parser.add_argument("--dataset-version")
    parser.add_argument("--code-version")
    parser.add_argument("--target-model")
    parser.add_argument("--grader-model")
    parser.add_argument("--container-digest")
    args = parser.parse_args()
    data = json.loads(Path(args.results).read_text())
    report = summarize(data, args.container_digest)
    Path(args.report).write_text(json.dumps(report, indent=2) + "\n")
    if args.evidence:
        record = evidence(report, args)
        Path(args.evidence).write_text(json.dumps(record, indent=2) + "\n")
        print("findings:", json.dumps(record["findings"], indent=1))
    print(json.dumps(report["result"], indent=2))
    print(json.dumps(report["stopping_layer"]))


if __name__ == "__main__":
    main()
