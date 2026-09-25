"""CLI Tool for Reproducing SkyZen AI & Meteorological Benchmarks (Phase 32).

Usage:
    python scripts/run_benchmarks.py
    python scripts/run_benchmarks.py --output reports/benchmark_report.json --markdown
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai.evaluation.benchmark_evaluator import SkyZenBenchmarkEvaluator


def format_markdown_report(report: dict) -> str:
    """Formats benchmark results as a GitHub-flavored Markdown table."""
    metrics = report.get("metrics", {})
    env = report.get("test_environment", {})

    lines = [
        "# SkyZen AI & Meteorological System Evaluation Benchmark Report",
        "",
        f"**Generated:** {report.get('generated_at')}",
        f"**Environment:** {env.get('platform')}, Python {env.get('python_version')}",
        "",
        "> [!NOTE]",
        f"> {report.get('general_disclaimer')}",
        "",
        "## Evaluated Metrics (12/12)",
        "",
        "| Metric Name | Sample Size | Value | Unit | Definition |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]

    for k, v in metrics.items():
        name = v.get("metric_name", k)
        sample = v.get("sample_size", "-")
        val = v.get("value", "-")
        unit = v.get("unit", "")
        defn = v.get("metric_definition", "")

        if isinstance(val, dict):
            val_str = f"p50: {val.get('p50_ms')}ms, p95: {val.get('p95_ms')}ms"
        else:
            val_str = f"{val}{'%' if unit == 'percent' else ''}"

        lines.append(f"| `{name}` | {sample} | **{val_str}** | {unit} | {defn} |")

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run reproducible SkyZen benchmarks.")
    parser.add_argument("--output", type=str, default="reports/skyzen_benchmark_report.json",
                        help="Output path for machine-readable JSON evaluation report.")
    parser.add_argument("--markdown", action="store_true",
                        help="Also save a markdown summary alongside the JSON report.")
    parser.add_argument("--verbose", action="store_true",
                        help="Print detailed evaluation traces.")

    args = parser.parse_args()

    print("================================================================")
    print("           SKYZEN AI & METEOROLOGICAL EVALUATION               ")
    print("================================================================")
    print("Running deterministic evaluation across 12 target metrics...\n")

    evaluator = SkyZenBenchmarkEvaluator()
    report = evaluator.run_all_benchmarks()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[+] Machine-readable report saved to: {out_path.resolve()}")

    if args.markdown:
        md_path = out_path.with_suffix(".md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(format_markdown_report(report))
        print(f"[+] Markdown summary saved to: {md_path.resolve()}")

    # Print summary table
    print("\n----------------------------------------------------------------")
    print(f"{'METRIC NAME':<38} | {'SAMPLE':<8} | {'RESULT':<12}")
    print("----------------------------------------------------------------")
    for k, v in report["metrics"].items():
        sample = v.get("sample_size", "-")
        val = v.get("value", "-")
        unit = v.get("unit", "")
        if isinstance(val, dict):
            res_str = f"{val.get('p50_ms')} ms (p50)"
        else:
            res_str = f"{val} {'%' if unit == 'percent' else unit}"
        print(f"{k:<38} | {str(sample):<8} | {res_str:<12}")
    print("----------------------------------------------------------------")
    print(f"\n[NOTE] {report.get('general_disclaimer')}\n")


if __name__ == "__main__":
    main()
