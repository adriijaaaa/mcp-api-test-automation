
import json
from datetime import datetime, timezone
from pathlib import Path


REPORT_FILES = {
    "rule_based": Path("reports/test_run_report.json"),
    "ai_assisted": Path("reports/ai_test_run_report.json"),
    "boundary_value": Path("reports/boundary_test_report.json"),
}

OUTPUT_FILE = Path("reports/consolidated_report.json")


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
            "name": result.get("name", result.get("test_name", "Unnamed test")),
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

    print(f"\nSaved report: {OUTPUT_FILE}")

    return consolidated


if __name__ == "__main__":
    build_consolidated_report()
