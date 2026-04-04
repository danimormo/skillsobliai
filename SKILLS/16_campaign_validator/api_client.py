import logging

import httpx

from core.config import settings
from core.errors import MetaAPIError

logger = logging.getLogger(__name__)

SKILL_NAME = "campaign-validator"


class MetaValidator:
    """Validate Meta ad-account, pixel and funding via the Graph API."""

    def __init__(self) -> None:
        self.base_url: str = settings.META_BASE_URL
        self.api_version: str = settings.META_API_VERSION

    async def check_ad_account(self, token: str, ad_account_id: str) -> dict:
        """GET ad account status."""
        url = f"{self.base_url}/{self.api_version}/{ad_account_id}"
        params = {"access_token": token, "fields": "account_status,name,currency"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                raise MetaAPIError(
                    message=f"Ad account check failed ({response.status_code}): {response.text}",
                    skill=SKILL_NAME,
                    code="META_AD_ACCOUNT_ERROR",
                )
            return response.json()

    async def check_pixel(self, token: str, pixel_id: str) -> dict:
        """GET pixel status."""
        url = f"{self.base_url}/{self.api_version}/{pixel_id}"
        params = {"access_token": token, "fields": "name,is_unavailable,last_fired_time"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                raise MetaAPIError(
                    message=f"Pixel check failed ({response.status_code}): {response.text}",
                    skill=SKILL_NAME,
                    code="META_PIXEL_ERROR",
                )
            return response.json()

    async def check_funding(self, token: str, ad_account_id: str) -> dict:
        """GET funding source for the ad account."""
        url = f"{self.base_url}/{self.api_version}/{ad_account_id}/funding_source"
        params = {"access_token": token}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                raise MetaAPIError(
                    message=f"Funding check failed ({response.status_code}): {response.text}",
                    skill=SKILL_NAME,
                    code="META_FUNDING_ERROR",
                )
            return response.json()
