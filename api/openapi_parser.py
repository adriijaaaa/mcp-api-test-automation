
import json
from pathlib import Path
from urllib.request import urlopen

OPENAPI_URL = "http://127.0.0.1:8000/openapi.json"


def load_openapi():
    """Fetch the OpenAPI specification from our running API."""
    with urlopen(OPENAPI_URL, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def discover_endpoints(spec):
    """Extract every endpoint and its HTTP methods."""
    endpoints = []

    for path, path_details in spec.get("paths", {}).items():
        for method, details in path_details.items():
            if method.lower() not in {
                "get", "post", "put", "patch", "delete"
            }:
                continue

            endpoints.append({
                "path": path,
                "method": method.upper(),
                "summary": details.get("summary", ""),
                "operation_id": details.get("operationId", ""),
                "parameters": details.get("parameters", []),
                "request_body": details.get("requestBody"),
                "responses": list(details.get("responses", {}).keys()),
            })

    return endpoints


def main():
    spec = load_openapi()
    endpoints = discover_endpoints(spec)

    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "discovered_endpoints.json"
    output_file.write_text(
        json.dumps(endpoints, indent=2),
        encoding="utf-8",
    )

    print(f"API: {spec.get('info', {}).get('title', 'Unknown')}")
    print(f"Endpoints discovered: {len(endpoints)}")

    for endpoint in endpoints:
        print(
            f"{endpoint['method']:6} "
            f"{endpoint['path']:25} "
            f"{endpoint['summary']}"
        )

    print(f"\nSaved endpoint inventory to: {output_file}")


if __name__ == "__main__":
    main()
