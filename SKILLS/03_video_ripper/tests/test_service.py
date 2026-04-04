"""Tests for VideoRipperSkill service."""

import importlib

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.skill_interface import SkillContext

_schemas = importlib.import_module("SKILLS.03_video_ripper.schemas")
VideoRipperInput = _schemas.VideoRipperInput

_service = importlib.import_module("SKILLS.03_video_ripper.service")
VideoRipperSkill = _service.VideoRipperSkill


def _make_ctx(user_id: str = "user-1") -> SkillContext:
    return SkillContext(user_id=user_id)


def _fake_video(
    ad_id: str,
    views: int = 50000,
    engagement_rate: float = 0.05,
    duration: float = 30.0,
    source: str = "shop_videos",
):
    return {
        "ad_id": ad_id,
        "download_url": f"https://cdn.example.com/{ad_id}.mp4",
        "views": views,
        "engagement_rate": engagement_rate,
        "duration": duration,
        "thumbnail_url": f"https://cdn.example.com/{ad_id}_thumb.jpg",
        "_source": source,
        "_resolved_id": ad_id,
    }


def _mock_supabase():
    """Return a mock Supabase client with storage and table stubs."""
    mock_storage_bucket = MagicMock()
    mock_storage_bucket.upload.return_value = None
    mock_storage_bucket.create_signed_url.return_value = {
        "signedURL": "https://storage.example.com/signed/video.mp4"
    }

    mock_storage = MagicMock()
    mock_storage.from_.return_value = mock_storage_bucket

    mock_table_exec = MagicMock()
    mock_table_exec.execute.return_value = None
    mock_table_insert = MagicMock()
    mock_table_insert.insert.return_value = mock_table_exec
    mock_table = MagicMock(return_value=mock_table_insert)

    mock_client = MagicMock()
    mock_client.storage = mock_storage
    mock_client.table = mock_table

    return mock_client


def _mock_http_client():
    """Return a mock httpx.AsyncClient for video downloads."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"\x00\x00\x00\x1cftypisom"  # fake mp4 bytes
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
async def test_happy_path_downloads_and_uploads():
    """Service fetches shop videos, downloads them, uploads to storage, returns result."""
    videos = [
        _fake_video("v1", views=100000, engagement_rate=0.06, duration=25.0),
        _fake_video("v2", views=80000, engagement_rate=0.04, duration=40.0),
        _fake_video("v3", views=200000, engagement_rate=0.08, duration=15.0),
    ]

    mock_sb = _mock_supabase()
    mock_dl = _mock_http_client()

    # Also mock the api_client httpx.AsyncClient context manager
    mock_api_cm = AsyncMock()
    mock_api_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_api_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "SKILLS.03_video_ripper.api_client.fetch_shop_videos",
            new_callable=AsyncMock,
        ) as mock_fetch_shop,
        patch(
            "SKILLS.03_video_ripper.service.get_supabase",
            return_value=mock_sb,
        ),
        patch(
            "SKILLS.03_video_ripper.service.httpx.AsyncClient",
            side_effect=[mock_api_cm, mock_dl],
        ),
    ):
        mock_fetch_shop.return_value = videos

        skill = VideoRipperSkill()
        inp = VideoRipperInput(
            product_id="prod-123",
            max_videos=5,
            min_views=10000,
            min_engagement_rate=0.02,
        )
        result = await skill.run(inp, _make_ctx())

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.product_id == "prod-123"
    assert result.data.videos_downloaded == 3
    assert len(result.data.videos) == 3
    assert result.data.used_product_details_enrichment is False

    # Verify timestamp calculations for first video (duration=25.0)
    v1 = result.data.videos[0]
    assert v1.ad_id == "v1"
    assert v1.hook_end_seconds == min(3.0, 25.0 * 0.15)
    assert v1.cta_start_seconds == 20.0  # 25 - 5
    assert v1.source == "shop_videos"


@pytest.mark.asyncio
async def test_us_enrichment_with_product_url():
    """When region=US and product_url provided, product details endpoint is called."""
    shop_videos = [
        _fake_video("v1", views=100000, engagement_rate=0.06, duration=20.0),
    ]
    detail_videos = [
        _fake_video("v2", views=90000, engagement_rate=0.05, duration=35.0, source="product_details"),
    ]

    mock_sb = _mock_supabase()
    mock_dl = _mock_http_client()

    mock_api_cm = AsyncMock()
    mock_api_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_api_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "SKILLS.03_video_ripper.api_client.fetch_shop_videos",
            new_callable=AsyncMock,
        ) as mock_fetch_shop,
        patch(
            "SKILLS.03_video_ripper.api_client.fetch_product_details_videos",
            new_callable=AsyncMock,
        ) as mock_fetch_details,
        patch(
            "SKILLS.03_video_ripper.service.get_supabase",
            return_value=mock_sb,
        ),
        patch(
            "SKILLS.03_video_ripper.service.httpx.AsyncClient",
            side_effect=[mock_api_cm, mock_dl],
        ),
    ):
        mock_fetch_shop.return_value = shop_videos
        mock_fetch_details.return_value = detail_videos

        skill = VideoRipperSkill()
        inp = VideoRipperInput(
            product_id="prod-us",
            product_url="https://tiktok.com/product/prod-us",
            region="US",
            max_videos=5,
        )
        result = await skill.run(inp, _make_ctx())

    assert result.success is True
    assert result.data is not None
    assert result.data.videos_downloaded == 2
    assert result.data.used_product_details_enrichment is True

    # Check that we have videos from both sources
    sources = {v.source for v in result.data.videos}
    assert "shop_videos" in sources
    assert "product_details" in sources

    mock_fetch_shop.assert_awaited_once()
    mock_fetch_details.assert_awaited_once()


@pytest.mark.asyncio
async def test_eu_no_enrichment():
    """When region is not US, product details endpoint is NOT called even if URL provided."""
    shop_videos = [
        _fake_video("v1", views=100000, engagement_rate=0.06, duration=20.0),
    ]

    mock_sb = _mock_supabase()
    mock_dl = _mock_http_client()

    mock_api_cm = AsyncMock()
    mock_api_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_api_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "SKILLS.03_video_ripper.api_client.fetch_shop_videos",
            new_callable=AsyncMock,
        ) as mock_fetch_shop,
        patch(
            "SKILLS.03_video_ripper.api_client.fetch_product_details_videos",
            new_callable=AsyncMock,
        ) as mock_fetch_details,
        patch(
            "SKILLS.03_video_ripper.service.get_supabase",
            return_value=mock_sb,
        ),
        patch(
            "SKILLS.03_video_ripper.service.httpx.AsyncClient",
            side_effect=[mock_api_cm, mock_dl],
        ),
    ):
        mock_fetch_shop.return_value = shop_videos
        mock_fetch_details.return_value = []

        skill = VideoRipperSkill()
        inp = VideoRipperInput(
            product_id="prod-eu",
            product_url="https://tiktok.com/product/prod-eu",
            region="DE",
            max_videos=5,
        )
        result = await skill.run(inp, _make_ctx())

    assert result.success is True
    assert result.data is not None
    assert result.data.videos_downloaded == 1
    assert result.data.used_product_details_enrichment is False

    mock_fetch_shop.assert_awaited_once()
    mock_fetch_details.assert_not_awaited()
