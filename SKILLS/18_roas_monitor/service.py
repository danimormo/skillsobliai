import logging
import time
from datetime import datetime, timezone

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.roas_monitor.api_client import MetaInsightsClient
from SKILLS.roas_monitor.schemas import (
    CampaignROASResult,
    ROASMonitorInput,
    ROASMonitorOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "roas-monitor"


class ROASMonitorSkill(BaseSkill[ROASMonitorInput, ROASMonitorOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Reads ROAS from Meta Graph API for all active campaigns"
    consumes_credits = True
    credit_cost = 1

    def __init__(self) -> None:
        self._insights_client = MetaInsightsClient()

    def validate(self, input: ROASMonitorInput) -> bool:
        # No strict validation required; user_id may come from context.
        return True

    async def run(
        self, input: ROASMonitorInput, ctx: SkillContext
    ) -> SkillResult[ROASMonitorOutput]:
        start = time.perf_counter()
        self.validate(input)

        user_id = input.user_id or ctx.user_id
        supabase = get_supabase()

        # ── 1. Get active campaigns from DB ─────────────────────────
        campaigns_resp = (
            supabase.table("campaigns")
            .select("id, meta_campaign_id, name, ad_account_id")
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
        )
        campaigns = campaigns_resp.data or []

        if not campaigns:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=ROASMonitorOutput(
                    campaigns_checked=0,
                    snapshots_saved=0,
                    actions_triggered=0,
                    results=[],
                    monitored_at=datetime.now(timezone.utc).isoformat(),
                ),
                cached=False,
                execution_ms=elapsed_ms,
            )

        # ── 2. Get Meta token from user_integrations ────────────────
        integration_resp = (
            supabase.table("user_integrations")
            .select("access_token")
            .eq("user_id", user_id)
            .eq("provider", "meta")
            .single()
            .execute()
        )
        meta_token = integration_resp.data.get("access_token") if integration_resp.data else None
        if not meta_token:
            raise InvalidParamsError(
                message="No Meta integration found for user",
                skill=SKILL_NAME,
                code="MISSING_INTEGRATION",
            )

        # ── 3. Fetch insights for each campaign ────────────────────
        results: list[CampaignROASResult] = []
        snapshots_saved = 0

        for campaign in campaigns:
            campaign_db_id = campaign["id"]
            meta_campaign_id = campaign["meta_campaign_id"]
            ad_account_id = campaign["ad_account_id"]
            campaign_name = campaign.get("name", "")

            try:
                insights = await self._insights_client.get_campaign_insights(
                    token=meta_token,
                    ad_account_id=ad_account_id,
                    campaign_id=meta_campaign_id,
                )
            except Exception:
                logger.exception(
                    "Failed to fetch insights for campaign %s", meta_campaign_id
                )
                continue

            roas = insights["roas"]
            spend = insights["spend"]
            revenue = insights["revenue"]
            impressions = insights["impressions"]
            clicks = insights["clicks"]
            conversions = insights["conversions"]

            # ── 4. Save snapshot to roas_snapshots ──────────────────
            snapshot_row = {
                "user_id": user_id,
                "campaign_id": campaign_db_id,
                "meta_campaign_id": meta_campaign_id,
                "roas": roas,
                "spend_usd": spend,
                "revenue_usd": revenue,
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "action_taken": None,
                "snapshot_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                supabase.table("roas_snapshots").insert(snapshot_row).execute()
                snapshots_saved += 1
            except Exception:
                logger.exception("Failed to save ROAS snapshot for %s", campaign_db_id)

            results.append(
                CampaignROASResult(
                    campaign_db_id=campaign_db_id,
                    meta_campaign_id=meta_campaign_id,
                    campaign_name=campaign_name,
                    roas=roas,
                    spend_usd=spend,
                    revenue_usd=revenue,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                )
            )

        # ── 5. Return results ───────────────────────────────────────
        output = ROASMonitorOutput(
            campaigns_checked=len(campaigns),
            snapshots_saved=snapshots_saved,
            actions_triggered=0,
            results=results,
            monitored_at=datetime.now(timezone.utc).isoformat(),
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
