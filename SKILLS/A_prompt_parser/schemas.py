from pydantic import BaseModel


class PromptParserInput(BaseModel):
    prompt: str
    override_countries: list[str] | None = None


class ParsedParams(BaseModel):
    sources: list[str] = ["tiktok_shop"]
    countries: list[str]
    n_results: int
    search_signal: str
    categories: list[str]
    gender: str | None = None
    price_max: float | None = None
    price_min: float | None = None
    keywords_by_country: dict[str, list[str]]


class PromptParserOutput(BaseModel):
    parsed: ParsedParams
    raw_response: str
    used_defaults: bool
