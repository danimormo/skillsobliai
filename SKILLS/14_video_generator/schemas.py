from pydantic import BaseModel


class VideoGeneratorInput(BaseModel):
    product_title: str
    source_image_url: str | None = None
    custom_motion_prompt: str | None = None
    aspect_ratio: str = "9:16"


class VideoGeneratorOutput(BaseModel):
    job_id: str
    video_storage_path: str
    video_signed_url: str
    thumbnail_signed_url: str | None = None
    duration_seconds: float
    aspect_ratio: str
    file_size_mb: float
    credits_used: int
    credits_remaining: int
    vertex_operation_name: str
