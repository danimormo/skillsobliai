from pydantic import BaseModel


class ROASMonitorInput(BaseModel):
    user_id: str | None = None
    force_refresh: bool = False


class CampaignROASResult(BaseModel):
    campaign_db_id: str
    meta_campaign_id: str
    campaign_name: str
    roas: float
    spend_usd: float
    revenue_usd: float
    impressions: int
    clicks: int
    conversions: int
    action_triggered: str | None = None


class ROASMonitorOutput(BaseModel):
    campaigns_checked: int
    snapshots_saved: int
    actions_triggered: int
    results: list[CampaignROASResult]
    monitored_at: str
