import asyncio
import logging

import httpx

from core.config import settings
from core.errors import ManusError, ManusTimeoutError, MetaAPIError

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 120


class ManusClient:
    """Interact with the Manus AI campaign-launch API."""

    def __init__(self) -> None:
        self.base_url: str = settings.MANUS_BASE_URL

    async def submit_task(self, meta_token: str, task_config: dict) -> str:
        """POST a campaign task to Manus and return the task_id."""
        url = f"{self.base_url}/tasks"
        headers = {
            "Authorization": f"Bearer {meta_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=task_config)
            if response.status_code != 200:
                raise ManusError(
                    message=f"Manus submit failed ({response.status_code}): {response.text}",
                    skill="campaign-launcher",
                    code="MANUS_SUBMIT_ERROR",
                )
            data = response.json()
            return data["task_id"]

    async def poll_task(self, meta_token: str, task_id: str) -> dict:
        """Poll Manus task status every 5 s, timeout after 120 s."""
        url = f"{self.base_url}/tasks/{task_id}"
        headers = {"Authorization": f"Bearer {meta_token}"}
        elapsed = 0.0

        async with httpx.AsyncClient(timeout=30.0) as client:
            while elapsed < POLL_TIMEOUT_S:
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    raise ManusError(
                        message=f"Manus poll failed ({response.status_code}): {response.text}",
                        skill="campaign-launcher",
                        code="MANUS_POLL_ERROR",
                    )
                data = response.json()
                status = data.get("status")
                if status == "completed":
                    return data
                if status == "failed":
                    raise ManusError(
                        message=f"Manus task {task_id} failed: {data.get('error', 'unknown')}",
                        skill="campaign-launcher",
                        code="MANUS_TASK_FAILED",
                    )
                await asyncio.sleep(POLL_INTERVAL_S)
                elapsed += POLL_INTERVAL_S

        raise ManusTimeoutError(
            message=f"Manus task {task_id} timed out after {POLL_TIMEOUT_S}s",
            skill="campaign-launcher",
            code="MANUS_TIMEOUT",
        )


class MetaVerifier:
    """Verify campaign existence via the Meta Graph API."""

    def __init__(self) -> None:
        self.base_url: str = settings.META_BASE_URL
        self.api_version: str = settings.META_API_VERSION

    async def verify_campaign(self, meta_token: str, campaign_id: str) -> dict:
        """GET campaign details from the Meta Graph API."""
        url = f"{self.base_url}/{self.api_version}/{campaign_id}"
        params = {"access_token": meta_token}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                raise MetaAPIError(
                    message=f"Meta campaign verification failed ({response.status_code}): {response.text}",
                    skill="campaign-launcher",
                    code="META_VERIFY_ERROR",
                )
            return response.json()
