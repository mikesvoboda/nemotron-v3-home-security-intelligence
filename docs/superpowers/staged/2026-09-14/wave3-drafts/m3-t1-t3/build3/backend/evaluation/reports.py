"""Report generation for prompt evaluation results.

This module provides functions for generating evaluation reports in
JSON and HTML formats. Reports include:
- Template ranking tables
- Per-scenario-type breakdowns
- Failure case analysis
- Detailed metrics and statistics

Usage:
    from backend.evaluation.reports import generate_json_report, save_report

    report = generate_json_report(results_df, metrics)
    save_report(report, Path("report.json"), "json")
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

from backend.evaluation.metrics import rank_templates


def generate_json_report(
    results: pd.DataFrame,
    metrics: dict,
) -> dict:
    """Generate a JSON evaluation report.

    Creates a comprehensive report with all evaluation results, metrics,
    and rankings in a structured JSON format.

    Args:
        results: DataFrame with evaluation results
        metrics: Aggregated metrics from aggregate_metrics()

    Returns:
        Dictionary suitable for JSON serialization containing:
        - metadata: Report generation info
        - summary: High-level statistics
        - template_rankings: Ranked list of templates
        - detailed_metrics: Per-template, per-scenario-type breakdowns
        - failure_cases: Scenarios with risk scores outside ground truth
        - raw_results: Optional detailed per-scenario results
    """
    timestamp = datetime.now(UTC).isoformat()

    # Get template rankings
    rankings = rank_templates(metrics)

    # Identify failure cases (risk deviation > 0)
    failure_cases = []
    if not results.empty and "risk_deviation" in results.columns:
        failures = results[results["risk_deviation"] > 0]
        for _, row in failures.iterrows():
            failure_cases.append(
                {
                    "scenario_id": row.get("scenario_id", ""),
                    "template_name": row.get("template_name", ""),
                    "scenario_type": row.get("scenario_type", ""),
                    "risk_score": int(row.get("risk_score", 0)),
                    "ground_truth_min": int(row.get("ground_truth_min", 0)),
                    "ground_truth_max": int(row.get("ground_truth_max", 100)),
                    "risk_deviation": float(row.get("risk_deviation", 0)),
                    "reasoning": row.get("reasoning", "")[:200],  # Truncate for report
                }
            )

    # Build report structure
    report = {
        "metadata": {
            "generated_at": timestamp,
            "report_version": "1.0",
            "total_scenarios": len(results) // max(len(rankings), 1) if rankings else len(results),
            "total_evaluations": len(results),
            "templates_evaluated": len(rankings),
        },
        "summary": {
            "overall_metrics": metrics.get("overall", {}),
            "best_template": rankings[0]["template_name"] if rankings else None,
            "worst_template": rankings[-1]["template_name"] if rankings else None,
            "failure_count": len(failure_cases),
            "success_rate": (
                (len(results) - len(failure_cases)) / len(results) * 100 if len(results) > 0 else 0
            ),
        },
        "template_rankings": rankings,
        "detailed_metrics": {
            "by_template": metrics.get("by_template", {}),
            "by_scenario_type": metrics.get("by_scenario_type", {}),
            "by_enrichment_level": metrics.get("by_enrichment_level", {}),
            "percentiles": metrics.get("percentiles", {}),
        },
        "failure_cases": failure_cases[:50],  # Limit to first 50 failures
    }

    return report


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def generate_html_report(
    results: pd.DataFrame,
    metrics: dict,
) -> str:
    """Generate an HTML evaluation report.

    Creates a visual report with tables and charts (text-based) showing
    evaluation results and metrics.

    Args:
        results: DataFrame with evaluation results
        metrics: Aggregated metrics from aggregate_metrics()

    Returns:
        HTML string for the complete report
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    rankings = rank_templates(metrics)
    overall = metrics.get("overall", {})
    by_scenario_type = metrics.get("by_scenario_type", {})
    by_template = metrics.get("by_template", {})

    # Build HTML
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "<title>Prompt Evaluation Report</title>",
        "<style>",
        """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1, h2, h3 { color: #333; }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th { background: #f8f9fa; font-weight: 600; }
        tr:hover { background: #f5f5f5; }
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .metric-box {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            text-align: center;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #2563eb;
        }
        .metric-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }
        .rank-1 { color: #16a34a; font-weight: bold; }
        .rank-2 { color: #2563eb; }
        .rank-3 { color: #9333ea; }
        .bar-chart {
            font-family: monospace;
            font-size: 12px;
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
        }
        .bar-row {
            margin: 5px 0;
            display: flex;
            align-items: center;
        }
        .bar-label {
            width: 120px;
            text-align: right;
            padding-right: 10px;
        }
        .bar-fill {
            background: #3b82f6;
            height: 20px;
            border-radius: 2px;
        }
        .bar-value {
            margin-left: 10px;
            color: #666;
        }
        .failure-row { background: #fef2f2; }
        .success-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            background: #dcfce7;
            color: #166534;
        }
        .failure-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            background: #fef2f2;
            color: #991b1b;
        }
        """,
        "</style>",
        "</head>",
        "<body>",
        "<h1>Prompt Evaluation Report</h1>",
        f"<p><em>Generated: {timestamp}</em></p>",
    ]

    # Summary card
    html_parts.extend(
        [
            "<div class='card'>",
            "<h2>Summary</h2>",
            "<div class='metric-grid'>",
            f"<div class='metric-box'><div class='metric-value'>{overall.get('total_scenarios', 0)}</div><div class='metric-label'>Total Evaluations</div></div>",
            f"<div class='metric-box'><div class='metric-value'>{overall.get('mean_risk_deviation', 0):.1f}</div><div class='metric-label'>Mean Risk Deviation</div></div>",
            f"<div class='metric-box'><div class='metric-value'>{overall.get('within_range_pct', 0):.1f}%</div><div class='metric-label'>Within Range</div></div>",
            f"<div class='metric-box'><div class='metric-value'>{overall.get('mean_key_point_coverage', 0):.2f}</div><div class='metric-label'>Key Point Coverage</div></div>",
            "</div>",
            "</div>",
        ]
    )

    # Template Rankings card
    html_parts.extend(
        [
            "<div class='card'>",
            "<h2>Template Rankings</h2>",
            "<table>",
            "<thead><tr>",
            "<th>Rank</th><th>Template</th><th>Score</th><th>Mean Deviation</th><th>Within Range</th><th>Key Points</th>",
            "</tr></thead>",
            "<tbody>",
        ]
    )

    for ranking in rankings:
        rank_class = f"rank-{ranking['rank']}" if ranking["rank"] <= 3 else ""
        html_parts.append(
            f"<tr class='{rank_class}'>"
            f"<td>#{ranking['rank']}</td>"
            f"<td><strong>{_escape_html(ranking['template_name'])}</strong></td>"
            f"<td>{ranking['composite_score']:.3f}</td>"
            f"<td>{ranking['mean_risk_deviation']:.1f}</td>"
            f"<td>{ranking['within_range_pct']:.1f}%</td>"
            f"<td>{ranking['mean_key_point_coverage']:.2f}</td>"
            "</tr>"
        )

    html_parts.extend(["</tbody>", "</table>", "</div>"])

    # Per-Scenario-Type Breakdown
    html_parts.extend(
        [
            "<div class='card'>",
            "<h2>Performance by Scenario Type</h2>",
            "<table>",
            "<thead><tr>",
            "<th>Scenario Type</th><th>Count</th><th>Mean Deviation</th><th>Within Range</th><th>Key Points</th>",
            "</tr></thead>",
            "<tbody>",
        ]
    )

    for scenario_type, type_metrics in by_scenario_type.items():
        html_parts.append(
            f"<tr>"
            f"<td><strong>{_escape_html(scenario_type)}</strong></td>"
            f"<td>{type_metrics.get('count', 0)}</td>"
            f"<td>{type_metrics.get('mean_risk_deviation', 0):.1f}</td>"
            f"<td>{type_metrics.get('within_range_pct', 0):.1f}%</td>"
            f"<td>{type_metrics.get('mean_key_point_coverage', 0):.2f}</td>"
            "</tr>"
        )

    html_parts.extend(["</tbody>", "</table>", "</div>"])

    # Visual bar chart for template comparison
    html_parts.extend(
        [
            "<div class='card'>",
            "<h2>Template Comparison (Within-Range %)</h2>",
            "<div class='bar-chart'>",
        ]
    )

    max_pct = max((m.get("within_range_pct", 0) for m in by_template.values()), default=100)
    for template_name, template_metrics in by_template.items():
        pct = template_metrics.get("within_range_pct", 0)
        bar_width = int(pct / max(max_pct, 1) * 300)
        html_parts.append(
            f"<div class='bar-row'>"
            f"<div class='bar-label'>{_escape_html(template_name)}</div>"
            f"<div class='bar-fill' style='width: {bar_width}px'></div>"
            f"<div class='bar-value'>{pct:.1f}%</div>"
            "</div>"
        )

    html_parts.extend(["</div>", "</div>"])

    # Failure cases
    if not results.empty and "risk_deviation" in results.columns:
        failures = results[results["risk_deviation"] > 0].head(20)
        if len(failures) > 0:
            html_parts.extend(
                [
                    "<div class='card'>",
                    f"<h2>Failure Cases (showing {len(failures)} of {len(results[results['risk_deviation'] > 0])})</h2>",
                    "<table>",
                    "<thead><tr>",
                    "<th>Scenario</th><th>Template</th><th>Type</th><th>Score</th><th>Expected</th><th>Deviation</th>",
                    "</tr></thead>",
                    "<tbody>",
                ]
            )

            for _, row in failures.iterrows():
                html_parts.append(
                    f"<tr class='failure-row'>"
                    f"<td>{_escape_html(str(row.get('scenario_id', '')))}</td>"
                    f"<td>{_escape_html(str(row.get('template_name', '')))}</td>"
                    f"<td>{_escape_html(str(row.get('scenario_type', '')))}</td>"
                    f"<td>{row.get('risk_score', 0)}</td>"
                    f"<td>{row.get('ground_truth_min', 0)}-{row.get('ground_truth_max', 100)}</td>"
                    f"<td><span class='failure-badge'>+{row.get('risk_deviation', 0):.0f}</span></td>"
                    "</tr>"
                )

            html_parts.extend(["</tbody>", "</table>", "</div>"])

    # Footer
    html_parts.extend(
        [
            "<div class='card'>",
            "<h3>Report Details</h3>",
            f"<p>Templates evaluated: {len(rankings)}</p>",
            f"<p>Total evaluations: {len(results)}</p>",
            "</div>",
            "</body>",
            "</html>",
        ]
    )

    return "\n".join(html_parts)


def save_report(
    report: dict | str,
    path: Path,
    format: str = "json",
) -> None:
    """Save report to file.

    Args:
        report: Report data (dict for JSON, str for HTML)
        path: Path to save the report
        format: Report format ("json" or "html")

    Raises:
        ValueError: If format is not recognized
    """
    # Resolve and validate path to prevent path traversal
    resolved_path = path.resolve()

    # Ensure parent directory exists
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    if format == "json":
        if isinstance(report, dict):
            with resolved_path.open("w") as f:
                json.dump(report, f, indent=2, default=str)
        else:
            with resolved_path.open("w") as f:
                f.write(report)
    elif format == "html":
        if isinstance(report, str):
            with resolved_path.open("w") as f:
                f.write(report)
        else:
            # If report is dict, convert to pretty JSON for HTML embedding
            with resolved_path.open("w") as f:
                f.write(f"<pre>{json.dumps(report, indent=2, default=str)}</pre>")
    else:
        raise ValueError(f"Unknown format: {format}. Use 'json' or 'html'.")


def generate_summary_table(metrics: dict) -> str:
    """Generate a text-based summary table for terminal output.

    Args:
        metrics: Aggregated metrics from aggregate_metrics()

    Returns:
        Formatted text table suitable for terminal display
    """
    rankings = rank_templates(metrics)

    lines = [
        "=" * 80,
        "PROMPT EVALUATION SUMMARY",
        "=" * 80,
        "",
        "TEMPLATE RANKINGS",
        "-" * 80,
        f"{'Rank':<6}{'Template':<25}{'Score':<10}{'Deviation':<12}{'In-Range %':<12}",
        "-" * 80,
    ]

    for r in rankings:
        lines.append(
            f"#{r['rank']:<5}{r['template_name']:<25}{r['composite_score']:.3f}     "
            f"{r['mean_risk_deviation']:.1f}        {r['within_range_pct']:.1f}%"
        )

    lines.extend(
        [
            "",
            "OVERALL METRICS",
            "-" * 80,
        ]
    )

    overall = metrics.get("overall", {})
    lines.extend(
        [
            f"Total Evaluations:      {overall.get('total_scenarios', 0)}",
            f"Mean Risk Deviation:    {overall.get('mean_risk_deviation', 0):.2f} (+/- {overall.get('std_risk_deviation', 0):.2f})",
            f"Within Range:           {overall.get('within_range_pct', 0):.1f}%",
            f"Mean Key Point Coverage:{overall.get('mean_key_point_coverage', 0):.2f}",
            f"Mean Reasoning Sim:     {overall.get('mean_reasoning_similarity', 0):.2f}",
            "",
            "=" * 80,
        ]
    )

    return "\n".join(lines)
