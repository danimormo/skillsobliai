from unittest.mock import MagicMock, patch

import pytest

from SKILLS.image_creator.schemas import ImageCreatorInput
from SKILLS.image_creator.service import ImageCreatorSkill
from core.errors import InsufficientCreditsError, InvalidParamsError
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return ImageCreatorSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return ImageCreatorInput(
        product_title="Organic Matcha Powder",
        variant="product_shot",
        num_images=1,
        aspect_ratio="1:1",
    )


def _mock_supabase():
    """Build a mock supabase client with credit check, storage, and table ops."""
    mock_sb = MagicMock()

    # user_credits select
    credits_result = MagicMock()
    credits_result.data = [{"image_credits_used": 5, "image_credits_limit": 100}]

    select_chain = MagicMock()
    select_chain.select.return_value = select_chain
    select_chain.eq.return_value = select_chain
    select_chain.limit.return_value = select_chain
    select_chain.execute.return_value = credits_result

    # update chain
    update_chain = MagicMock()
    update_chain.update.return_value = update_chain
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = None

    # insert chain (creative_jobs)
    insert_chain = MagicMock()
    insert_chain.insert.return_value = insert_chain
    insert_chain.execute.return_value = None

    def table_router(name):
        if name == "user_credits":
            tbl = MagicMock()
            tbl.select = select_chain.select
            tbl.update = update_chain.update
            return tbl
        return insert_chain

    mock_sb.table = MagicMock(side_effect=table_router)

    # storage mock
    bucket = MagicMock()
    bucket.upload.return_value = None
    bucket.create_signed_url.return_value = {"signedURL": "https://storage.example.com/signed"}
    mock_sb.storage.from_.return_value = bucket

    return mock_sb


@pytest.mark.asyncio
async def test_run_happy_path(skill, ctx, sample_input):
    """Successful generation returns images and deducts credits."""
    mock_sb = _mock_supabase()
    fake_image_bytes = b"\x89PNG fake image bytes"

    with (
        patch(
            "SKILLS.image_creator.service.get_supabase",
            return_value=mock_sb,
        ),
        patch(
            "SKILLS.image_creator.service.generate_images",
            return_value=[fake_image_bytes],
        ),
    ):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data is not None
    assert len(result.data.images) == 1
    assert result.data.credits_used == 1
    assert result.data.credits_remaining == 94  # 100 - 5 - 1
    assert result.data.images[0].variant == "product_shot"
    assert result.data.images[0].width == 1024
    assert result.data.images[0].height == 1024


@pytest.mark.asyncio
async def test_run_insufficient_credits(skill, ctx, sample_input):
    """Raises InsufficientCreditsError when user is at limit."""
    mock_sb = MagicMock()
    credits_result = MagicMock()
    credits_result.data = [{"image_credits_used": 100, "image_credits_limit": 100}]

    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = credits_result
    mock_sb.table.return_value = chain

    with (
        patch(
            "SKILLS.image_creator.service.get_supabase",
            return_value=mock_sb,
        ),
        pytest.raises(InsufficientCreditsError),
    ):
        await skill.run(sample_input, ctx)


@pytest.mark.asyncio
async def test_validate_invalid_variant(skill, ctx):
    """Invalid variant raises InvalidParamsError."""
    bad_input = ImageCreatorInput(
        product_title="Test Product",
        variant="nonexistent_variant",
        num_images=1,
    )

    with pytest.raises(InvalidParamsError, match="Unknown variant"):
        skill.validate(bad_input)
