"""Shared Playwright helper used by the JS-heavy scraping providers.

Keeping launch / stealth / UA-rotation in one place lets every provider share
the same anti-bot defaults (and lets the tests monkey-patch a single seam).

Usage::

    html = await fetch_html("https://facebook.com/ads/library/?q=foo")

The helper launches a *new* browser per call with a random UA and cookie
jar under ``settings.data_dir``. That's deliberately wasteful but keeps
each request isolated — fine given how rarely any single provider is
invoked (once per skill run, behind a 6-24h cache).
"""

from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)


_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

_COOKIE_DIR = Path("/tmp/trend_analyzer/cookies")
_COOKIE_DIR.mkdir(parents=True, exist_ok=True)


async def random_delay(min_s: float = 5.0, max_s: float = 15.0) -> None:
    """Jitter between consecutive requests to the same host."""
    delay = random.uniform(min_s, max_s)
    logger.debug("browser.sleep %.1fs", delay)
    await asyncio.sleep(delay)


def random_user_agent() -> str:
    return random.choice(_USER_AGENTS)


async def fetch_html(
    url: str,
    *,
    wait_selector: str | None = None,
    timeout_ms: int = 30_000,
    cookie_namespace: str = "default",
    headless: bool = True,
) -> str:
    """Fetch ``url`` using a stealthy Playwright context and return the HTML.

    The Playwright imports are lazy so the package is optional at runtime
    (tests can monkey-patch this function without having Playwright
    installed). If Playwright is missing in production, the caller gets
    :class:`RuntimeError` and the provider's failure policy kicks in.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "playwright is not installed — run `playwright install chromium`"
        ) from exc

    try:
        from playwright_stealth import stealth_async
    except ImportError:  # pragma: no cover
        stealth_async = None  # type: ignore[assignment]

    storage_path = _COOKIE_DIR / f"{cookie_namespace}.json"
    storage_state = str(storage_path) if storage_path.exists() else None

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        try:
            context = await browser.new_context(
                user_agent=random_user_agent(),
                locale="en-US",
                storage_state=storage_state,
            )
            page = await context.new_page()
            if stealth_async is not None:
                try:
                    await stealth_async(page)
                except Exception as exc:  # pragma: no cover
                    logger.debug("stealth.apply_failed: %s", exc)

            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except Exception as exc:
                    logger.debug("wait_selector missed %s: %s", wait_selector, exc)

            html = await page.content()
            try:
                await context.storage_state(path=str(storage_path))
            except Exception as exc:  # pragma: no cover
                logger.debug("storage_state.save_failed: %s", exc)
            return html
        finally:
            await browser.close()
