import logging
import time
import uuid

import httpx

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.03_kalodata_ripper import api_client
from SKILLS.03_kalodata_ripper.schemas import (
    KalodataRipperInput,
    KalodataRipperOutput,
    RippedVideo,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "kalodata-ripper"
BUCKET_NAME = "ripped-videos"
SIGNED_URL_EXPIRY = 86400  # 24 hours


class KalodataRipperSkill(BaseSkill[KalodataRipperInput, KalodataRipperOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Download top-performing TikTok Shop videos for a product and store them in Supabase Storage"
    consumes_credits = True
    credit_cost = 2

    def validate(self, input: KalodataRipperInput) -> bool:
        if not input.product_id or not input.product_id.strip():
            raise InvalidParamsError(
                message="product_id must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        if input.max_videos < 1:
            raise InvalidParamsError(
                message="max_videos must be at least 1",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: KalodataRipperInput, ctx: SkillContext
    ) -> SkillResult[KalodataRipperOutput]:
        start = time.perf_counter()
        self.validate(input)

        # ── Fetch video list from upstream ───────────────────────────
        raw_videos = await api_client.fetch_product_videos(
            product_id=input.product_id,
            limit=input.max_videos * 3,  # over-fetch to allow filtering
        )

        # ── Filter by min_views and min_engagement_rate ──────────────
        filtered = [
            v for v in raw_videos
            if v.get("views", 0) >= input.min_views
            and v.get("engagement_rate", 0.0) >= input.min_engagement_rate
        ]

        # ── Limit to max_videos ──────────────────────────────────────
        filtered = filtered[: input.max_videos]

        # ── Download each video and upload to Supabase Storage ───────
        supabase = get_supabase()
        storage = supabase.storage.from_(BUCKET_NAME)
        ripped: list[RippedVideo] = []

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            for video in filtered:
                download_url = video.get("download_url", "")
                if not download_url:
                    logger.warning("Skipping video with no download_url: %s", video.get("ad_id", "unknown"))
                    continue

                ad_id = str(video.get("ad_id", video.get("id", uuid.uuid4().hex)))
                duration = float(video.get("duration", video.get("duration_seconds", 0)))
                file_name = f"{ad_id}.mp4"
                storage_path = f"{ctx.user_id}/{input.product_id}/{file_name}"

                try:
                    # Stream-download the video
                    resp = await client.get(download_url)
                    resp.raise_for_status()
                    video_bytes = resp.content

                    # Upload to Supabase Storage
                    storage.upload(
                        path=storage_path,
                        file=video_bytes,
                        file_options={"content-type": "video/mp4"},
                    )

                    # Generate a signed URL (24h expiry)
                    signed = storage.create_signed_url(
                        path=storage_path,
                        expires_in=SIGNED_URL_EXPIRY,
                    )
                    signed_url = signed.get("signedURL", signed.get("signedUrl", ""))

                    # Calculate timestamps
                    hook_end = min(3.0, duration * 0.15)
                    cta_start = max(0.0, duration - 5.0)

                    ripped.append(
                        RippedVideo(
                            ad_id=ad_id,
                            storage_url=signed_url,
                            duration_seconds=duration,
                            views=int(video.get("views", 0)),
                            engagement_rate=float(video.get("engagement_rate", 0.0)),
                            suggested_hook_end=round(hook_end, 2),
                            suggested_cta_start=round(cta_start, 2),
                            thumbnail_url=video.get("thumbnail_url"),
                        )
                    )

                except Exception:
                    logger.exception(
                        "Failed to download/upload video %s for product %s",
                        ad_id,
                        input.product_id,
                    )
                    continue

        output = KalodataRipperOutput(
            product_id=input.product_id,
            videos_downloaded=len(ripped),
            videos=ripped,
        )

        # ── Persist metadata to Supabase ─────────────────────────────
        try:
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "query_params": input.model_dump(),
                    "result": output.model_dump(),
                    "items_count": len(ripped),
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist rip results to Supabase")

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
