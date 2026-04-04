from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.video_generator.schemas import VideoGeneratorInput
from SKILLS.video_generator.service import VideoGeneratorSkill
from core.errors import FALTimeoutError, InsufficientCreditsError, InvalidParamsError
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return VideoGeneratorSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return VideoGeneratorInput(
        product_title="Organic Matcha Powder",
        source_image_url="https://example.com/product.jpg",
        aspect_ratio="9:16",
    )


def _mock_supabase():
    """Build a mock supabase client with credit check, storage, and table ops."""
    mock_sb = MagicMock()

    # user_credits select
    credits_result = MagicMock()
    credits_result.data = [{"video_credits_used": 3, "video_credits_limit": 50}]

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
    """Successful generation returns video output and deducts credits."""
    mock_sb = _mock_supabase()
    mock_http_resp = MagicMock()
    mock_http_resp.content = b"\x00\x00\x00 ftypisom" + b"\x00" * 1000
    mock_http_resp.raise_for_status = MagicMock()

    submit_resp = {"request_id": "req-abc-123"}
    poll_resp = {
        "status": "COMPLETED",
        "video": {"url": "https://fal.ai/output/video.mp4"},
        "duration": 5.0,
    }

    with (
        patch(
            "SKILLS.video_generator.service.get_supabase",
            return_value=mock_sb,
        ),
        patch(
            "SKILLS.video_generator.service.submit_video",
            new_callable=AsyncMock,
            return_value=submit_resp,
        ),
        patch(
            "SKILLS.video_generator.service.poll_video",
            new_callable=AsyncMock,
            return_value=poll_resp,
        ),
        patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=mock_http_resp,
        ),
    ):
        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data is not None
    assert result.data.credits_used == 1
    assert result.data.credits_remaining == 46  # 50 - 3 - 1
    assert result.data.fal_request_id == "req-abc-123"
    assert result.data.duration_seconds == 5.0
    assert result.data.aspect_ratio == "9:16"


@pytest.mark.asyncio
async def test_run_insufficient_credits(skill, ctx, sample_input):
    """Raises InsufficientCreditsError when user is at limit."""
    mock_sb = MagicMock()
    credits_result = MagicMock()
    credits_result.data = [{"video_credits_used": 50, "video_credits_limit": 50}]

    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = credits_result
    mock_sb.table.return_value = chain

    with (
        patch(
            "SKILLS.video_generator.service.get_supabase",
            return_value=mock_sb,
        ),
        pytest.raises(InsufficientCreditsError),
    ):
        await skill.run(sample_input, ctx)


@pytest.mark.asyncio
async def test_validate_empty_title(skill, ctx):
    """Empty product_title raises InvalidParamsError."""
    bad_input = VideoGeneratorInput(
        product_title="   ",
        source_image_url="https://example.com/img.jpg",
    )

    with pytest.raises(InvalidParamsError, match="product_title must not be empty"):
        skill.validate(bad_input)
