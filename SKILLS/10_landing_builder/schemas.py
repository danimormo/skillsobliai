from pydantic import BaseModel


class LandingBuilderInput(BaseModel):
    product_title: str
    product_description: str
    price: float
    original_price: float | None = None
    target_audience: str
    main_benefit: str
    cta_destination_url: str
    language: str = "en"


class LandingSection(BaseModel):
    type: str
    headline: str
    body: str
    cta_text: str | None = None


class LandingBuilderOutput(BaseModel):
    landing_id: str
    sections: list[LandingSection]
    total_word_count: int
    language: str
