
import contextlib
import io
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from api.consolidated_report import build_consolidated_report

from api.openapi_parser import load_openapi, discover_endpoints
from api.test_generator import load_spec, generate_cases
from api.test_runner import run_tests
from api.ai_test_generator import generate_ai_cases
from api.run_ai_tests import run_ai_tests
from api.boundary_test_runner import run_boundary_tests

mcp = FastMCP("API Test Automation Framework")


@mcp.tool()
def discover_api_endpoints() -> str:
    """Discover API endpoints from the live OpenAPI specification."""

    spec = load_openapi()
    endpoints = discover_endpoints(spec)

    return json.dumps(
        {
            "api": spec.get("info", {}).get("title", "Unknown"),
            "endpoint_count": len(endpoints),
            "endpoints": endpoints,
        },
        indent=2,
    )


@mcp.tool()
def generate_api_test_cases() -> str:
    """Generate rule-based API test cases from the OpenAPI specification."""

    spec = load_spec()
    cases = generate_cases(spec)

    output_file = Path("test_data/generated_cases.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(cases, indent=2),
        encoding="utf-8",
    )

    return json.dumps(
        {
            "generated_count": len(cases),
            "output_file": str(output_file),
            "cases": cases,
        },
        indent=2,
    )


@mcp.tool()
def execute_generated_api_tests() -> str:
    """Execute the rule-based test cases and return their report."""

    report = run_tests()
    return json.dumps(report, indent=2)


@mcp.tool()
def generate_ai_test_cases() -> str:
    """Generate and validate negative API test cases using local Ollama AI."""

    # Suppress print output so it does not interfere with MCP stdio.
    with contextlib.redirect_stdout(io.StringIO()):
        cases = generate_ai_cases()

    return json.dumps(
        {
            "generated_count": len(cases),
            "output_file": "test_data/ai_generated_cases.json",
            "cases": cases,
        },
        indent=2,
    )


@mcp.tool()
def execute_ai_generated_api_tests() -> str:
    """Execute AI-generated test cases against the live API."""

    # The runner prints progress to stdout; keep MCP communication clean.
    with contextlib.redirect_stdout(io.StringIO()):
        run_ai_tests()

    report_file = Path("reports/ai_test_run_report.json")

    if not report_file.exists():
        raise RuntimeError("AI test report was not created.")

    report = json.loads(report_file.read_text(encoding="utf-8"))
    return json.dumps(report, indent=2)

@mcp.tool()
def execute_boundary_api_tests() -> str:
    """Execute boundary-value API tests and return the JSON report."""

    with contextlib.redirect_stdout(io.StringIO()):
        run_boundary_tests()

    report_file = Path("reports/boundary_test_report.json")

    if not report_file.exists():
        raise RuntimeError("Boundary test report was not created.")

    report = json.loads(
        report_file.read_text(encoding="utf-8")
    )

    return json.dumps(report, indent=2)


@mcp.tool()
def generate_consolidated_report() -> str:
    """Combine saved rule-based, AI-assisted, and boundary test reports."""

    with contextlib.redirect_stdout(io.StringIO()):
        build_consolidated_report()

    report_file = Path("reports/consolidated_report.json")

    if not report_file.exists():
        raise RuntimeError("Consolidated report was not created.")

    report = json.loads(
        report_file.read_text(encoding="utf-8")
    )

    return json.dumps(report, indent=2)

if __name__ == "__main__":
    mcp.run(transport="stdio")
