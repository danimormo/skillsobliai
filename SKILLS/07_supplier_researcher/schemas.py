from pydantic import BaseModel


class SupplierResearchInput(BaseModel):
    product_name: str
    target_price_usd: float | None = None
    ship_to_country: str = "US"
    limit_per_source: int = 10
    product_image_url: str | None = None


class SupplierProduct(BaseModel):
    source: str  # "aliexpress"
    product_id: str
    title: str
    cost_usd: float
    shipping_cost_usd: float
    shipping_days_min: int
    shipping_days_max: int
    moq: int
    supplier_rating: float | None = None
    image_urls: list[str] = []
    product_url: str
    margin_at_3x: float | None = None
    in_stock: bool


class SupplierResearchOutput(BaseModel):
    total_found: int
    products: list[SupplierProduct]
    best_price: SupplierProduct | None = None
    best_margin: SupplierProduct | None = None
    fastest_shipping: SupplierProduct | None = None
    supplier_links_static: dict = {}
    vision_supplier_links: dict = {}
    price_estimate: dict | None = None
