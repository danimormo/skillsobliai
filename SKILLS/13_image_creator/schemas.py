from pydantic import BaseModel


class ImageCreatorInput(BaseModel):
    product_title: str
    variant: str = "product_shot"
    custom_prompt_additions: str | None = None
    aspect_ratio: str = "1:1"
    num_images: int = 1


class GeneratedImage(BaseModel):
    storage_path: str
    signed_url: str
    prompt_used: str
    width: int
    height: int
    variant: str


class ImageCreatorOutput(BaseModel):
    job_id: str
    images: list[GeneratedImage]
    credits_used: int
    credits_remaining: int
