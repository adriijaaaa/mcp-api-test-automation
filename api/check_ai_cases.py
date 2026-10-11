import json
from pathlib import Path

import httpx

API_URL = "http://127.0.0.1:8000"

cases_file = Path("test_data/ai_generated_cases.json")
cases = json.loads(cases_file.read_text(encoding="utf-8"))

print("\nAI-GENERATED TEST RESULTS")
print("=" * 60)

for case in cases:
    response = httpx.request(
        method=case["method"],
        url=API_URL + case["path"],
        json=case["payload"],
    )

    expected = case["expected_status"]
    actual = response.status_code

    result = "PASS" if actual == expected else "FAIL"

    print(f"\nTest: {case['name']}")
    print(f"Expected status: {expected}")
    print(f"Actual status:   {actual}")
    print(f"Result:          {result}")

print("\n" + "=" * 60)