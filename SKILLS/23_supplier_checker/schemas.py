from pydantic import BaseModel, Field


class SupplierCheckerInput(BaseModel):
    product_title: str
    sale_price: float
    supplier_cost: float | None = None
    shipping_cost: float = 4.0
    daily_budget_usd: float = 30.0
    daily_orders_estimate: float = 2.0
    target_countries: list[str] = ["IT"]


class SupplierCheckerOutput(BaseModel):
    product_title: str
    sale_price: float
    best_supplier_cost: float
    best_supplier_source: str
    net_margin_pct: float
    net_margin_usd: float
    is_viable: bool  # net_margin_pct > 0.15
    flag: str  # "green" | "yellow" | "red"
    breakdown: dict
    recommendation: str
    alternative_suppliers: list[dict]
