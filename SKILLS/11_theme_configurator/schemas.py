from pydantic import BaseModel


class ThemeConfiguratorInput(BaseModel):
    shop_domain: str
    theme_preset: str = "shrine"
    primary_color: str = "#000000"
    secondary_color: str = "#ffffff"
    accent_color: str = "#ff6b35"
    enable_sticky_cart: bool = True
    custom_overrides: dict = {}


class ThemeConfiguratorOutput(BaseModel):
    shop_domain: str
    theme_id: str
    theme_name: str
    settings_modified: list[str]
    success: bool
