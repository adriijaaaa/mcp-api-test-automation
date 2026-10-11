
import json
from pathlib import Path
from urllib.request import urlopen

OPENAPI_URL = "http://127.0.0.1:8000/openapi.json"


def load_spec():
    with urlopen(OPENAPI_URL, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def resolve_schema(spec, schema):
    """Resolve simple local OpenAPI schema references."""
    if "$ref" in schema:
        ref = schema["$ref"]

        if not ref.startswith("#/"):
            raise ValueError(f"Unsupported schema reference: {ref}")

        target = spec
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]

        return resolve_schema(spec, target)

    return schema


def valid_value(spec, schema):
    """Generate a basic valid value for a JSON schema."""
    schema = resolve_schema(spec, schema)
    kind = schema.get("type")

    if kind == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", list(properties.keys()))

        return {
            name: valid_value(spec, properties[name])
            for name in required
            if name in properties
        }

    if kind == "array":
        return [valid_value(spec, schema.get("items", {}))]

    if "enum" in schema:
        return schema["enum"][0]

    if kind == "string":
        minimum = schema.get("minLength", 1)
        maximum = schema.get("maxLength", max(minimum, 12))
        length = max(1, minimum)
        length = min(length, maximum)
        value = "x" * length

        if schema.get("format") == "email":
            value = "user@example.com"

        return value

    if kind == "integer":
        return max(0, schema.get("minimum", 1))

    if kind == "number":
        return max(1, schema.get("minimum", 1))

    if kind == "boolean":
        return True

    return None


def find_request_schema(spec, operation):
    """Find the JSON request schema for an operation."""
    request_body = operation.get("requestBody", {})
    request_body = resolve_schema(spec, request_body)

    content = request_body.get("content", {})
    json_content = content.get("application/json", {})
    schema = json_content.get("schema", {})

    if schema:
        return resolve_schema(spec, schema)

    return None


def generate_cases(spec):
    cases = []

    for path, path_details in spec.get("paths", {}).items():
        for method, operation in path_details.items():
            method = method.upper()

            if method not in {"POST", "PUT", "PATCH"}:
                continue

            schema = find_request_schema(spec, operation)

            if not schema:
                continue

            valid_payload = valid_value(spec, schema)

            cases.append({
                "name": f"{method} {path} - valid payload",
                "method": method,
                "path": path,
                "payload": valid_payload,
                "expected_status": 201 if method == "POST" else 200,
            })

            resolved = resolve_schema(spec, schema)
            properties = resolved.get("properties", {})
            required = resolved.get("required", [])

            # Missing required field
            if required:
                missing_field = required[0]
                missing_payload = valid_payload.copy()
                missing_payload.pop(missing_field, None)

                cases.append({
                    "name": f"{method} {path} - missing {missing_field}",
                    "method": method,
                    "path": path,
                    "payload": missing_payload,
                    "expected_status": 422,
                })

            # Invalid values derived from field constraints
            for field, rules in properties.items():
                rules = resolve_schema(spec, rules)
                invalid_payload = valid_payload.copy()
                kind = rules.get("type")

                if kind == "string" and rules.get("minLength", 0) > 0:
                    invalid_payload[field] = ""
                elif kind in {"integer", "number"}:
                    if rules.get("exclusiveMinimum") is not None:
                        invalid_payload[field] = rules["exclusiveMinimum"]
                    elif rules.get("minimum", 0) >= 0:
                        invalid_payload[field] = -1
                    else:
                        continue
                else:
                    continue

                cases.append({
                    "name": f"{method} {path} - invalid {field}",
                    "method": method,
                    "path": path,
                    "payload": invalid_payload,
                    "expected_status": 422,
                })

    return cases


def main():
    spec = load_spec()
    cases = generate_cases(spec)

    output = Path("test_data")
    output.mkdir(exist_ok=True)

    destination = output / "generated_cases.json"
    destination.write_text(
        json.dumps(cases, indent=2),
        encoding="utf-8",
    )

    print(f"Generated {len(cases)} test cases")

    for case in cases:
        print(f"- {case['name']}")

    print(f"\nSaved to {destination}")


if __name__ == "__main__":
    main()
