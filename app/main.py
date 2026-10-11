
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Online Store API",
    description="Demo API for automated contract testing",
    version="1.0.0",
)


class Product(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)


products = {
    1: {"id": 1, "name": "Keyboard", "price": 1499.0, "stock": 20}
}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/products")
def list_products():
    return list(products.values())


@app.get("/products/{product_id}")
def get_product(product_id: int):
    product = products.get(product_id)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


@app.post("/products", status_code=201)
def create_product(product: Product):
    new_id = max(products.keys(), default=0) + 1
    new_product = {"id": new_id, **product.model_dump()}
    products[new_id] = new_product
    return new_product
