import logging
import time
import uuid

import httpx

from core.errors import FALError, InsufficientCreditsError, InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.image_creator.api_client import VARIANT_PROMPTS, image_to_image, text_to_image
from SKILLS.image_creator.schemas import (
    GeneratedImage,
    ImageCreatorInput,
    ImageCreatorOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "image-creator"
STORAGE_BUCKET = "generated-images"
SIGNED_URL_TTL = 86400  # 24 hours


class ImageCreatorSkill(BaseSkill[ImageCreatorInput, ImageCreatorOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Generate product images via FAL.ai Flux.2 Pro"
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

        # ── 1. Check image credits ──────────────────────────────────
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

        # ── 2. Build prompt ─────────────────────────────────────────
        prompt = f"{input.product_title}, {VARIANT_PROMPTS[input.variant]}"
        if input.custom_prompt_additions:
            prompt += f", {input.custom_prompt_additions}"

        # ── 3. Call FAL.ai ──────────────────────────────────────────
        if input.source_image_url:
            fal_response = await image_to_image(
                prompt=prompt,
                image_url=input.source_image_url,
                image_size=input.image_size,
                num_images=input.num_images,
            )
        else:
            fal_response = await text_to_image(
                prompt=prompt,
                image_size=input.image_size,
                num_images=input.num_images,
            )

        # ── 4. Download and upload generated images ─────────────────
        fal_images = fal_response.get("images", [])
        generated: list[GeneratedImage] = []

        async with httpx.AsyncClient(timeout=30.0) as http:
            for idx, img_data in enumerate(fal_images):
                img_url = img_data["url"]
                width = img_data.get("width", 0)
                height = img_data.get("height", 0)
                seed = img_data.get("seed")

                # Download image bytes
                dl_resp = await http.get(img_url)
                dl_resp.raise_for_status()
                image_bytes = dl_resp.content

                # Upload to Supabase Storage
                file_name = f"{job_id}_{idx}.png"
                storage_path = f"{ctx.user_id}/{file_name}"

                supabase.storage.from_(STORAGE_BUCKET).upload(
                    path=storage_path,
                    file=image_bytes,
                    file_options={"content-type": "image/png"},
                )

                # ── 5. Generate signed URL ──────────────────────────
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
                        fal_seed=seed,
                        width=width,
                        height=height,
                        variant=input.variant,
                    )
                )

        # ── 6. Update credits ───────────────────────────────────────
        new_used = used + len(generated)
        supabase.table("user_credits").update(
            {"image_credits_used": new_used}
        ).eq("user_id", ctx.user_id).execute()

        # ── 7. Save creative_jobs record ────────────────────────────
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

        # ── 8. Return output ────────────────────────────────────────
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
