
import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000"


def test_health_check():
    response = httpx.get(f"{BASE_URL}/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_list_products():
    response = httpx.get(f"{BASE_URL}/products")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_existing_product():
    response = httpx.get(f"{BASE_URL}/products/1")

    assert response.status_code == 200
    assert response.json()["name"] == "Keyboard"


def test_get_missing_product():
    response = httpx.get(f"{BASE_URL}/products/999999")

    assert response.status_code == 404


def test_create_valid_product():
    payload = {
        "name": "Test Mouse",
        "price": 799,
        "stock": 10,
    }

    response = httpx.post(
        f"{BASE_URL}/products",
        json=payload,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Test Mouse"
    assert body["price"] == 799
    assert body["stock"] == 10
    assert "id" in body


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "A", "price": 100, "stock": 5},
        {"name": "Mouse", "price": 0, "stock": 5},
        {"name": "Mouse", "price": -10, "stock": 5},
        {"name": "Mouse", "price": 100, "stock": -1},
        {"name": "Mouse", "price": 100},
    ],
)
def test_create_invalid_product(payload):
    response = httpx.post(
        f"{BASE_URL}/products",
        json=payload,
    )

    assert response.status_code == 422
