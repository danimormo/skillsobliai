from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.B_vision_classifier.schemas import ImageItem, VisionClassifierInput
from SKILLS.B_vision_classifier.service import VisionClassifierSkill
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return VisionClassifierSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return VisionClassifierInput(
        items=[
            ImageItem(item_id="p1", image_url="https://example.com/dress.jpg", title="Summer Dress"),
            ImageItem(item_id="p2", image_url="https://example.com/bag.jpg"),
        ],
        batch_size=5,
    )


def _make_classification() -> dict:
    return {
        "is_fashion": True,
        "confidence": 0.95,
        "category": "dresses",
        "subcategory": "summer_dress",
        "target_gender": "women",
        "gender": "woman",
        "price_tier": "mid",
        "style_tags": ["casual", "summer", "floral"],
        "reasoning": "A floral summer dress suitable for casual wear.",
        "eu_market_fit": True,
    }


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx, sample_input):
    """Successful classification returns items with correct totals."""
    with (
        patch(
            "SKILLS.B_vision_classifier.api_client.download_image",
            new_callable=AsyncMock,
            return_value=("base64data", "image/jpeg"),
        ),
        patch(
            "SKILLS.B_vision_classifier.api_client.classify_image",
            new_callable=AsyncMock,
            return_value=_make_classification(),
        ),
        patch(
            "SKILLS.B_vision_classifier.service.get_supabase",
        ) as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data is not None
    assert result.data.total_processed == 2
    assert result.data.total_fashion == 2
    assert result.data.total_errors == 0
    assert result.data.items[0].is_fashion is True
    assert result.data.items[0].confidence == 0.95


@pytest.mark.asyncio
async def test_run_classification_error_handled(skill, ctx):
    """When image download fails, item is returned with error and is_fashion=False."""
    inp = VisionClassifierInput(
        items=[ImageItem(item_id="fail1", image_url="https://bad-url.com/img.jpg")],
        batch_size=5,
    )

    with (
        patch(
            "SKILLS.B_vision_classifier.api_client.download_image",
            new_callable=AsyncMock,
            side_effect=RuntimeError("download failed"),
        ),
        patch(
            "SKILLS.B_vision_classifier.service.get_supabase",
        ) as mock_sb,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(inp, ctx)

    assert result.success is True
    assert result.data is not None
    assert result.data.total_processed == 1
    assert result.data.total_fashion == 0
    assert result.data.total_errors == 1
    assert result.data.items[0].is_fashion is False
    assert result.data.items[0].classification_error is not None


@pytest.mark.asyncio
async def test_run_batching(skill, ctx):
    """Items are processed in batches of batch_size."""
    items = [
        ImageItem(item_id=f"p{i}", image_url=f"https://example.com/img{i}.jpg")
        for i in range(7)
    ]
    inp = VisionClassifierInput(items=items, batch_size=3)

    with (
        patch(
            "SKILLS.B_vision_classifier.api_client.download_image",
            new_callable=AsyncMock,
            return_value=("base64data", "image/jpeg"),
        ),
        patch(
            "SKILLS.B_vision_classifier.api_client.classify_image",
            new_callable=AsyncMock,
            return_value=_make_classification(),
        ),
        patch(
            "SKILLS.B_vision_classifier.service.get_supabase",
        ) as mock_sb,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = None
        mock_sb.return_value.table.return_value = mock_table

        result = await skill.run(inp, ctx)

    assert result.data.total_processed == 7
    # 3 batches: [0-2], [3-5], [6] -- sleep called between batches (2 times)
    assert mock_sleep.call_count == 2
