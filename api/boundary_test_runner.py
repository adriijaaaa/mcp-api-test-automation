
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx


API_URL = "http://127.0.0.1:8000"
REPORT_FILE = Path("reports/boundary_test_report.json")


def build_boundary_cases():
    """Create boundary-value and invalid-type test cases."""

    cases = []

    def add_case(name, payload, expected_status, invalid_field=None):
        cases.append({
            "name": name,
            "method": "POST",
            "path": "/products",
            "payload": payload,
            "expected_status": expected_status,
            "invalid_field": invalid_field,
        })

    # Name boundaries: minimum 2, maximum 100 characters.
    add_case(
        "Name: empty string",
        {"name": "", "price": 10, "stock": 5},
        422,
        "name",
    )
    add_case(
        "Name: 1 character",
        {"name": "A", "price": 10, "stock": 5},
        422,
        "name",
    )
    add_case(
        "Name: minimum valid length (2)",
        {"name": "AB", "price": 10, "stock": 5},
        201,
    )
    add_case(
        "Name: maximum valid length (100)",
        {"name": "N" * 100, "price": 10, "stock": 5},
        201,
    )
    add_case(
        "Name: 1 over maximum (101)",
        {"name": "N" * 101, "price": 10, "stock": 5},
        422,
        "name",
    )

    # Price boundaries: must be greater than zero.
    add_case(
        "Price: negative",
        {"name": "Price Test", "price": -1, "stock": 5},
        422,
        "price",
    )
    add_case(
        "Price: zero",
        {"name": "Price Test", "price": 0, "stock": 5},
        422,
        "price",
    )
    add_case(
        "Price: positive",
        {"name": "Price Test", "price": 0.01, "stock": 5},
        201,
    )

    # Stock boundaries: must be an integer >= 0.
    add_case(
        "Stock: negative",
        {"name": "Stock Test", "price": 10, "stock": -1},
        422,
        "stock",
    )
    add_case(
        "Stock: zero",
        {"name": "Stock Test", "price": 10, "stock": 0},
        201,
    )
    add_case(
        "Stock: positive integer",
        {"name": "Stock Test", "price": 10, "stock": 1},
        201,
    )

    # Invalid data types.
    add_case(
        "Price: non-numeric string",
        {"name": "Type Test", "price": "abc", "stock": 5},
        422,
        "price",
    )
    add_case(
        "Stock: fractional number",
        {"name": "Type Test", "price": 10, "stock": 1.5},
        422,
        "stock",
    )
    add_case(
        "Name: integer instead of string",
        {"name": 123, "price": 10, "stock": 5},
        422,
        "name",
    )

    return cases


def validate_response(case, response):
    """Check status, JSON response, and relevant response content."""

    checks = []
    expected = case["expected_status"]
    actual = response.status_code

    checks.append({
        "check": "status_code",
        "passed": actual == expected,
        "expected": expected,
        "actual": actual,
    })

    try:
        body = response.json()
        is_json = True
    except ValueError:
        body = None
        is_json = False

    checks.append({
        "check": "response_is_json",
        "passed": is_json,
        "expected": "JSON response",
        "actual": "JSON" if is_json else "Non-JSON response",
    })

    if not is_json:
        return checks, None

    if expected == 201:
        is_object = isinstance(body, dict)

        checks.append({
            "check": "created_product_is_object",
            "passed": is_object,
            "expected": "JSON object",
            "actual": type(body).__name__,
        })

        if is_object:
            has_id = (
                isinstance(body.get("id"), int)
                and not isinstance(body.get("id"), bool)
            )

            checks.append({
                "check": "created_product_has_id",
                "passed": has_id,
                "expected": "Integer product ID",
                "actual": body.get("id"),
            })

            payload_matches = all(
                body.get(key) == value
                for key, value in case["payload"].items()
            )

            checks.append({
                "check": "created_product_matches_payload",
                "passed": payload_matches,
                "expected": case["payload"],
                "actual": {
                    key: body.get(key)
                    for key in case["payload"]
                },
            })

    elif expected == 422:
        details = body.get("detail") if isinstance(body, dict) else None
        has_details = isinstance(details, list) and bool(details)

        checks.append({
            "check": "validation_error_details",
            "passed": has_details,
            "expected": "Non-empty detail list",
            "actual": details,
        })

        if has_details:
            reported_fields = {
                str(error["loc"][-1])
                for error in details
                if isinstance(error, dict)
                and isinstance(error.get("loc"), list)
                and error["loc"]
            }

            expected_field = case.get("invalid_field")
            field_matches = (
                expected_field in reported_fields
                if expected_field
                else True
            )

            checks.append({
                "check": "error_matches_invalid_field",
                "passed": field_matches,
                "expected": expected_field,
                "actual": sorted(reported_fields),
            })

    return checks, body


def run_boundary_tests():
    """Run all boundary cases and save a JSON report."""

    cases = build_boundary_cases()
    results = []

    print("\nEXECUTING BOUNDARY-VALUE TESTS")
    print("=" * 65)

    with httpx.Client(timeout=10) as client:
        for case in cases:
            started = datetime.now(timezone.utc)

            try:
                response = client.request(
                    method=case["method"],
                    url=API_URL + case["path"],
                    json=case["payload"],
                )

                checks, body = validate_response(case, response)
                passed = all(check["passed"] for check in checks)

                result = {
                    "name": case["name"],
                    "payload": case["payload"],
                    "expected_status": case["expected_status"],
                    "actual_status": response.status_code,
                    "duration_ms": round(
                        response.elapsed.total_seconds() * 1000,
                        2,
                    ),
                    "response_body": body,
                    "checks": checks,
                    "passed": passed,
                    "error": None,
                }

            except (httpx.HTTPError, ValueError) as exc:
                result = {
                    "name": case["name"],
                    "payload": case["payload"],
                    "expected_status": case["expected_status"],
                    "actual_status": None,
                    "duration_ms": None,
                    "response_body": None,
                    "checks": [],
                    "passed": False,
                    "error": str(exc),
                }

            result["executed_at"] = started.isoformat()
            results.append(result)

            print(f"\nTest: {result['name']}")

            for check in result["checks"]:
                status = "PASS" if check["passed"] else "FAIL"
                print(f"  {status}: {check['check']}")

            print(
                f"  Overall: {'PASS' if result['passed'] else 'FAIL'}"
            )

            if result["error"]:
                print(f"  Error: {result['error']}")

    passed_count = sum(result["passed"] for result in results)
    failed_count = len(results) - passed_count

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_url": API_URL,
        "total": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "pass_rate_percent": round(
            passed_count / len(results) * 100, 2
        ) if results else 0,
        "results": results,
    }

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 65)
    print(f"Total:     {len(results)}")
    print(f"Passed:    {passed_count}")
    print(f"Failed:    {failed_count}")
    print(f"Pass rate: {report['pass_rate_percent']}%")
    print(f"Report:    {REPORT_FILE}")

    return report


if __name__ == "__main__":
    run_boundary_tests()
