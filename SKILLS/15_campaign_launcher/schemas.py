from pydantic import BaseModel


class CampaignLauncherInput(BaseModel):
    shop_domain: str
    campaign_name: str
    daily_budget_usd: float
    target_countries: list[str] = ["IT"]
    target_age_min: int = 18
    target_age_max: int = 65
    pixel_id: str
    ad_account_id: str
    creative_image_urls: list[str]
    creative_video_url: str | None = None
    ad_copy: str
    ad_headline: str
    ad_cta: str = "SHOP_NOW"
    destination_url: str
    roas_target: float = 2.5
    roas_kill_threshold: float = 1.0
    spend_kill_limit_usd: float = 30.0


class CampaignLauncherOutput(BaseModel):
    campaign_db_id: str
    meta_campaign_id: str
    meta_adset_id: str
    meta_ad_id: str
    campaign_name: str
    status: str
    daily_budget_usd: float
    manus_task_id: str
    launched_at: str
