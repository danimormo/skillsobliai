from pydantic import BaseModel


class ScaleKillInput(BaseModel):
    campaign_db_id: str
    current_roas: float
    current_spend_usd: float
    roas_history: list[dict]
    custom_rules: dict = {}


class ScaleKillOutput(BaseModel):
    campaign_db_id: str
    action: str  # "scale" | "kill" | "duplicate" | "hold"
    reason: str
    previous_budget_usd: float | None = None
    new_budget_usd: float | None = None
    manus_task_id: str | None = None
    executed: bool
