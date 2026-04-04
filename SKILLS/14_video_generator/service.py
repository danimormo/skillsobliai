import logging
import time
import uuid

import httpx

from core.errors import (
    InsufficientCreditsError,
    InvalidParamsError,
    VertexAIError,
    VertexAITimeoutError,
)
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from .api_client import poll_video_operation, submit_video_generation
from .schemas import (
    VideoGeneratorInput,
    VideoGeneratorOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "video-generator"
STORAGE_BUCKET = "creative-videos"
SIGNED_URL_TTL = 86400  # 24 hours
VIDEO_CREDIT_COST = 1


class VideoGeneratorSkill(BaseSkill[VideoGeneratorInput, VideoGeneratorOutput]):
    name = SKILL_NAME
    version = "2.0.0"
    description = "Generate short product videos via Google Vertex AI Veo 2"
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

        # -- 1. Check video credits ----------------------------------------
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

        # -- 2. Build prompt -----------------------------------------------
        prompt = f"Product showcase video: {input.product_title}, smooth camera motion, professional lighting"
        if input.custom_motion_prompt:
            prompt += f", {input.custom_motion_prompt}"

        # -- 3. If source_image_url provided, download image bytes ---------
        image_bytes: bytes | None = None
        if input.source_image_url:
            async with httpx.AsyncClient(timeout=30.0) as http:
                dl_resp = await http.get(input.source_image_url)
                dl_resp.raise_for_status()
                image_bytes = dl_resp.content

        # -- 4. Submit via Vertex AI Veo 2 ---------------------------------
        operation = submit_video_generation(
            prompt=prompt,
            image_bytes=image_bytes,
            aspect_ratio=input.aspect_ratio,
        )
        operation_name = getattr(operation, "operation", getattr(operation, "name", str(operation)))

        # -- 5. Poll until done (10s interval, 300s timeout) ---------------
        video_bytes = await poll_video_operation(operation)

        # -- 6. Upload video to Supabase Storage ---------------------------
        file_size_mb = round(len(video_bytes) / (1024 * 1024), 2)
        storage_path = f"{ctx.user_id}/{job_id}/video.mp4"

        supabase.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=video_bytes,
            file_options={"content-type": "video/mp4"},
        )

        # -- 7. Generate 24h signed URL ------------------------------------
        signed = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
            path=storage_path,
            expires_in=SIGNED_URL_TTL,
        )
        video_signed_url = signed.get("signedURL", "") if isinstance(signed, dict) else ""

        # -- 8. Increment video_credits_used -------------------------------
        new_used = used + VIDEO_CREDIT_COST
        supabase.table("user_credits").update(
            {"video_credits_used": new_used}
        ).eq("user_id", ctx.user_id).execute()

        # -- 9. Save creative_jobs record ----------------------------------
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

        # -- 10. Return output ---------------------------------------------
        output = VideoGeneratorOutput(
            job_id=job_id,
            video_storage_path=f"{STORAGE_BUCKET}/{storage_path}",
            video_signed_url=video_signed_url,
            thumbnail_signed_url=None,
            duration_seconds=5.0,
            aspect_ratio=input.aspect_ratio,
            file_size_mb=file_size_mb,
            credits_used=VIDEO_CREDIT_COST,
            credits_remaining=limit - new_used,
            vertex_operation_name=str(operation_name),
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
