import logging
import time
import uuid

import httpx

from core.errors import FALError, FALTimeoutError, InsufficientCreditsError, InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.video_generator.api_client import poll_video, submit_video
from SKILLS.video_generator.schemas import (
    VideoGeneratorInput,
    VideoGeneratorOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "video-generator"
STORAGE_BUCKET = "generated-videos"
SIGNED_URL_TTL = 86400  # 24 hours
VIDEO_CREDIT_COST = 1


class VideoGeneratorSkill(BaseSkill[VideoGeneratorInput, VideoGeneratorOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Generate short product videos via FAL.ai Kling 2.6"
    consumes_credits = True

    def validate(self, input: VideoGeneratorInput) -> bool:
        if not input.product_title.strip():
            raise InvalidParamsError(
                message="product_title must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: VideoGeneratorInput, ctx: SkillContext
    ) -> SkillResult[VideoGeneratorOutput]:
        start = time.perf_counter()
        self.validate(input)

        supabase = get_supabase()
        job_id = str(uuid.uuid4())

        # ── 1. Check video credits ──────────────────────────────────
        credits_resp = (
            supabase.table("user_credits")
            .select("video_credits_used, video_credits_limit")
            .eq("user_id", ctx.user_id)
            .limit(1)
            .execute()
        )

        if not credits_resp.data:
            raise InsufficientCreditsError(
                message="No credit record found for user",
                skill=SKILL_NAME,
                code="NO_CREDITS_RECORD",
            )

        credits_row = credits_resp.data[0]
        used = credits_row["video_credits_used"]
        limit = credits_row["video_credits_limit"]

        if used + VIDEO_CREDIT_COST > limit:
            raise InsufficientCreditsError(
                message=f"Insufficient video credits: {used}/{limit} used, need {VIDEO_CREDIT_COST} more",
                skill=SKILL_NAME,
                code="INSUFFICIENT_CREDITS",
            )

        # ── 2. Build motion prompt ──────────────────────────────────
        prompt = f"Product showcase video: {input.product_title}, smooth camera motion, professional lighting"
        if input.custom_motion_prompt:
            prompt += f", {input.custom_motion_prompt}"

        # ── 3. Resolve source image ─────────────────────────────────
        image_url = input.source_image_url
        if not image_url:
            raise InvalidParamsError(
                message="source_image_url is required for video generation",
                skill=SKILL_NAME,
                code="MISSING_SOURCE_IMAGE",
            )

        # ── 4. Submit to FAL.ai ─────────────────────────────────────
        submit_resp = await submit_video(
            prompt=prompt,
            image_url=image_url,
            duration="5",
            aspect_ratio=input.aspect_ratio,
        )

        request_id = submit_resp.get("request_id", "")
        if not request_id:
            raise FALError(
                message="FAL did not return a request_id",
                skill=SKILL_NAME,
                code="FAL_NO_REQUEST_ID",
            )

        # ── 5. Poll until done ──────────────────────────────────────
        poll_result = await poll_video(request_id)

        # ── 6. Download video and upload to Supabase Storage ────────
        video_url = poll_result.get("video", {}).get("url", "")
        if not video_url:
            # Try alternate response shapes
            video_url = poll_result.get("video_url", "")
        if not video_url:
            raise FALError(
                message="FAL response did not contain a video URL",
                skill=SKILL_NAME,
                code="FAL_NO_VIDEO_URL",
            )

        async with httpx.AsyncClient(timeout=60.0) as http:
            dl_resp = await http.get(video_url)
            dl_resp.raise_for_status()
            video_bytes = dl_resp.content

        file_size_mb = round(len(video_bytes) / (1024 * 1024), 2)
        file_name = f"{job_id}.mp4"
        storage_path = f"{ctx.user_id}/{file_name}"

        supabase.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=video_bytes,
            file_options={"content-type": "video/mp4"},
        )

        # ── 7. Generate signed URL ──────────────────────────────────
        signed = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
            path=storage_path,
            expires_in=SIGNED_URL_TTL,
        )
        video_signed_url = signed.get("signedURL", "") if isinstance(signed, dict) else ""

        # Thumbnail (optional, from FAL response)
        thumbnail_signed_url = None
        thumbnail_url = poll_result.get("thumbnail", {}).get("url") if isinstance(poll_result.get("thumbnail"), dict) else None
        if thumbnail_url:
            try:
                async with httpx.AsyncClient(timeout=30.0) as http:
                    thumb_resp = await http.get(thumbnail_url)
                    thumb_resp.raise_for_status()
                    thumb_bytes = thumb_resp.content

                thumb_path = f"{ctx.user_id}/{job_id}_thumb.jpg"
                supabase.storage.from_(STORAGE_BUCKET).upload(
                    path=thumb_path,
                    file=thumb_bytes,
                    file_options={"content-type": "image/jpeg"},
                )
                thumb_signed = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
                    path=thumb_path,
                    expires_in=SIGNED_URL_TTL,
                )
                thumbnail_signed_url = thumb_signed.get("signedURL", "") if isinstance(thumb_signed, dict) else None
            except Exception:
                logger.warning("Failed to download/upload thumbnail for job %s", job_id)

        # ── 8. Update video credits ─────────────────────────────────
        new_used = used + VIDEO_CREDIT_COST
        supabase.table("user_credits").update(
            {"video_credits_used": new_used}
        ).eq("user_id", ctx.user_id).execute()

        # ── 9. Save creative_jobs record ────────────────────────────
        try:
            supabase.table("creative_jobs").insert(
                {
                    "id": job_id,
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "product_id": None,
                    "input_params": input.model_dump(),
                    "output_urls": [video_signed_url],
                    "status": "completed",
                    "credits_used": VIDEO_CREDIT_COST,
                }
            ).execute()
        except Exception:
            logger.exception("Failed to save creative_jobs record %s", job_id)

        # ── 10. Return output ───────────────────────────────────────
        duration_seconds = float(poll_result.get("duration", 5.0))

        output = VideoGeneratorOutput(
            job_id=job_id,
            video_storage_path=f"{STORAGE_BUCKET}/{storage_path}",
            video_signed_url=video_signed_url,
            thumbnail_signed_url=thumbnail_signed_url,
            duration_seconds=duration_seconds,
            aspect_ratio=input.aspect_ratio,
            file_size_mb=file_size_mb,
            credits_used=VIDEO_CREDIT_COST,
            credits_remaining=limit - new_used,
            fal_request_id=request_id,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
