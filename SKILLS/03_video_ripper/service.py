"""Core service for the Video Ripper skill."""

from __future__ import annotations

import logging
import time
import uuid

import httpx

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from . import api_client
from .schemas import (
    VideoRipperInput,
    VideoRipperOutput,
    RippedVideo,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "video-ripper"
BUCKET_NAME = "ripped-videos"
SIGNED_URL_EXPIRY = 86400  # 24 hours


class VideoRipperSkill(BaseSkill[VideoRipperInput, VideoRipperOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = (
        "Download winning TikTok Shop video ads and store them in Supabase Storage"
    )

    def validate(self, input: VideoRipperInput) -> bool:
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
        self, input: VideoRipperInput, ctx: SkillContext
    ) -> SkillResult[VideoRipperOutput]:
        start = time.perf_counter()
        self.validate(input)

        used_product_details = False

        async with httpx.AsyncClient(timeout=30.0) as api_http:
            # ── 1. Always fetch shop videos ─────────────────────────────
            raw_videos = await api_client.fetch_shop_videos(
                api_http,
                product_id=input.product_id,
                limit=input.max_videos * 3,  # over-fetch to allow filtering
            )

            # ── 2. Enrich with product details if US + URL provided ─────
            if input.region == "US" and input.product_url:
                detail_videos = await api_client.fetch_product_details_videos(
                    api_http,
                    product_url=input.product_url,
                    region=input.region,
                )
                if detail_videos:
                    used_product_details = True
                    raw_videos.extend(detail_videos)

        # ── 3. Deduplicate by video ID ──────────────────────────────
        seen: set[str] = set()
        unique_videos: list[dict] = []
        for v in raw_videos:
            vid = str(v.get("ad_id", v.get("id", uuid.uuid4().hex)))
            if vid not in seen:
                seen.add(vid)
                v["_resolved_id"] = vid
                unique_videos.append(v)

        # ── 4. Filter by min_views and min_engagement_rate ──────────
        filtered = [
            v
            for v in unique_videos
            if v.get("views", 0) >= input.min_views
            and v.get("engagement_rate", 0.0) >= input.min_engagement_rate
        ]

        # ── 5. Limit to max_videos ─────────────────────────────────
        filtered = filtered[: input.max_videos]

        # ── 6-8. Download, upload, generate signed URLs ─────────────
        supabase = get_supabase()
        storage = supabase.storage.from_(BUCKET_NAME)
        ripped: list[RippedVideo] = []

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as dl_http:
            for video in filtered:
                download_url = video.get("download_url", "")
                if not download_url:
                    logger.warning(
                        "Skipping video with no download_url: %s",
                        video.get("_resolved_id", "unknown"),
                    )
                    continue

                ad_id = video["_resolved_id"]
                duration = float(
                    video.get("duration", video.get("duration_seconds", 0))
                )
                source = video.get("_source", "shop_videos")
                storage_path = f"{ctx.user_id}/{input.product_id}/{ad_id}.mp4"

                try:
                    # Stream-download the video
                    resp = await dl_http.get(download_url)
                    resp.raise_for_status()
                    video_bytes = resp.content

                    # Upload to Supabase Storage
                    storage.upload(
                        path=storage_path,
                        file=video_bytes,
                        file_options={"content-type": "video/mp4"},
                    )

                    # Generate signed URL (24h)
                    signed = storage.create_signed_url(
                        path=storage_path,
                        expires_in=SIGNED_URL_EXPIRY,
                    )
                    signed_url = signed.get(
                        "signedURL", signed.get("signedUrl", "")
                    )

                    # ── 9. Calculate timestamps ─────────────────────
                    hook_end = round(min(3.0, duration * 0.15), 2)
                    cta_start = round(max(duration - 5.0, 0.0), 2)

                    ripped.append(
                        RippedVideo(
                            ad_id=ad_id,
                            storage_path=storage_path,
                            signed_url=signed_url,
                            duration_seconds=duration,
                            views=int(video.get("views", 0)),
                            engagement_rate=float(
                                video.get("engagement_rate", 0.0)
                            ),
                            hook_end_seconds=hook_end,
                            cta_start_seconds=cta_start,
                            thumbnail_url=video.get("thumbnail_url"),
                            source=source,
                        )
                    )

                except Exception:
                    logger.exception(
                        "Failed to download/upload video %s for product %s",
                        ad_id,
                        input.product_id,
                    )
                    continue

        output = VideoRipperOutput(
            product_id=input.product_id,
            videos_downloaded=len(ripped),
            videos=ripped,
            used_product_details_enrichment=used_product_details,
        )

        # ── 10. Persist metadata to research_results ────────────────
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
