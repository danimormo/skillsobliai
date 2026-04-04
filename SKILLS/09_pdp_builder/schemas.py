from pydantic import BaseModel


class PDPBuilderInput(BaseModel):
    product_title: str
    product_description: str | None = None
    price: float
    original_price: float | None = None
    category: str | None = None
    copy_angle: str = "benefit"
    target_audience: str | None = None
    language: str = "en"


class PDPSections(BaseModel):
    headlines: list[str]
    subheadline: str
    benefit_bullets: list[str]
    description_long: str
    faq: list[dict]
    urgency_text: str
    cta_text: str


class PDPBuilderOutput(BaseModel):
    pdp_id: str
    sections: PDPSections
    copy_angle: str
    language: str
    word_count: int
