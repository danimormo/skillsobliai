# Skill 14 -- Video Generator

## Description

Generates 5-second product videos via FAL.ai Kling 2.6 (image-to-video).
Submits the job and polls for completion. Consumes video credits.

## Endpoint

```
POST /video-generator/run
```

### Authentication

Pass a Bearer token in the `Authorization` header. The token is used as the
user identifier for credit checks and storage.

```
Authorization: Bearer <user_id>
```

## Input

| Field                  | Type   | Required | Default  | Description                                  |
|------------------------|--------|----------|----------|----------------------------------------------|
| `product_title`        | `str`  | Yes      | --       | Title of the product for the motion prompt.  |
| `source_image_url`     | `str?` | No       | `null`   | Source image URL (required for generation).   |
| `custom_motion_prompt` | `str?` | No       | `null`   | Extra motion/style instructions.             |
| `aspect_ratio`         | `str`  | No       | `"9:16"` | Video aspect ratio.                          |

## Output

| Field                  | Type    | Description                                |
|------------------------|---------|--------------------------------------------|
| `job_id`               | `str`   | Unique job identifier.                     |
| `video_storage_path`   | `str`   | Path in Supabase Storage bucket.           |
| `video_signed_url`     | `str`   | Pre-signed URL valid for 24 hours.         |
| `thumbnail_signed_url` | `str?`  | Thumbnail signed URL (if available).       |
| `duration_seconds`     | `float` | Video duration in seconds.                 |
| `aspect_ratio`         | `str`   | Aspect ratio of the generated video.       |
| `file_size_mb`         | `float` | File size in megabytes.                    |
| `credits_used`         | `int`   | Number of video credits consumed.          |
| `credits_remaining`    | `int`   | Remaining video credits for the user.      |
| `fal_request_id`       | `str`   | FAL.ai request ID for reference.           |

## curl Example

```bash
curl -X POST http://localhost:8000/video-generator/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "product_title": "Organic Green Tea Matcha Powder",
    "source_image_url": "https://example.com/product.jpg",
    "aspect_ratio": "9:16"
  }'
```

## Credits

Each video generation consumes 1 video credit. Credits are checked before
generation and deducted after successful completion. If the user has
insufficient credits, a `402` response is returned.

## Polling

After submitting to FAL.ai, the service polls every 5 seconds for up to 120
seconds. If the job does not complete within this window, a `504` timeout
response is returned.

## Caching

No caching -- every invocation produces unique generated output.
