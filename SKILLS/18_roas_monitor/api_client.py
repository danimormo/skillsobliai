import logging

import httpx

from core.config import settings
from core.errors import UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "roas-monitor"


class MetaInsightsClient:
    """Fetches campaign-level ROAS data from the Meta Graph API."""

    async def get_campaign_insights(
        self,
        token: str,
        ad_account_id: str,
        campaign_id: str,
    ) -> dict:
        """Fetch today's insights for a single campaign and compute ROAS.

        Returns a dict with keys: roas, spend, revenue, impressions, clicks, conversions.
        """
        url = (
            f"{settings.META_BASE_URL}/{settings.META_API_VERSION}"
            f"/act_{ad_account_id}/insights"
        )
        params = {
            "fields": "spend,actions,action_values,impressions,clicks",
            "filtering": (
                f'[{{"field":"campaign.id","operator":"EQUAL","value":"{campaign_id}"}}]'
            ),
            "date_preset": "today",
            "access_token": token,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise UpstreamError(
                    message=f"Meta API returned {exc.response.status_code}: {exc.response.text}",
                    skill=SKILL_NAME,
                    code="UPSTREAM_ERROR",
                ) from exc
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                raise UpstreamError(
                    message=f"Meta API unreachable: {exc}",
                    skill=SKILL_NAME,
                    code="UPSTREAM_ERROR",
                ) from exc

        data = response.json().get("data", [])
        if not data:
            return {
                "roas": 0.0,
                "spend": 0.0,
                "revenue": 0.0,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
            }

        row = data[0]
        spend = float(row.get("spend", 0))
        impressions = int(row.get("impressions", 0))
        clicks = int(row.get("clicks", 0))

        action_values = row.get("action_values", [])
        purchase_value = sum(
            float(av["value"])
            for av in action_values
            if av.get("action_type") == "purchase"
        )

        actions = row.get("actions", [])
        conversions = sum(
            int(a.get("value", 0))
            for a in actions
            if a.get("action_type") == "purchase"
        )

        roas = purchase_value / spend if spend > 0 else 0.0

        return {
            "roas": round(roas, 4),
            "spend": round(spend, 2),
            "revenue": round(purchase_value, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
        }
