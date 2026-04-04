import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.skill_interface import SkillContext

from SKILLS.03_kalodata_ripper.schemas import KalodataRipperInput
from SKILLS.03_kalodata_ripper.service import KalodataRipperSkill


def _make_ctx(user_id: str = "user-1") -> SkillContext:
    return SkillContext(user_id=user_id)


def _fake_video(ad_id: str, views: int = 50000, engagement_rate: float = 0.05, duration: float = 30.0):
    return {
        "ad_id": ad_id,
        "download_url": f"https://cdn.example.com/{ad_id}.mp4",
        "views": views,
        "engagement_rate": engagement_rate,
        "duration": duration,
        "thumbnail_url": f"https://cdn.example.com/{ad_id}_thumb.jpg",
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


@pytest.mark.asyncio
async def test_happy_path_downloads_and_uploads():
    """Service fetches videos, downloads them, uploads to storage, returns result."""
    videos = [
        _fake_video("v1", views=100000, engagement_rate=0.06, duration=25.0),
        _fake_video("v2", views=80000, engagement_rate=0.04, duration=40.0),
        _fake_video("v3", views=200000, engagement_rate=0.08, duration=15.0),
    ]

    mock_sb = _mock_supabase()

    # Mock httpx response for video downloads
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"\x00\x00\x00\x1cftypisom"  # fake mp4 bytes
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = mock_response
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("SKILLS.03_kalodata_ripper.service.api_client.fetch_product_videos", new_callable=AsyncMock) as mock_fetch,
        patch("SKILLS.03_kalodata_ripper.service.get_supabase", return_value=mock_sb),
        patch("SKILLS.03_kalodata_ripper.service.httpx.AsyncClient", return_value=mock_http_client),
    ):
        mock_fetch.return_value = videos

        skill = KalodataRipperSkill()
        inp = KalodataRipperInput(product_id="prod-123", max_videos=5, min_views=10000, min_engagement_rate=0.02)
        result = await skill.run(inp, _make_ctx())

    assert result.success is True
    assert result.cached is False
    assert result.data is not None
    assert result.data.product_id == "prod-123"
    assert result.data.videos_downloaded == 3
    assert len(result.data.videos) == 3

    # Verify timestamp calculations for first video (duration=25.0)
    v1 = result.data.videos[0]
    assert v1.ad_id == "v1"
    assert v1.suggested_hook_end == min(3.0, 25.0 * 0.15)
    assert v1.suggested_cta_start == 20.0  # 25 - 5


@pytest.mark.asyncio
async def test_upstream_error_propagates():
    """When the API client raises an error, the service propagates it."""
    from core.errors import UpstreamError

    with (
        patch("SKILLS.03_kalodata_ripper.service.api_client.fetch_product_videos", new_callable=AsyncMock) as mock_fetch,
    ):
        mock_fetch.side_effect = UpstreamError(
            message="Upstream returned 500",
            skill="kalodata-ripper",
            code="UPSTREAM_ERROR",
        )

        skill = KalodataRipperSkill()
        inp = KalodataRipperInput(product_id="prod-fail")

        with pytest.raises(UpstreamError):
            await skill.run(inp, _make_ctx())


@pytest.mark.asyncio
async def test_empty_results_after_filtering():
    """When all videos are filtered out, the result has zero videos."""
    videos = [
        _fake_video("v1", views=500, engagement_rate=0.001),   # below min_views
        _fake_video("v2", views=200, engagement_rate=0.005),   # below both
    ]

    mock_sb = _mock_supabase()

    with (
        patch("SKILLS.03_kalodata_ripper.service.api_client.fetch_product_videos", new_callable=AsyncMock) as mock_fetch,
        patch("SKILLS.03_kalodata_ripper.service.get_supabase", return_value=mock_sb),
    ):
        mock_fetch.return_value = videos

        skill = KalodataRipperSkill()
        inp = KalodataRipperInput(product_id="prod-empty", min_views=10000, min_engagement_rate=0.02)
        result = await skill.run(inp, _make_ctx())

    assert result.success is True
    assert result.data is not None
    assert result.data.videos_downloaded == 0
    assert result.data.videos == []
