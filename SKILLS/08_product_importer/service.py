import logging
import time
import uuid

from core.errors import IntegrationNotConnectedError, InvalidParamsError, UpstreamError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from SKILLS.product_importer.api_client import ShopifyClient
from SKILLS.product_importer.schemas import (
    ProductImportInput,
    ProductImportOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "product-importer"


class ProductImporterSkill(BaseSkill[ProductImportInput, ProductImportOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Import products into a Shopify store with pricing and images"
    consumes_credits = True
    credit_cost = 2

    def validate(self, input: ProductImportInput) -> bool:
        if not input.title.strip():
            raise InvalidParamsError(
                message="title must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        if input.cost_usd <= 0:
            raise InvalidParamsError(
                message="cost_usd must be positive",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        if not input.shop_domain.strip():
            raise InvalidParamsError(
                message="shop_domain must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: ProductImportInput, ctx: SkillContext
    ) -> SkillResult[ProductImportOutput]:
        start = time.perf_counter()
        self.validate(input)

        supabase = get_supabase()
        job_id = str(uuid.uuid4())

        # ── 1. Retrieve Shopify credentials ─────────────────────────
        try:
            creds_resp = (
                supabase.table("user_integrations")
                .select("access_token, metadata")
                .eq("user_id", ctx.user_id)
                .eq("provider", "shopify")
                .eq("status", "active")
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.exception("Failed to query user_integrations")
            raise UpstreamError(
                message=f"Database error: {exc}",
                skill=SKILL_NAME,
                code="DB_ERROR",
            ) from exc

        if not creds_resp.data:
            raise IntegrationNotConnectedError(
                message=f"No Shopify integration found for shop {input.shop_domain}. Please connect your Shopify store first.",
                skill=SKILL_NAME,
                code="INTEGRATION_NOT_CONNECTED",
            )

        access_token = creds_resp.data[0]["access_token"]
        client = ShopifyClient(input.shop_domain, access_token)

        # ── 2. Create import_jobs record ────────────────────────────
        try:
            supabase.table("import_jobs").insert(
                {
                    "id": job_id,
                    "user_id": ctx.user_id,
                    "shop_domain": input.shop_domain,
                    "product_data": input.model_dump(),
                    "status": "pending",
                }
            ).execute()
        except Exception:
            logger.exception("Failed to create import_jobs record")

        # ── 3. Build Shopify product payload ────────────────────────
        price = round(input.cost_usd * input.markup_multiplier, 2)

        variants_payload = []
        if input.variants:
            for v in input.variants:
                variant_data: dict = {
                    "title": v.title,
                    "inventory_quantity": v.inventory_quantity,
                }
                if v.sku:
                    variant_data["sku"] = v.sku
                variant_data["price"] = str(v.price if v.price is not None else price)
                variants_payload.append(variant_data)
        else:
            variants_payload.append(
                {
                    "title": "Default",
                    "price": str(price),
                    "inventory_quantity": 100,
                }
            )

        product_payload: dict = {
            "title": input.title,
            "body_html": input.description_html,
            "variants": variants_payload,
            "tags": ", ".join(input.tags) if input.tags else "",
        }
        if input.vendor:
            product_payload["vendor"] = input.vendor
        if input.product_type:
            product_payload["product_type"] = input.product_type

        # ── 4. Idempotency check ────────────────────────────────────
        try:
            existing = await client.find_product_by_title(input.title)
        except Exception:
            logger.warning("Idempotency check failed, proceeding with create")
            existing = None

        shopify_product: dict
        try:
            if existing:
                product_id = str(existing["id"])
                shopify_product = await client.update_product(product_id, product_payload)
                logger.info("Updated existing product %s", product_id)
            else:
                shopify_product = await client.create_product(product_payload)
                logger.info("Created new product %s", shopify_product.get("id"))
        except Exception as exc:
            # ── Full failure ─────────────────────────────────────────
            self._update_job_status(supabase, job_id, "failed", error=str(exc))
            raise UpstreamError(
                message=f"Failed to create/update Shopify product: {exc}",
                skill=SKILL_NAME,
                code="SHOPIFY_PRODUCT_ERROR",
            ) from exc

        shopify_product_id = str(shopify_product["id"])

        # ── 5. Upload images one by one ─────────────────────────────
        images_uploaded = 0
        image_errors = 0
        for image_url in input.image_urls:
            try:
                await client.add_image(shopify_product_id, image_url)
                images_uploaded += 1
            except Exception:
                image_errors += 1
                logger.warning(
                    "Failed to upload image %s for product %s",
                    image_url,
                    shopify_product_id,
                )

        # ── 6. Determine status and update job ──────────────────────
        if image_errors > 0 and images_uploaded > 0:
            status = "partial"
        elif image_errors > 0 and images_uploaded == 0 and input.image_urls:
            status = "partial"
        else:
            status = "completed"

        self._update_job_status(
            supabase,
            job_id,
            status,
            shopify_product_id=shopify_product_id,
        )

        # ── 7. Build output ─────────────────────────────────────────
        shopify_product_url = (
            f"https://{input.shop_domain}/admin/products/{shopify_product_id}"
        )
        handle = shopify_product.get("handle", "")
        shopify_storefront_url = f"https://{input.shop_domain}/products/{handle}"

        output = ProductImportOutput(
            job_id=job_id,
            shopify_product_id=shopify_product_id,
            shopify_product_url=shopify_product_url,
            shopify_storefront_url=shopify_storefront_url,
            title=input.title,
            price=price,
            variants_count=len(variants_payload),
            images_uploaded=images_uploaded,
            status=status,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )

    @staticmethod
    def _update_job_status(
        supabase,
        job_id: str,
        status: str,
        *,
        shopify_product_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Update the import_jobs record in Supabase."""
        try:
            update_data: dict = {"status": status}
            if shopify_product_id:
                update_data["shopify_product_id"] = shopify_product_id
            if error:
                update_data["error"] = error
            supabase.table("import_jobs").update(update_data).eq("id", job_id).execute()
        except Exception:
            logger.exception("Failed to update import_jobs record %s", job_id)
