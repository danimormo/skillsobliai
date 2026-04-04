import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

from core.config import settings
from core.errors import VertexAIError

VARIANT_PROMPTS = {
    "product_shot": "professional product photography, white background, studio lighting, sharp focus, 8k quality",
    "lifestyle": "lifestyle photography, natural setting, person using product, natural lighting, candid",
    "close_up": "macro photography, extreme close-up, product detail, texture visible, 8k",
    "before_after": "split composition, before and after comparison, transformation visual",
    "ugc_style": "candid smartphone photo, authentic feel, user generated content style, slightly imperfect",
}


def generate_images(
    prompt: str,
    num_images: int = 1,
    aspect_ratio: str = "1:1",
) -> list[bytes]:
    """Generate images using Vertex AI Imagen 3. Synchronous."""
    try:
        vertexai.init(
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION,
        )
        model = ImageGenerationModel.from_pretrained(settings.VERTEX_IMAGE_MODEL)
        images = model.generate_images(
            prompt=prompt,
            number_of_images=num_images,
            aspect_ratio=aspect_ratio,
            safety_filter_level="block_some",
            person_generation="allow_adult",
        )
        return [img._image_bytes for img in images]
    except Exception as e:
        raise VertexAIError(
            f"Imagen 3 generation failed: {e}",
            skill="image-creator",
            code="VERTEX_IMAGE_ERROR",
        ) from e
