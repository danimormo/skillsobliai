import logging
import time

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.scale_kill_engine.api_client import ManusActionClient
from SKILLS.scale_kill_engine.schemas import ScaleKillInput, ScaleKillOutput

logger = logging.getLogger(__name__)

SKILL_NAME = "scale-kill-engine"

DEFAULT_RULES = {
    "scale_threshold": 2.5,
    "scale_increase_pct": 20,
    "scale_consecutive_days": 2,
    "kill_threshold": 1.0,
    "kill_min_spend_usd": 30.0,
    "duplicate_threshold": 4.0,
    "duplicate_consecutive_days": 5,
}


def _consecutive_days_above(roas_history: list[dict], threshold: float) -> int:
    """Count consecutive most-recent days where ROAS exceeded *threshold*."""
    count = 0
    for entry in reversed(roas_history):
        if entry.get("roas", 0) > threshold:
            count += 1
        else:
            break
    return count


class ScaleKillEngineSkill(BaseSkill[ScaleKillInput, ScaleKillOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Applies ROAS rules: scale, kill, or duplicate campaigns via Manus AI"
    consumes_credits = True
    credit_cost = 1

    def __init__(self) -> None:
        self._manus_client = ManusActionClient()

    def validate(self, input: ScaleKillInput) -> bool:
        if not input.campaign_db_id:
            raise InvalidParamsError(
                message="campaign_db_id is required",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: ScaleKillInput, ctx: SkillContext
    ) -> SkillResult[ScaleKillOutput]:
        start = time.perf_counter()
        self.validate(input)

        # ── 1. Merge custom rules with defaults ────────────────────
        rules = {**DEFAULT_RULES, **input.custom_rules}

        action = "hold"
        reason = "ROAS within acceptable range; no action needed."
        previous_budget: float | None = None
        new_budget: float | None = None
        manus_task_id: str | None = None
        executed = False

        # ── 2. Check kill ───────────────────────────────────────────
        if (
            input.current_roas < rules["kill_threshold"]
            and input.current_spend_usd > rules["kill_min_spend_usd"]
        ):
            action = "kill"
            reason = (
                f"ROAS {input.current_roas:.2f} < kill threshold "
                f"{rules['kill_threshold']} with spend ${input.current_spend_usd:.2f} "
                f"> min ${rules['kill_min_spend_usd']:.2f}."
            )

        # ── 3. Check duplicate ──────────────────────────────────────
        elif input.current_roas > rules["duplicate_threshold"]:
            consec = _consecutive_days_above(
                input.roas_history, rules["duplicate_threshold"]
            )
            if consec >= rules["duplicate_consecutive_days"]:
                action = "duplicate"
                reason = (
                    f"ROAS {input.current_roas:.2f} > duplicate threshold "
                    f"{rules['duplicate_threshold']} for {consec} consecutive days."
                )

        # ── 4. Check scale ──────────────────────────────────────────
        if action == "hold" and input.current_roas > rules["scale_threshold"]:
            consec = _consecutive_days_above(
                input.roas_history, rules["scale_threshold"]
            )
            if consec >= rules["scale_consecutive_days"]:
                action = "scale"
                reason = (
                    f"ROAS {input.current_roas:.2f} > scale threshold "
                    f"{rules['scale_threshold']} for {consec} consecutive days."
                )

        # ── 5. Execute action via Manus if needed ───────────────────
        if action != "hold":
            supabase = get_supabase()

            # Get Meta token
            integration_resp = (
                supabase.table("user_integrations")
                .select("access_token")
                .eq("user_id", ctx.user_id)
                .eq("provider", "meta")
                .single()
                .execute()
            )
            meta_token = (
                integration_resp.data.get("access_token")
                if integration_resp.data
                else None
            )

            # Get current budget
            campaign_resp = (
                supabase.table("campaigns")
                .select("daily_budget_usd, meta_campaign_id")
                .eq("id", input.campaign_db_id)
                .single()
                .execute()
            )
            campaign_data = campaign_resp.data or {}
            meta_campaign_id = campaign_data.get("meta_campaign_id", "")
            previous_budget = campaign_data.get("daily_budget_usd")

            if meta_token and meta_campaign_id:
                try:
                    if action == "kill":
                        manus_task_id = await self._manus_client.kill_campaign(
                            meta_token=meta_token,
                            campaign_id=meta_campaign_id,
                        )
                        # Update campaign status in DB
                        supabase.table("campaigns").update(
                            {"status": "paused"}
                        ).eq("id", input.campaign_db_id).execute()

                    elif action == "duplicate":
                        manus_task_id = await self._manus_client.duplicate_campaign(
                            meta_token=meta_token,
                            campaign_id=meta_campaign_id,
                        )

                    elif action == "scale":
                        increase_pct = rules["scale_increase_pct"]
                        if previous_budget:
                            new_budget = round(
                                previous_budget * (1 + increase_pct / 100), 2
                            )
                        else:
                            new_budget = None

                        if new_budget:
                            manus_task_id = await self._manus_client.scale_budget(
                                meta_token=meta_token,
                                campaign_id=meta_campaign_id,
                                new_budget=new_budget,
                            )
                            # Update budget in DB
                            supabase.table("campaigns").update(
                                {"daily_budget_usd": new_budget}
                            ).eq("id", input.campaign_db_id).execute()

                    executed = True
                except Exception:
                    logger.exception(
                        "Failed to execute %s for campaign %s",
                        action,
                        input.campaign_db_id,
                    )
                    executed = False

        output = ScaleKillOutput(
            campaign_db_id=input.campaign_db_id,
            action=action,
            reason=reason,
            previous_budget_usd=previous_budget,
            new_budget_usd=new_budget,
            manus_task_id=manus_task_id,
            executed=executed,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
