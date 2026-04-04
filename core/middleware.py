import time
import uuid
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.errors import (
    SkillBaseError,
    TokenExpiredError,
    TokenMissingError,
    RateLimitError,
    InvalidParamsError,
    UpstreamError,
    InsufficientCreditsError,
    IntegrationNotConnectedError,
    InvalidApiKeyError,
    VertexAIError,
    VertexAITimeoutError,
    GoogleVisionError,
    ManusError,
    ManusTimeoutError,
    ShopifyError,
    MetaAPIError,
)

logger = logging.getLogger("skillsobliai")

ERROR_STATUS_MAP: dict[type, int] = {
    TokenExpiredError: 401,
    TokenMissingError: 401,
    InvalidApiKeyError: 401,
    RateLimitError: 429,
    InvalidParamsError: 422,
    UpstreamError: 502,
    InsufficientCreditsError: 402,
    IntegrationNotConnectedError: 403,
    VertexAIError: 502,
    VertexAITimeoutError: 504,
    GoogleVisionError: 502,
    ManusError: 502,
    ManusTimeoutError: 504,
    ShopifyError: 502,
    MetaAPIError: 502,
}


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.headers["x-request-id"] = request_id
        response.headers["x-execution-ms"] = str(elapsed_ms)
        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )
        return response
