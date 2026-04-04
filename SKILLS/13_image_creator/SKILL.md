# Skill 13 -- Image Creator

## Description

Generates product images via FAL.ai Flux.2 Pro. Supports text-to-image and
image-to-image workflows with multiple style variants. Consumes image credits.

## Endpoint

```
POST /image-creator/run
```

### Authentication

Pass a Bearer token in the `Authorization` header. The token is used as the
user identifier for credit checks and storage.

```
Authorization: Bearer <user_id>
```

## Input

| Field                    | Type     | Required | Default          | Description                                    |
|--------------------------|----------|----------|------------------|------------------------------------------------|
| `product_title`          | `str`    | Yes      | --               | Title of the product to generate images for.   |
| `variant`                | `str`    | No       | `"product_shot"` | Style variant (see variants below).            |
| `custom_prompt_additions`| `str?`   | No       | `null`           | Extra prompt text appended to generated prompt. |
| `source_image_url`       | `str?`   | No       | `null`           | Source image URL for image-to-image mode.      |
| `num_images`             | `int`    | No       | `1`              | Number of images to generate (1-4).            |
| `image_size`             | `str`    | No       | `"square_hd"`    | FAL image size preset.                         |

### Variants

| Key            | Description                                          |
|----------------|------------------------------------------------------|
| `product_shot` | Professional product photography, white background.  |
| `lifestyle`    | Natural setting with a person using the product.     |
| `close_up`     | Macro close-up of product detail and texture.        |
| `before_after` | Split before-and-after comparison visual.            |
| `ugc_style`    | Candid smartphone-style user generated content.      |

## Output

| Field              | Type              | Description                          |
|--------------------|-------------------|--------------------------------------|
| `job_id`           | `str`             | Unique job identifier.               |
| `images`           | `GeneratedImage[]`| List of generated image objects.     |
| `credits_used`     | `int`             | Number of image credits consumed.    |
| `credits_remaining`| `int`             | Remaining image credits for the user.|

### GeneratedImage object

| Field          | Type     | Description                              |
|----------------|----------|------------------------------------------|
| `storage_path` | `str`    | Path in Supabase Storage bucket.         |
| `signed_url`   | `str`    | Pre-signed URL valid for 24 hours.       |
| `prompt_used`  | `str`    | Full prompt sent to FAL.ai.              |
| `fal_seed`     | `int?`   | Seed used by FAL for reproducibility.    |
| `width`        | `int`    | Image width in pixels.                   |
| `height`       | `int`    | Image height in pixels.                  |
| `variant`      | `str`    | Style variant used.                      |

## curl Example

```bash
curl -X POST http://localhost:8000/image-creator/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer user_abc123" \
  -d '{
    "product_title": "Organic Green Tea Matcha Powder",
    "variant": "product_shot",
    "num_images": 2,
    "image_size": "square_hd"
  }'
```

## Credits

Each generated image consumes 1 image credit. Credits are checked before
generation and deducted after successful completion. If the user has
insufficient credits, a `402` response is returned.

## Caching

No caching -- every invocation produces unique generated output.
