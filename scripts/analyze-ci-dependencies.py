#!/usr/bin/env python3
"""Analyze GitHub Actions CI workflow job dependencies and output a dependency graph.

This script parses CI workflow YAML files and:
1. Extracts all job definitions and their dependencies
2. Builds a dependency graph
3. Identifies critical path (longest chain of dependencies)
4. Detects potential parallelization opportunities
5. Outputs ASCII graph and optimization suggestions

Usage:
    python scripts/analyze-ci-dependencies.py [workflow-file]
    python scripts/analyze-ci-dependencies.py  # defaults to .github/workflows/ci.yml

Output formats:
    --format text    ASCII dependency graph (default)
    --format mermaid Mermaid diagram syntax
    --format json    JSON dependency data
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml


def load_workflow(workflow_path: Path) -> dict:
    """Load and parse a GitHub Actions workflow YAML file."""
    with open(workflow_path) as f:
        return yaml.safe_load(f)


def extract_jobs(workflow: dict) -> dict[str, dict]:
    """Extract job definitions from workflow."""
    return workflow.get("jobs", {})


def build_dependency_graph(jobs: dict[str, dict]) -> dict[str, list[str]]:
    """Build a dependency graph from job definitions.

    Returns:
        Dict mapping job names to list of jobs they depend on
    """
    graph = {}
    for job_name, job_def in jobs.items():
        needs = job_def.get("needs", [])
        # Handle both string and list formats
        if isinstance(needs, str):
            needs = [needs]
        graph[job_name] = needs
    return graph


def build_reverse_graph(graph: dict[str, list[str]]) -> dict[str, list[str]]:
    """Build reverse dependency graph (what depends on each job)."""
    reverse = defaultdict(list)
    for job, deps in graph.items():
        for dep in deps:
            reverse[dep].append(job)
    # Include jobs with no dependents
    for job in graph:
        if job not in reverse:
            reverse[job] = []
    return dict(reverse)


def find_root_jobs(graph: dict[str, list[str]]) -> list[str]:
    """Find jobs with no dependencies (roots of the DAG)."""
    return sorted([job for job, deps in graph.items() if not deps])


def find_leaf_jobs(graph: dict[str, list[str]]) -> list[str]:
    """Find jobs that nothing depends on (leaves of the DAG)."""
    reverse = build_reverse_graph(graph)
    return sorted([job for job, dependents in reverse.items() if not dependents])


def calculate_depths(graph: dict[str, list[str]]) -> dict[str, int]:
    """Calculate the depth (longest path from root) for each job."""
    depths: dict[str, int] = {}

    def get_depth(job: str) -> int:
        if job in depths:
            return depths[job]

        deps = graph.get(job, [])
        if not deps:
            depths[job] = 0
        else:
            depths[job] = max(get_depth(dep) for dep in deps) + 1

        return depths[job]

    for job in graph:
        get_depth(job)

    return depths


def find_critical_path(graph: dict[str, list[str]]) -> list[str]:
    """Find the critical path (longest dependency chain)."""
    depths = calculate_depths(graph)

    if not depths:
        return []

    # Start from the deepest job
    max_depth = max(depths.values())
    deepest_jobs = [job for job, depth in depths.items() if depth == max_depth]

    # Trace back to root
    path = []
    current = deepest_jobs[0]

    while current:
        path.append(current)
        deps = graph.get(current, [])
        if not deps:
            break
        # Follow the deepest dependency
        current = max(deps, key=lambda j: depths.get(j, 0))

    return list(reversed(path))


def get_job_display_name(job_name: str, jobs: dict[str, dict]) -> str:
    """Get the display name for a job."""
    job_def = jobs.get(job_name, {})
    return job_def.get("name", job_name)


def format_text_graph(graph: dict[str, list[str]], jobs: dict[str, dict]) -> str:
    """Format dependency graph as ASCII text."""
    lines = []
    lines.append("=" * 80)
    lines.append("CI WORKFLOW DEPENDENCY GRAPH")
    lines.append("=" * 80)
    lines.append("")

    depths = calculate_depths(graph)
    root_jobs = find_root_jobs(graph)
    leaf_jobs = find_leaf_jobs(graph)
    critical_path = find_critical_path(graph)

    # Summary
    lines.append(f"Total jobs: {len(graph)}")
    lines.append(f"Root jobs (no dependencies): {len(root_jobs)}")
    lines.append(f"Leaf jobs (no dependents): {len(leaf_jobs)}")
    lines.append(f"Max depth: {max(depths.values()) if depths else 0}")
    lines.append(f"Critical path length: {len(critical_path)}")
    lines.append("")

    # Root jobs (can run immediately)
    lines.append("-" * 40)
    lines.append("ROOT JOBS (Start Immediately)")
    lines.append("-" * 40)
    for job in root_jobs:
        display_name = get_job_display_name(job, jobs)
        lines.append(f"  - {job}")
        if display_name != job:
            lines.append(f"    ({display_name})")
    lines.append("")

    # Jobs by depth level
    lines.append("-" * 40)
    lines.append("JOBS BY DEPTH LEVEL")
    lines.append("-" * 40)
    max_depth = max(depths.values()) if depths else 0
    for depth in range(max_depth + 1):
        jobs_at_depth = sorted([j for j, d in depths.items() if d == depth])
        lines.append(f"\nLevel {depth}:")
        for job in jobs_at_depth:
            deps = graph.get(job, [])
            display_name = get_job_display_name(job, jobs)
            deps_str = f" <- [{', '.join(deps)}]" if deps else ""
            lines.append(f"  {job}{deps_str}")
    lines.append("")

    # Critical path
    lines.append("-" * 40)
    lines.append("CRITICAL PATH (Longest Chain)")
    lines.append("-" * 40)
    for i, job in enumerate(critical_path):
        prefix = "  " + ("-> " if i > 0 else "   ")
        lines.append(f"{prefix}{job}")
    lines.append("")

    # Dependency visualization
    lines.append("-" * 40)
    lines.append("DEPENDENCY TREE")
    lines.append("-" * 40)

    def print_tree(job: str, prefix: str = "", is_last: bool = True) -> None:
        connector = "`-- " if is_last else "|-- "
        lines.append(f"{prefix}{connector}{job}")

        reverse = build_reverse_graph(graph)
        dependents = sorted(reverse.get(job, []))

        for i, dependent in enumerate(dependents):
            ext = "    " if is_last else "|   "
            print_tree(dependent, prefix + ext, i == len(dependents) - 1)

    for i, root in enumerate(root_jobs):
        if i > 0:
            lines.append("")
        print_tree(root, "", i == len(root_jobs) - 1)

    return "\n".join(lines)


def format_mermaid_graph(graph: dict[str, list[str]], jobs: dict[str, dict]) -> str:
    """Format dependency graph as Mermaid diagram."""
    lines = ["graph TD"]

    # Add nodes with display names
    for job in sorted(graph.keys()):
        display_name = get_job_display_name(job, jobs)
        safe_name = display_name.replace('"', "'")
        lines.append(f'    {job}["{safe_name}"]')

    lines.append("")

    # Add edges
    for job, deps in sorted(graph.items()):
        for dep in sorted(deps):
            lines.append(f"    {dep} --> {job}")

    # Style critical path
    critical_path = find_critical_path(graph)
    if critical_path:
        lines.append("")
        lines.append("    %% Critical path highlighted")
        for job in critical_path:
            lines.append(f"    style {job} fill:#f96")

    return "\n".join(lines)


def format_json_graph(graph: dict[str, list[str]], jobs: dict[str, dict]) -> str:
    """Format dependency graph as JSON."""
    depths = calculate_depths(graph)
    reverse = build_reverse_graph(graph)

    data = {
        "summary": {
            "total_jobs": len(graph),
            "root_jobs": find_root_jobs(graph),
            "leaf_jobs": find_leaf_jobs(graph),
            "critical_path": find_critical_path(graph),
            "max_depth": max(depths.values()) if depths else 0,
        },
        "jobs": {
            job: {
                "display_name": get_job_display_name(job, jobs),
                "depends_on": deps,
                "dependents": reverse.get(job, []),
                "depth": depths.get(job, 0),
            }
            for job, deps in graph.items()
        },
    }

    return json.dumps(data, indent=2)


def analyze_parallelization(graph: dict[str, list[str]]) -> list[str]:
    """Analyze potential parallelization improvements."""
    suggestions = []
    depths = calculate_depths(graph)
    reverse = build_reverse_graph(graph)

    # Check for unnecessary sequential dependencies
    for job, deps in graph.items():
        if len(deps) == 1:
            dep = deps[0]
            # If the dependency has no other dependents at the same depth,
            # it might be an unnecessary chain
            dep_dependents = reverse.get(dep, [])
            if len(dep_dependents) == 1:
                suggestions.append(
                    f"POTENTIAL: '{job}' only depends on '{dep}' - "
                    f"verify if dependency is necessary"
                )

    # Check for jobs that could share a dependency
    depth_groups = defaultdict(list)
    for job, depth in depths.items():
        depth_groups[depth].append(job)

    for _depth, jobs_at_depth in depth_groups.items():
        if len(jobs_at_depth) > 1:
            # Check if they share similar dependency patterns
            deps_by_job = {j: frozenset(graph.get(j, [])) for j in jobs_at_depth}
            unique_dep_sets = set(deps_by_job.values())
            if len(unique_dep_sets) < len(jobs_at_depth):
                pass  # Some jobs share dependencies - this is good

    return suggestions


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze CI workflow job dependencies")
    parser.add_argument(
        "workflow",
        nargs="?",
        default=".github/workflows/ci.yml",
        help="Path to workflow YAML file",
    )
    parser.add_argument(
        "--format",
        choices=["text", "mermaid", "json"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    workflow_path = Path(args.workflow)
    if not workflow_path.exists():
        print(f"Error: Workflow file not found: {workflow_path}", file=sys.stderr)
        return 1

    try:
        workflow = load_workflow(workflow_path)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}", file=sys.stderr)
        return 1

    jobs = extract_jobs(workflow)
    if not jobs:
        print("No jobs found in workflow", file=sys.stderr)
        return 1

    graph = build_dependency_graph(jobs)

    if args.format == "text":
        print(format_text_graph(graph, jobs))
        print("")
        print("-" * 40)
        print("PARALLELIZATION ANALYSIS")
        print("-" * 40)
        suggestions = analyze_parallelization(graph)
        if suggestions:
            for suggestion in suggestions:
                print(f"  {suggestion}")
        else:
            print("  No obvious improvements detected")
    elif args.format == "mermaid":
        print(format_mermaid_graph(graph, jobs))
    elif args.format == "json":
        print(format_json_graph(graph, jobs))

    return 0


if __name__ == "__main__":
    sys.exit(main())
