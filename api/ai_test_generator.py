
import json
from pathlib import Path

import requests

from api.test_generator import load_spec


# Ollama configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"

# Output file for AI-assisted test cases
OUTPUT_FILE = Path("test_data/ai_generated_cases.json")


def validate_case(case):
    """
    Verify that a test case targets POST /products,
    expects HTTP 422, and contains a genuinely invalid payload.
    """

    if not isinstance(case, dict):
        return False, "Test case must be a JSON object."

    if (
        case.get("method") != "POST"
        or case.get("path") != "/products"
        or case.get("expected_status") != 422
    ):
        return False, "Invalid method, path, or expected status."

    payload = case.get("payload")

    if not isinstance(payload, dict):
        return False, "Payload must be a JSON object."

    violations = []

    # name must be a string with 2–100 characters.
    name = payload.get("name")

    if not isinstance(name, str) or not 2 <= len(name) <= 100:
        violations.append("name")

    # price must be a number greater than zero.
    price = payload.get("price")

    if (
        isinstance(price, bool)
        or not isinstance(price, (int, float))
        or price <= 0
    ):
        violations.append("price")

    # stock must be an integer greater than or equal to zero.
    stock = payload.get("stock")

    if (
        isinstance(stock, bool)
        or not isinstance(stock, int)
        or stock < 0
    ):
        violations.append("stock")

    if not violations:
        return False, "Payload is valid, not a negative test."

    return True, None


def generate_ai_cases():
    """
    Ask Ollama to suggest validation rules, then use deterministic
    Python logic to build and validate negative test cases.
    """

    # Load the API specification.
    spec = load_spec()

    product_schema = (
        spec.get("components", {})
        .get("schemas", {})
        .get("Product", {})
    )

    # Ask the local AI to identify the validation rules to test.
    prompt = f"""
You are an API testing engineer.

Analyze this OpenAPI Product schema:
{json.dumps(product_schema)}

Select exactly these three test categories:
1. name_too_short
2. negative_price
3. negative_stock

Return JSON only, in this format:
{{
    "rules": [
        "name_too_short",
        "negative_price",
        "negative_stock"
    ]
}}

Do not return test payloads.
"""

    print("Asking the local AI to identify test categories...")

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        timeout=180,
    )

    response.raise_for_status()

    ai_result = json.loads(response.json()["response"])

    allowed_rules = {
        "name_too_short",
        "negative_price",
        "negative_stock",
    }

    suggested_rules = ai_result.get("rules", [])

    if not isinstance(suggested_rules, list):
        suggested_rules = []

    # Accept only recognized rules, without duplicates.
    selected_rules = []

    for rule in suggested_rules:
        if rule in allowed_rules and rule not in selected_rules:
            selected_rules.append(rule)

    # Safe fallback if the model omits a rule or returns unexpected output.
    if set(selected_rules) != allowed_rules:
        print("AI response was incomplete; using the predefined test categories.")
        selected_rules = [
            "name_too_short",
            "negative_price",
            "negative_stock",
        ]

    # Python creates the actual invalid values.
    payload_by_rule = {
        "name_too_short": {
            "name": "A",
            "price": 10,
            "stock": 5,
        },
        "negative_price": {
            "name": "Example",
            "price": -1,
            "stock": 5,
        },
        "negative_stock": {
            "name": "Example",
            "price": 10,
            "stock": -1,
        },
    }

    name_by_rule = {
        "name_too_short": "Name Below Minimum Length",
        "negative_price": "Negative Product Price",
        "negative_stock": "Negative Product Stock",
    }

    cases = []

    for rule in selected_rules:
        case = {
            "name": name_by_rule[rule],
            "method": "POST",
            "path": "/products",
            "payload": payload_by_rule[rule],
            "expected_status": 422,
        }

        # Never save a case unless local validation confirms it is invalid.
        is_valid, error = validate_case(case)

        if not is_valid:
            raise ValueError(
                f"Generated test case failed validation: {error}"
            )

        cases.append(case)

    # Ensure the generated test cases are distinct.
    names = [case["name"] for case in cases]
    payloads = [
        json.dumps(case["payload"], sort_keys=True)
        for case in cases
    ]

    if len(cases) != 3:
        raise ValueError("Expected exactly 3 negative test cases.")

    if len(set(names)) != 3 or len(set(payloads)) != 3:
        raise ValueError("Generated test cases are not distinct.")

    # Save only after all validation checks succeed.
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_FILE.write_text(
        json.dumps(cases, indent=2),
        encoding="utf-8",
    )

    print(f"\nGenerated {len(cases)} validated negative test cases.")

    for case in cases:
        print(f"\n- {case['name']}")
        print(f"  Method: {case['method']}")
        print(f"  Path: {case['path']}")
        print(f"  Payload: {json.dumps(case['payload'])}")
        print(f"  Expected status: {case['expected_status']}")

    print(f"\nSaved to: {OUTPUT_FILE}")

    return cases


if __name__ == "__main__":
    generate_ai_cases()
