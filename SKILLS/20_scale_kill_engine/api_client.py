import logging

import httpx

from core.config import settings
from core.errors import UpstreamError

logger = logging.getLogger(__name__)

SKILL_NAME = "scale-kill-engine"


class ManusActionClient:
    """Executes campaign actions (scale / kill / duplicate) via Manus AI."""

    async def scale_budget(
        self,
        meta_token: str,
        campaign_id: str,
        new_budget: float,
    ) -> str:
        """POST a Manus task to increase the campaign budget.

        Returns the Manus task ID.
        """
        url = f"{settings.MANUS_BASE_URL}/tasks"
        payload = {
            "action": "scale_budget",
            "meta_token": meta_token,
            "campaign_id": campaign_id,
            "new_budget": new_budget,
        }
        return await self._post_task(url, payload)

    async def kill_campaign(
        self,
        meta_token: str,
        campaign_id: str,
    ) -> str:
        """POST a Manus task to pause (kill) the campaign.

        Returns the Manus task ID.
        """
        url = f"{settings.MANUS_BASE_URL}/tasks"
        payload = {
            "action": "kill_campaign",
            "meta_token": meta_token,
            "campaign_id": campaign_id,
        }
        return await self._post_task(url, payload)

    async def duplicate_campaign(
        self,
        meta_token: str,
        campaign_id: str,
    ) -> str:
        """POST a Manus task to duplicate the campaign.

        Returns the Manus task ID.
        """
        url = f"{settings.MANUS_BASE_URL}/tasks"
        payload = {
            "action": "duplicate_campaign",
            "meta_token": meta_token,
            "campaign_id": campaign_id,
        }
        return await self._post_task(url, payload)

    async def _post_task(self, url: str, payload: dict) -> str:
        """Send a task to Manus and return the task ID."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise UpstreamError(
                    message=f"Manus API returned {exc.response.status_code}: {exc.response.text}",
                    skill=SKILL_NAME,
                    code="UPSTREAM_ERROR",
                ) from exc
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                raise UpstreamError(
                    message=f"Manus API unreachable: {exc}",
                    skill=SKILL_NAME,
                    code="UPSTREAM_ERROR",
                ) from exc

        data = response.json()
        return data.get("task_id", "")
