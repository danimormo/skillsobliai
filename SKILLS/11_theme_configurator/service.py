import logging
import time

from core.errors import (
    IntegrationNotConnectedError,
    InvalidParamsError,
    UpstreamError,
)
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.theme_configurator.api_client import ShopifyThemeClient
from SKILLS.theme_configurator.schemas import (
    ThemeConfiguratorInput,
    ThemeConfiguratorOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "theme-configurator"

# Preset-to-settings mapping
PRESETS = {
    "shrine": {
        "color_schemes.primary": None,  # filled dynamically
        "color_schemes.secondary": None,
        "color_schemes.accent": None,
        "cart_type": "drawer",
    },
    "minimal": {
        "color_schemes.primary": None,
        "color_schemes.secondary": None,
        "color_schemes.accent": None,
        "cart_type": "page",
    },
}


class ThemeConfiguratorSkill(
    BaseSkill[ThemeConfiguratorInput, ThemeConfiguratorOutput]
):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Configure Shopify theme settings via Admin API"
    consumes_credits = True
    credit_cost = 1

    def validate(self, input: ThemeConfiguratorInput) -> bool:
        if not input.shop_domain.strip():
            raise InvalidParamsError(
                message="shop_domain must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: ThemeConfiguratorInput, ctx: SkillContext
    ) -> SkillResult[ThemeConfiguratorOutput]:
        start = time.perf_counter()
        self.validate(input)

        supabase = get_supabase()

        # -- 1. Retrieve Shopify credentials ------------------------------
        try:
            creds_resp = (
                supabase.table("user_integrations")
                .select("access_token, metadata")
                .eq("user_id", ctx.user_id)
                .eq("provider", "shopify")
                .eq("status", "active")
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.exception("Failed to query user_integrations")
            raise UpstreamError(
                message=f"Database error: {exc}",
                skill=SKILL_NAME,
                code="DB_ERROR",
            ) from exc

        if not creds_resp.data:
            raise IntegrationNotConnectedError(
                message=(
                    f"No Shopify integration found for shop {input.shop_domain}. "
                    "Please connect your Shopify store first."
                ),
                skill=SKILL_NAME,
                code="INTEGRATION_NOT_CONNECTED",
            )

        access_token = creds_resp.data[0]["access_token"]
        client = ShopifyThemeClient(input.shop_domain, access_token)

        # -- 2. Get the active (main) theme -------------------------------
        themes = await client.get_themes()
        active_theme = None
        for theme in themes:
            if theme.get("role") == "main":
                active_theme = theme
                break

        if not active_theme:
            raise UpstreamError(
                message="No active (main) theme found on the store",
                skill=SKILL_NAME,
                code="NO_ACTIVE_THEME",
            )

        theme_id = str(active_theme["id"])
        theme_name = active_theme.get("name", "Unknown")

        # -- 3. Build settings to apply -----------------------------------
        settings_to_apply: dict = {}
        settings_modified: list[str] = []

        # Colors
        settings_to_apply["colors_solid_button_labels"] = input.primary_color
        settings_modified.append("primary_color")

        settings_to_apply["colors_secondary"] = input.secondary_color
        settings_modified.append("secondary_color")

        settings_to_apply["colors_accent"] = input.accent_color
        settings_modified.append("accent_color")

        # Sticky cart
        settings_to_apply["cart_type"] = "drawer" if input.enable_sticky_cart else "page"
        settings_modified.append("cart_type")

        # Custom overrides
        for key, value in input.custom_overrides.items():
            settings_to_apply[key] = value
            settings_modified.append(key)

        # -- 4. Apply settings to theme -----------------------------------
        theme_settings = {
            "current": {
                "settings": settings_to_apply,
            }
        }
        await client.update_theme_settings(theme_id, theme_settings)

        output = ThemeConfiguratorOutput(
            shop_domain=input.shop_domain,
            theme_id=theme_id,
            theme_name=theme_name,
            settings_modified=settings_modified,
            success=True,
        )

        # -- Persist to Supabase ------------------------------------------
        try:
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "query_params": input.model_dump(),
                    "result": output.model_dump(),
                    "items_count": len(settings_modified),
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist theme config results to Supabase")

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
