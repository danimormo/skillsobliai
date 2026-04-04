from pydantic import BaseModel, Field


class ProductVariant(BaseModel):
    title: str
    sku: str | None = None
    price: float | None = None
    inventory_quantity: int = 100


class ProductImportInput(BaseModel):
    shop_domain: str
    title: str
    description_html: str
    vendor: str | None = None
    product_type: str | None = None
    tags: list[str] = Field(default=[])
    image_urls: list[str]
    cost_usd: float
    markup_multiplier: float = 3.0
    variants: list[ProductVariant] = Field(default=[])
    supplier_source: str | None = None
    supplier_product_id: str | None = None


class ProductImportOutput(BaseModel):
    job_id: str
    shopify_product_id: str
    shopify_product_url: str
    shopify_storefront_url: str
    title: str
    price: float
    variants_count: int
    images_uploaded: int
    status: str  # "completed" | "partial"
