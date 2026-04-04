import logging
import time
import uuid
from datetime import datetime, timezone

from core.errors import IntegrationNotConnectedError, InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.campaign_launcher.api_client import ManusClient, MetaVerifier
from SKILLS.campaign_launcher.schemas import (
    CampaignLauncherInput,
    CampaignLauncherOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "campaign-launcher"


class CampaignLauncherSkill(BaseSkill[CampaignLauncherInput, CampaignLauncherOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Launch Meta campaigns via Manus AI"
    consumes_credits = True
    credit_cost = 5

    def __init__(self) -> None:
        self.manus = ManusClient()
        self.verifier = MetaVerifier()

    def validate(self, input: CampaignLauncherInput) -> bool:
        if not input.creative_image_urls:
            raise InvalidParamsError(
                message="At least one creative image URL is required",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        if input.daily_budget_usd < 5.0:
            raise InvalidParamsError(
                message="Daily budget must be at least $5.00",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: CampaignLauncherInput, ctx: SkillContext
    ) -> SkillResult[CampaignLauncherOutput]:
        start = time.perf_counter()
        self.validate(input)

        # ── 1. Get Meta token ───────────────────────────────────────
        supabase = get_supabase()
        row = (
            supabase.table("user_integrations")
            .select("access_token")
            .eq("user_id", ctx.user_id)
            .eq("provider", "meta")
            .single()
            .execute()
        )
        if not row.data or not row.data.get("access_token"):
            raise IntegrationNotConnectedError(
                message="Meta integration not connected. Please connect your Meta account.",
                skill=SKILL_NAME,
                code="INTEGRATION_NOT_CONNECTED",
            )
        meta_token: str = row.data["access_token"]

        # ── 2. Build Manus task config ──────────────────────────────
        task_config = {
            "type": "campaign_launch",
            "shop_domain": input.shop_domain,
            "campaign_name": input.campaign_name,
            "daily_budget_usd": input.daily_budget_usd,
            "target_countries": input.target_countries,
            "target_age_min": input.target_age_min,
            "target_age_max": input.target_age_max,
            "pixel_id": input.pixel_id,
            "ad_account_id": input.ad_account_id,
            "creative_image_urls": input.creative_image_urls,
            "creative_video_url": input.creative_video_url,
            "ad_copy": input.ad_copy,
            "ad_headline": input.ad_headline,
            "ad_cta": input.ad_cta,
            "destination_url": input.destination_url,
            "roas_target": input.roas_target,
        }

        # ── 3. Submit to Manus AI ──────────────────────────────────
        task_id = await self.manus.submit_task(meta_token, task_config)

        # ── 4. Poll until complete ──────────────────────────────────
        task_result = await self.manus.poll_task(meta_token, task_id)

        # ── 5. Extract IDs from Manus response ─────────────────────
        meta_campaign_id = task_result["campaign_id"]
        meta_adset_id = task_result["adset_id"]
        meta_ad_id = task_result["ad_id"]

        # ── 6. Verify campaign via Meta Graph API ───────────────────
        await self.verifier.verify_campaign(meta_token, meta_campaign_id)

        # ── 7. Save to campaigns table ──────────────────────────────
        campaign_db_id = str(uuid.uuid4())
        launched_at = datetime.now(timezone.utc).isoformat()

        supabase.table("campaigns").insert(
            {
                "id": campaign_db_id,
                "user_id": ctx.user_id,
                "meta_campaign_id": meta_campaign_id,
                "meta_adset_id": meta_adset_id,
                "meta_ad_id": meta_ad_id,
                "name": input.campaign_name,
                "status": "ACTIVE",
                "daily_budget_usd": input.daily_budget_usd,
                "roas_target": input.roas_target,
                "roas_kill_threshold": input.roas_kill_threshold,
                "spend_kill_limit_usd": input.spend_kill_limit_usd,
                "params": input.model_dump(),
            }
        ).execute()

        # ── 8. Return output ────────────────────────────────────────
        output = CampaignLauncherOutput(
            campaign_db_id=campaign_db_id,
            meta_campaign_id=meta_campaign_id,
            meta_adset_id=meta_adset_id,
            meta_ad_id=meta_ad_id,
            campaign_name=input.campaign_name,
            status="ACTIVE",
            daily_budget_usd=input.daily_budget_usd,
            manus_task_id=task_id,
            launched_at=launched_at,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
