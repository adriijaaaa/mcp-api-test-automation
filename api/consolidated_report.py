
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path


REPORT_FILES = {
    "rule_based": Path("reports/test_run_report.json"),
    "ai_assisted": Path("reports/ai_test_run_report.json"),
    "boundary_value": Path("reports/boundary_test_report.json"),
}

OUTPUT_FILE = Path("reports/consolidated_report.json")
HTML_OUTPUT_FILE = Path("reports/consolidated_report.html")


def load_report(suite_name, report_path):
    """Load one suite's report and validate its basic structure."""

    if not report_path.exists():
        raise FileNotFoundError(
            f"Missing report for {suite_name}: {report_path}. "
            "Run that test suite first."
        )

    report = json.loads(report_path.read_text(encoding="utf-8"))

    if not isinstance(report.get("results"), list):
        raise ValueError(
            f"Invalid report structure in {report_path}: "
            "'results' must be a list."
        )

    return report


def build_consolidated_report():
    """Combine the latest saved reports from all three test suites."""

    summaries = {}
    all_results = []

    for suite_name, report_path in REPORT_FILES.items():
        report = load_report(suite_name, report_path)
        results = report["results"]

        passed = sum(
            1 for result in results if result.get("passed") is True
        )
        failed = len(results) - passed

        summaries[suite_name] = {
            "source_report": str(report_path),
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "pass_rate_percent": round(
                passed / len(results) * 100, 2
            ) if results else 0,
        }

        for result in results:
            all_results.append({
                "suite": suite_name,
                **result,
            })

    total = len(all_results)
    passed_total = sum(
        1 for result in all_results
        if result.get("passed") is True
    )
    failed_total = total - passed_total

    failures = [
        {
            "suite": result["suite"],
            "name": result.get(
                "name", result.get("test_name", "Unnamed test")
            ),
            "expected_status": result.get("expected_status"),
            "actual_status": result.get("actual_status"),
            "error": result.get("error"),
            "failed_checks": [
                check.get("check", "Unknown check")
                for check in result.get("checks", [])
                if not check.get("passed", False)
            ],
        }
        for result in all_results
        if result.get("passed") is not True
    ]

    consolidated = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suite_count": len(summaries),
        "overall_status": "PASS" if failed_total == 0 else "FAIL",
        "total": total,
        "passed": passed_total,
        "failed": failed_total,
        "pass_rate_percent": round(
            passed_total / total * 100, 2
        ) if total else 0,
        "suite_summaries": summaries,
        "failures": failures,
        "results": all_results,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(consolidated, indent=2),
        encoding="utf-8",
    )

    generate_html_report(consolidated)

    print("\nCONSOLIDATED API TEST REPORT")
    print("=" * 55)

    for suite_name, summary in summaries.items():
        print(
            f"{suite_name:15} "
            f"Total: {summary['total']:2} | "
            f"Passed: {summary['passed']:2} | "
            f"Failed: {summary['failed']:2} | "
            f"Pass rate: {summary['pass_rate_percent']}%"
        )

    print("-" * 55)
    print(f"Total suites: {len(summaries)}")
    print(f"Total tests:  {total}")
    print(f"Passed:       {passed_total}")
    print(f"Failed:       {failed_total}")
    print(f"Pass rate:    {consolidated['pass_rate_percent']}%")
    print(f"Overall:      {consolidated['overall_status']}")

    if failures:
        print("\nFAILED TESTS")
        for failure in failures:
            print(f"- [{failure['suite']}] {failure['name']}")
            if failure["failed_checks"]:
                print(
                    f"  Failed checks: "
                    f"{', '.join(failure['failed_checks'])}"
                )
            if failure["error"]:
                print(f"  Error: {failure['error']}")

    print(f"\nSaved JSON report: {OUTPUT_FILE}")
    print(f"Saved HTML report: {HTML_OUTPUT_FILE}")

    return consolidated


def generate_html_report(report):
    """Generate a self-contained HTML dashboard from consolidated results."""

    def safe(value):
        return escape(str(value if value is not None else "—"))

    status = report["overall_status"]
    status_class = "pass" if status == "PASS" else "fail"

    suite_rows = ""
    for name, summary in report["suite_summaries"].items():
        suite_rows += f"""
        <tr>
          <td>{safe(name)}</td>
          <td>{summary['total']}</td>
          <td>{summary['passed']}</td>
          <td>{summary['failed']}</td>
          <td>{summary['pass_rate_percent']}%</td>
        </tr>
        """

    result_rows = ""
    for result in report["results"]:
        passed = result.get("passed") is True
        result_status = "PASS" if passed else "FAIL"
        result_class = "pass" if passed else "fail"
        name = result.get(
            "name", result.get("test_name", "Unnamed test")
        )
        checks = result.get("checks", [])
        failed_checks = [
            check.get("check", "Unknown check")
            for check in checks
            if not check.get("passed", False)
        ]
        details = result.get("error") or (
            ", ".join(failed_checks) if failed_checks else "—"
        )

        result_rows += f"""
        <tr>
          <td>{safe(result['suite'])}</td>
          <td>{safe(name)}</td>
          <td><span class="badge {result_class}">
            {result_status}</span></td>
          <td>{safe(result.get('expected_status'))}</td>
          <td>{safe(result.get('actual_status'))}</td>
          <td>{safe(details)}</td>
        </tr>
        """

    generated_at = safe(report.get("generated_at"))
    pass_rate = report["pass_rate_percent"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>API Test Automation Report</title>
<style>
:root {{
  color-scheme: light;
  font-family: Arial, sans-serif;
  background: #f4f7fb;
  color: #172033;
}}
body {{ margin: 0; padding: 28px; }}
main {{ max-width: 1200px; margin: auto; }}
header, .card, section {{
  background: white; border-radius: 14px;
  padding: 22px; margin-bottom: 20px;
  box-shadow: 0 3px 14px #1720330d;
}}
h1 {{ margin-top: 0; }}
.muted {{ color: #64748b; font-size: 14px; }}
.cards {{
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 14px; margin-bottom: 20px;
}}
.metric {{ font-size: 28px; font-weight: bold; margin-top: 8px; }}
.pass {{ color: #137547; }}
.fail {{ color: #b42318; }}
.badge {{
  display: inline-block; padding: 4px 9px;
  border-radius: 20px; font-weight: bold; font-size: 12px;
  background: #e8f7ef;
}}
.badge.fail {{ background: #fdecec; }}
.progress {{
  background: #e5eaf1; border-radius: 10px;
  overflow: hidden; height: 12px; margin-top: 12px;
}}
.bar {{ height: 100%; background: #15945b; }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{
  padding: 12px; border-bottom: 1px solid #e8edf3;
  text-align: left; vertical-align: top;
}}
th {{ background: #f8fafc; }}
td {{ overflow-wrap: anywhere; }}
@media (max-width: 700px) {{
  body {{ padding: 12px; }}
  .cards {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>
<main>
<header>
  <h1>API Test Automation Report</h1>
  <p class="muted">Generated at {generated_at}</p>
  <span class="badge {status_class}">Overall: {status}</span>
  <div class="progress">
    <div class="bar" style="width: {pass_rate}%"></div>
  </div>
  <p>{pass_rate}% pass rate</p>
</header>

<div class="cards">
  <div class="card"><div class="muted">Total tests</div>
    <div class="metric">{report['total']}</div></div>
  <div class="card"><div class="muted">Passed</div>
    <div class="metric pass">{report['passed']}</div></div>
  <div class="card"><div class="muted">Failed</div>
    <div class="metric fail">{report['failed']}</div></div>
  <div class="card"><div class="muted">Test suites</div>
    <div class="metric">{report['suite_count']}</div></div>
</div>

<section>
<h2>Suite Summary</h2>
<div class="table-wrap"><table>
<thead><tr><th>Suite</th><th>Total</th><th>Passed</th>
<th>Failed</th><th>Pass rate</th></tr></thead>
<tbody>{suite_rows}</tbody>
</table></div>
</section>

<section>
<h2>Individual Test Results</h2>
<div class="table-wrap"><table>
<thead><tr><th>Suite</th><th>Test</th><th>Status</th>
<th>Expected HTTP</th><th>Actual HTTP</th><th>Error / failed checks</th>
</tr></thead>
<tbody>{result_rows or '<tr><td colspan="6">No test results found.</td></tr>'}</tbody>
</table></div>
</section>
<footer class="muted">
  Generated by the MCP-Powered API Test Automation Framework.
</footer>
</main>
</body>
</html>
"""

    HTML_OUTPUT_FILE.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    build_consolidated_report()
