import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SKILLS.product_importer.schemas import ProductImportInput
from SKILLS.product_importer.service import ProductImporterSkill
from core.errors import IntegrationNotConnectedError
from core.skill_interface import SkillContext


@pytest.fixture
def skill():
    return ProductImporterSkill()


@pytest.fixture
def ctx():
    return SkillContext(user_id="test-user-001")


@pytest.fixture
def sample_input():
    return ProductImportInput(
        shop_domain="test-store.myshopify.com",
        title="Amazing Widget",
        description_html="<p>Best widget ever</p>",
        vendor="WidgetCo",
        product_type="Gadgets",
        tags=["widget", "trending"],
        image_urls=[
            "https://cdn.example.com/img1.jpg",
            "https://cdn.example.com/img2.jpg",
        ],
        cost_usd=10.0,
        markup_multiplier=3.0,
    )


def _mock_supabase(*, has_credentials: bool = True):
    """Return a MagicMock that simulates Supabase client."""
    mock_sb = MagicMock()

    # user_integrations select chain
    creds_data = (
        [{"access_token": "shpat_fake_token"}] if has_credentials else []
    )
    creds_resp = MagicMock()
    creds_resp.data = creds_data

    select_chain = MagicMock()
    select_chain.select.return_value = select_chain
    select_chain.eq.return_value = select_chain
    select_chain.limit.return_value = select_chain
    select_chain.execute.return_value = creds_resp

    # import_jobs insert / update chain
    jobs_chain = MagicMock()
    jobs_chain.insert.return_value = jobs_chain
    jobs_chain.update.return_value = jobs_chain
    jobs_chain.eq.return_value = jobs_chain
    jobs_chain.execute.return_value = MagicMock()

    def table_router(name: str):
        if name == "user_integrations":
            return select_chain
        return jobs_chain

    mock_sb.table.side_effect = table_router
    return mock_sb


def _shopify_product_response(product_id: int = 123456789):
    return {
        "id": product_id,
        "title": "Amazing Widget",
        "handle": "amazing-widget",
        "variants": [{"id": 1, "title": "Default", "price": "30.00"}],
    }


@pytest.mark.asyncio
async def test_happy_path(skill, ctx, sample_input):
    """Successful product import creates product and uploads images."""
    mock_sb = _mock_supabase(has_credentials=True)

    with (
        patch(
            "SKILLS.product_importer.service.get_supabase",
            return_value=mock_sb,
        ),
        patch(
            "SKILLS.product_importer.service.ShopifyClient",
        ) as MockClient,
    ):
        client_instance = AsyncMock()
        client_instance.find_product_by_title = AsyncMock(return_value=None)
        client_instance.create_product = AsyncMock(
            return_value=_shopify_product_response()
        )
        client_instance.add_image = AsyncMock(return_value={"id": 1})
        MockClient.return_value = client_instance

        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data is not None
    assert result.data.shopify_product_id == "123456789"
    assert result.data.price == 30.0
    assert result.data.variants_count == 1
    assert result.data.images_uploaded == 2
    assert result.data.status == "completed"
    assert result.data.title == "Amazing Widget"
    assert "test-store.myshopify.com" in result.data.shopify_product_url
    assert "amazing-widget" in result.data.shopify_storefront_url

    client_instance.create_product.assert_awaited_once()
    assert client_instance.add_image.await_count == 2


@pytest.mark.asyncio
async def test_missing_integration(skill, ctx, sample_input):
    """Raises IntegrationNotConnectedError when no Shopify credentials found."""
    mock_sb = _mock_supabase(has_credentials=False)

    with (
        patch(
            "SKILLS.product_importer.service.get_supabase",
            return_value=mock_sb,
        ),
        pytest.raises(IntegrationNotConnectedError) as exc_info,
    ):
        await skill.run(sample_input, ctx)

    assert "INTEGRATION_NOT_CONNECTED" == exc_info.value.code
    assert "shopify" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_partial_image_failure(skill, ctx, sample_input):
    """When some images fail to upload, status is 'partial'."""
    mock_sb = _mock_supabase(has_credentials=True)

    async def _add_image_side_effect(product_id, image_url):
        if "img2" in image_url:
            raise RuntimeError("upload failed")
        return {"id": 1}

    with (
        patch(
            "SKILLS.product_importer.service.get_supabase",
            return_value=mock_sb,
        ),
        patch(
            "SKILLS.product_importer.service.ShopifyClient",
        ) as MockClient,
    ):
        client_instance = AsyncMock()
        client_instance.find_product_by_title = AsyncMock(return_value=None)
        client_instance.create_product = AsyncMock(
            return_value=_shopify_product_response()
        )
        client_instance.add_image = AsyncMock(side_effect=_add_image_side_effect)
        MockClient.return_value = client_instance

        result = await skill.run(sample_input, ctx)

    assert result.success is True
    assert result.data is not None
    assert result.data.status == "partial"
    assert result.data.images_uploaded == 1
