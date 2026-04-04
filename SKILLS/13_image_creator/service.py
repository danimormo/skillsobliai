import logging
import time
import uuid

from core.errors import InsufficientCreditsError, InvalidParamsError, VertexAIError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from .api_client import VARIANT_PROMPTS, generate_images
from .schemas import (
    GeneratedImage,
    ImageCreatorInput,
    ImageCreatorOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "image-creator"
STORAGE_BUCKET = "creative-images"
SIGNED_URL_TTL = 86400  # 24 hours

# Aspect-ratio to pixel dimensions (for metadata)
ASPECT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "9:16": (768, 1344),
    "16:9": (1344, 768),
    "3:4": (896, 1152),
    "4:3": (1152, 896),
}


class ImageCreatorSkill(BaseSkill[ImageCreatorInput, ImageCreatorOutput]):
    name = SKILL_NAME
    version = "2.0.0"
    description = "Generate product images via Google Vertex AI Imagen 3"
    consumes_credits = True

    def validate(self, input: ImageCreatorInput) -> bool:
        if not input.product_title.strip():
            raise InvalidParamsError(
                message="product_title must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        if input.variant not in VARIANT_PROMPTS:
            raise InvalidParamsError(
                message=f"Unknown variant '{input.variant}'. Choose from: {list(VARIANT_PROMPTS.keys())}",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        if input.num_images < 1 or input.num_images > 4:
            raise InvalidParamsError(
                message="num_images must be between 1 and 4",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: ImageCreatorInput, ctx: SkillContext
    ) -> SkillResult[ImageCreatorOutput]:
        start = time.perf_counter()
        self.validate(input)

        supabase = get_supabase()
        job_id = str(uuid.uuid4())

        # -- 1. Check image credits ----------------------------------------
        credits_resp = (
            supabase.table("user_credits")
            .select("image_credits_used, image_credits_limit")
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
        used = credits_row["image_credits_used"]
        limit = credits_row["image_credits_limit"]

        if used + input.num_images > limit:
            raise InsufficientCreditsError(
                message=f"Insufficient image credits: {used}/{limit} used, need {input.num_images} more",
                skill=SKILL_NAME,
                code="INSUFFICIENT_CREDITS",
            )

        # -- 2. Build prompt -----------------------------------------------
        prompt = f"{VARIANT_PROMPTS[input.variant]}, {input.product_title}"
        if input.custom_prompt_additions:
            prompt += f", {input.custom_prompt_additions}"

        # -- 3. Call Vertex AI Imagen 3 (synchronous) ----------------------
        image_bytes_list = generate_images(
            prompt=prompt,
            num_images=input.num_images,
            aspect_ratio=input.aspect_ratio,
        )

        # -- 4. Upload bytes to Supabase Storage ---------------------------
        width, height = ASPECT_DIMENSIONS.get(input.aspect_ratio, (1024, 1024))
        generated: list[GeneratedImage] = []

        for idx, image_bytes in enumerate(image_bytes_list):
            file_name = f"{job_id}_{idx}.png"
            storage_path = f"{ctx.user_id}/{job_id}/{file_name}"

            supabase.storage.from_(STORAGE_BUCKET).upload(
                path=storage_path,
                file=image_bytes,
                file_options={"content-type": "image/png"},
            )

            # -- 5. Generate 24h signed URL --------------------------------
            signed = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
                path=storage_path,
                expires_in=SIGNED_URL_TTL,
            )
            signed_url = signed.get("signedURL", "") if isinstance(signed, dict) else ""

            generated.append(
                GeneratedImage(
                    storage_path=f"{STORAGE_BUCKET}/{storage_path}",
                    signed_url=signed_url,
                    prompt_used=prompt,
                    width=width,
                    height=height,
                    variant=input.variant,
                )
            )

        # -- 6. Increment image_credits_used -------------------------------
        new_used = used + len(generated)
        supabase.table("user_credits").update(
            {"image_credits_used": new_used}
        ).eq("user_id", ctx.user_id).execute()

        # -- 7. Save creative_jobs record ----------------------------------
        output_urls = [g.signed_url for g in generated]
        try:
            supabase.table("creative_jobs").insert(
                {
                    "id": job_id,
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "product_id": None,
                    "input_params": input.model_dump(),
                    "output_urls": output_urls,
                    "status": "completed",
                    "credits_used": len(generated),
                }
            ).execute()
        except Exception:
            logger.exception("Failed to save creative_jobs record %s", job_id)

        # -- 8. Return output ----------------------------------------------
        output = ImageCreatorOutput(
            job_id=job_id,
            images=generated,
            credits_used=len(generated),
            credits_remaining=limit - new_used,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
