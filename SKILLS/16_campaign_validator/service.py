import asyncio
import logging
import time

from core.errors import IntegrationNotConnectedError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.16_campaign_validator.api_client import MetaValidator
from SKILLS.16_campaign_validator.schemas import (
    CampaignValidatorInput,
    CampaignValidatorOutput,
    ValidationCheck,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "campaign-validator"


class CampaignValidatorSkill(BaseSkill[CampaignValidatorInput, CampaignValidatorOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Validate campaign parameters before launch"
    consumes_credits = False
    credit_cost = 0

    def __init__(self) -> None:
        self.meta = MetaValidator()

    def validate(self, input: CampaignValidatorInput) -> bool:
        return True

    async def run(
        self, input: CampaignValidatorInput, ctx: SkillContext
    ) -> SkillResult[CampaignValidatorOutput]:
        start = time.perf_counter()

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

        # ── 2. Run checks in parallel ──────────────────────────────
        checks: list[ValidationCheck] = []
        warnings: list[str] = []

        # Remote checks via Meta API (run concurrently)
        ad_account_task = asyncio.create_task(
            self._check_ad_account(meta_token, input.ad_account_id)
        )
        pixel_task = asyncio.create_task(
            self._check_pixel(meta_token, input.pixel_id)
        )
        funding_task = asyncio.create_task(
            self._check_funding(meta_token, input.ad_account_id)
        )

        ad_account_check, pixel_check, funding_check = await asyncio.gather(
            ad_account_task, pixel_task, funding_task, return_exceptions=True
        )

        # Process ad_account result
        if isinstance(ad_account_check, Exception):
            checks.append(ValidationCheck(
                name="ad_account_active",
                passed=False,
                message=f"Failed to verify ad account: {ad_account_check}",
                blocking=True,
            ))
        else:
            checks.append(ad_account_check)

        # Process pixel result
        if isinstance(pixel_check, Exception):
            checks.append(ValidationCheck(
                name="pixel_active",
                passed=False,
                message=f"Failed to verify pixel: {pixel_check}",
                blocking=True,
            ))
        else:
            checks.append(pixel_check)

        # Process funding result
        if isinstance(funding_check, Exception):
            checks.append(ValidationCheck(
                name="funding_source",
                passed=False,
                message=f"Failed to verify funding: {funding_check}",
                blocking=True,
            ))
        else:
            checks.append(funding_check)

        # ── Local checks ────────────────────────────────────────────
        # Budget check
        budget_ok = input.daily_budget_usd >= 5.0
        checks.append(ValidationCheck(
            name="budget_check",
            passed=budget_ok,
            message="Daily budget is sufficient" if budget_ok else "Daily budget must be at least $5.00",
            blocking=True,
        ))

        # Creative check
        creative_ok = len(input.creative_image_urls) >= 1
        checks.append(ValidationCheck(
            name="creative_check",
            passed=creative_ok,
            message="At least one creative image provided" if creative_ok else "At least one creative image URL is required",
            blocking=True,
        ))

        # Copy check
        copy_ok = bool(input.ad_copy.strip()) and bool(input.ad_headline.strip())
        checks.append(ValidationCheck(
            name="copy_check",
            passed=copy_ok,
            message="Ad copy and headline are set" if copy_ok else "Ad copy and headline must not be empty",
            blocking=True,
        ))

        # URL check
        url_ok = input.destination_url.startswith("https")
        checks.append(ValidationCheck(
            name="url_check",
            passed=url_ok,
            message="Destination URL uses HTTPS" if url_ok else "Destination URL must start with https",
            blocking=True,
        ))

        # Margin / break-even check
        break_even_roas = 0.0
        if input.product_price > 0:
            break_even_roas = round(
                (input.product_cost + input.shipping_cost) / input.product_price, 2
            )
        margin_ok = True  # non-blocking
        if break_even_roas > 0:
            margin_msg = f"Break-even ROAS: {break_even_roas}"
            # This is a warning, not blocking
            if break_even_roas >= 1.0:
                warnings.append(
                    f"Break-even ROAS ({break_even_roas}) is >= 1.0 which leaves very thin margins"
                )
        else:
            margin_msg = "Could not calculate break-even ROAS (product_price is 0)"
            margin_ok = False

        checks.append(ValidationCheck(
            name="margin_check",
            passed=margin_ok,
            message=margin_msg,
            blocking=False,
        ))

        # ── 3. Determine can_launch ─────────────────────────────────
        can_launch = all(c.passed for c in checks if c.blocking)

        failed = [c.name for c in checks if not c.passed]
        if can_launch:
            summary = "All blocking checks passed. Campaign is ready to launch."
        else:
            summary = f"Campaign cannot launch. Failed checks: {', '.join(failed)}."

        output = CampaignValidatorOutput(
            can_launch=can_launch,
            checks=checks,
            warnings=warnings,
            break_even_roas=break_even_roas,
            summary=summary,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )

    # ── Private helpers for remote checks ───────────────────────────

    async def _check_ad_account(self, token: str, ad_account_id: str) -> ValidationCheck:
        data = await self.meta.check_ad_account(token, ad_account_id)
        # account_status: 1 = ACTIVE, 2 = DISABLED, 3 = UNSETTLED, etc.
        status = data.get("account_status", 0)
        is_active = status == 1
        return ValidationCheck(
            name="ad_account_active",
            passed=is_active,
            message="Ad account is active" if is_active else f"Ad account status is {status} (expected 1/ACTIVE)",
            blocking=True,
        )

    async def _check_pixel(self, token: str, pixel_id: str) -> ValidationCheck:
        data = await self.meta.check_pixel(token, pixel_id)
        is_available = not data.get("is_unavailable", True)
        has_fired = bool(data.get("last_fired_time"))
        passed = is_available and has_fired
        if passed:
            msg = "Pixel is active and has fired"
        elif not is_available:
            msg = "Pixel is unavailable"
        else:
            msg = "Pixel has never fired events"
        return ValidationCheck(
            name="pixel_active",
            passed=passed,
            message=msg,
            blocking=True,
        )

    async def _check_funding(self, token: str, ad_account_id: str) -> ValidationCheck:
        data = await self.meta.check_funding(token, ad_account_id)
        has_funding = bool(data.get("id") or data.get("data"))
        return ValidationCheck(
            name="funding_source",
            passed=has_funding,
            message="Payment method is configured" if has_funding else "No payment method found on ad account",
            blocking=True,
        )
