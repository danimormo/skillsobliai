from pydantic import BaseModel


class CampaignValidatorInput(BaseModel):
    ad_account_id: str
    pixel_id: str
    campaign_name: str
    daily_budget_usd: float
    target_countries: list[str]
    creative_image_urls: list[str]
    ad_copy: str
    ad_headline: str
    destination_url: str
    product_price: float
    product_cost: float
    shipping_cost: float = 4.0


class ValidationCheck(BaseModel):
    name: str
    passed: bool
    message: str
    blocking: bool


class CampaignValidatorOutput(BaseModel):
    can_launch: bool
    checks: list[ValidationCheck]
    warnings: list[str]
    break_even_roas: float
    summary: str
