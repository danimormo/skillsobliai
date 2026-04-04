from pydantic import BaseModel


class ImageCreatorInput(BaseModel):
    product_title: str
    variant: str = "product_shot"
    custom_prompt_additions: str | None = None
    source_image_url: str | None = None
    num_images: int = 1
    image_size: str = "square_hd"


class GeneratedImage(BaseModel):
    storage_path: str
    signed_url: str
    prompt_used: str
    fal_seed: int | None = None
    width: int
    height: int
    variant: str


class ImageCreatorOutput(BaseModel):
    job_id: str
    images: list[GeneratedImage]
    credits_used: int
    credits_remaining: int
