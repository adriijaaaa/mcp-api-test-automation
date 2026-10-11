
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx


API_URL = "http://127.0.0.1:8000"

CASES_FILE = Path("test_data/generated_cases.json")
REPORT_FILE = Path("reports/test_run_report.json")


def validate_response(case, response):
    """Validate HTTP status and relevant response-body properties."""

    checks = []

    expected_status = case["expected_status"]
    actual_status = response.status_code

    checks.append({
        "check": "status_code",
        "passed": actual_status == expected_status,
        "expected": expected_status,
        "actual": actual_status,
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
        return checks

    # Successful product creation should return the product.
    if expected_status == 201:
        payload = case.get("payload", {})

        is_object = isinstance(body, dict)

        checks.append({
            "check": "created_product_is_object",
            "passed": is_object,
            "expected": "JSON object",
            "actual": type(body).__name__,
        })

        if is_object:
            has_id = isinstance(body.get("id"), int) and not isinstance(
                body.get("id"), bool
            )

            checks.append({
                "check": "created_product_has_id",
                "passed": has_id,
                "expected": "Integer product ID",
                "actual": body.get("id"),
            })

            fields_match = all(
                body.get(key) == value
                for key, value in payload.items()
            )

            checks.append({
                "check": "created_product_matches_payload",
                "passed": fields_match,
                "expected": payload,
                "actual": {
                    key: body.get(key)
                    for key in payload
                },
            })

    # Negative validation tests should return structured errors.
    if expected_status == 422:
        has_detail = (
            isinstance(body, dict)
            and isinstance(body.get("detail"), list)
            and len(body["detail"]) > 0
        )

        checks.append({
            "check": "validation_error_details",
            "passed": has_detail,
            "expected": "Non-empty detail list",
            "actual": (
                body.get("detail")
                if isinstance(body, dict)
                else body
            ),
        })

        if has_detail:
            reported_fields = {
                str(error["loc"][-1])
                for error in body["detail"]
                if isinstance(error, dict)
                and isinstance(error.get("loc"), list)
                and error["loc"]
            }

            payload = case.get("payload", {})
            invalid_fields = []

            name = payload.get("name")
            price = payload.get("price")
            stock = payload.get("stock")

            if "name" not in payload:
                invalid_fields.append("name")
            elif not isinstance(name, str) or not 2 <= len(name) <= 100:
                invalid_fields.append("name")

            if (
                isinstance(price, bool)
                or not isinstance(price, (int, float))
                or price <= 0
            ):
                invalid_fields.append("price")

            if (
                isinstance(stock, bool)
                or not isinstance(stock, int)
                or stock < 0
            ):
                invalid_fields.append("stock")

            if invalid_fields:
                relevant_error_found = bool(
                    set(invalid_fields) & reported_fields
                )
            else:
                # For other 422 cases, require structured error details.
                relevant_error_found = has_detail

            checks.append({
                "check": "error_matches_invalid_field",
                "passed": relevant_error_found,
                "expected": invalid_fields or "Relevant validation error",
                "actual": sorted(reported_fields),
            })

    return checks


def run_tests():
    """Execute generated test cases and save a detailed report."""

    if not CASES_FILE.exists():
        raise FileNotFoundError(
            f"Test cases not found: {CASES_FILE}. "
            "Run python -m api.test_generator first."
        )

    cases = json.loads(
        CASES_FILE.read_text(encoding="utf-8")
    )

    results = []

    print("\nEXECUTING RULE-BASED API TESTS")
    print("=" * 60)

    with httpx.Client(timeout=10) as client:
        for case in cases:
            started_at = datetime.now(timezone.utc)

            try:
                response = client.request(
                    method=case["method"],
                    url=API_URL + case["path"],
                    json=case.get("payload"),
                )

                checks = validate_response(case, response)
                passed = all(check["passed"] for check in checks)

                content_type = response.headers.get(
                    "content-type", ""
                )

                if "application/json" in content_type:
                    response_body = response.json()
                else:
                    response_body = response.text[:1000]

                result = {
                    "name": case["name"],
                    "method": case["method"],
                    "path": case["path"],
                    "payload": case.get("payload"),
                    "expected_status": case["expected_status"],
                    "actual_status": response.status_code,
                    "duration_ms": round(
                        response.elapsed.total_seconds() * 1000,
                        2,
                    ),
                    "response_body": response_body,
                    "checks": checks,
                    "passed": passed,
                    "error": None,
                }

            except (httpx.HTTPError, ValueError, KeyError) as exc:
                result = {
                    "name": case.get("name", "Unnamed test"),
                    "method": case.get("method"),
                    "path": case.get("path"),
                    "payload": case.get("payload"),
                    "expected_status": case.get("expected_status"),
                    "actual_status": None,
                    "duration_ms": None,
                    "response_body": None,
                    "checks": [],
                    "passed": False,
                    "error": str(exc),
                }

            result["executed_at"] = started_at.isoformat()
            results.append(result)

            print(f"\nTest: {result['name']}")

            for check in result["checks"]:
                label = "PASS" if check["passed"] else "FAIL"
                print(f"  {label}: {check['check']}")

            print(
                f"  Overall: {'PASS' if result['passed'] else 'FAIL'}"
            )

            if result["error"]:
                print(f"  Error: {result['error']}")

    passed_count = sum(
        result["passed"] for result in results
    )
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

    print("\n" + "=" * 60)
    print(f"Total:     {len(results)}")
    print(f"Passed:    {passed_count}")
    print(f"Failed:    {failed_count}")
    print(f"Pass rate: {report['pass_rate_percent']}%")
    print(f"Report:    {REPORT_FILE}")

    return report


if __name__ == "__main__":
    run_tests()
