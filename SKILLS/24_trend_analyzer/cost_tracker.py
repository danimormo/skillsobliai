"""Per-run cost tracker with hard-cap enforcement.

Design goals:
    * Every provider call that spends money MUST add an entry.
    * When the running total crosses ``cap_usd`` the next ``add()`` raises
      :class:`CostCapExceeded` — unless the tracker was built with
      ``force=True`` (the user explicitly opted out via the ``--force`` flag).
    * The tracker is request-scoped (one per ``service.run()`` invocation) so
      concurrent runs do not interfere.

The pricing constants are approximate published rates as of 2026-04.
Keep them close to reality but err on the generous side — when in doubt
log a higher cost so the cap triggers early rather than late.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Iterator

from core.errors import SkillBaseError

from .schemas import CostBreakdown, CostEntry

logger = logging.getLogger(__name__)


# ── Pricing constants (USD) ────────────────────────────────────────────────

# Anthropic Claude Haiku 4.5 — $1/MTok input, $5/MTok output (approx.)
CLAUDE_HAIKU_INPUT_PER_MTOK = 1.00
CLAUDE_HAIKU_OUTPUT_PER_MTOK = 5.00

# Most scraping providers are free; we still log them with usd=0 to keep the
# full trace. A non-zero entry should appear only for paid API calls.


class CostCapExceeded(SkillBaseError):
    """Raised when adding an entry would push the total past the cap."""


class CostTracker:
    """Thread-safe cost accumulator, request-scoped."""

    def __init__(self, cap_usd: float = 0.05, force: bool = False) -> None:
        self._cap = cap_usd
        self._force = force
        self._entries: list[CostEntry] = []
        self._total = 0.0
        self._lock = threading.Lock()

    # ── Recording ──────────────────────────────────────────────────────

    def add(
        self,
        *,
        provider: str,
        operation: str,
        usd: float,
        units: int = 1,
        note: str = "",
    ) -> None:
        """Record a cost entry. Raises :class:`CostCapExceeded` past cap."""
        if usd < 0:
            raise ValueError("cost must be non-negative")

        with self._lock:
            new_total = self._total + usd
            entry = CostEntry(
                provider=provider,
                operation=operation,
                usd=round(usd, 6),
                units=units,
                note=note,
            )
            self._entries.append(entry)
            self._total = new_total
            logger.debug(
                "cost.add provider=%s op=%s usd=%.6f total=%.6f",
                provider,
                operation,
                usd,
                new_total,
            )

            if new_total > self._cap and not self._force:
                raise CostCapExceeded(
                    message=(
                        f"Cost cap ${self._cap:.4f} exceeded "
                        f"(attempted ${new_total:.4f} after '{provider}:{operation}'). "
                        "Pass force=true to bypass."
                    ),
                    skill="trend-analyzer",
                    code="COST_CAP_EXCEEDED",
                )

    def add_claude_haiku(
        self,
        *,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        note: str = "",
    ) -> None:
        """Convenience wrapper for Claude Haiku 4.5 usage."""
        usd = (
            input_tokens / 1_000_000 * CLAUDE_HAIKU_INPUT_PER_MTOK
            + output_tokens / 1_000_000 * CLAUDE_HAIKU_OUTPUT_PER_MTOK
        )
        self.add(
            provider="anthropic",
            operation=operation,
            usd=usd,
            units=input_tokens + output_tokens,
            note=note or f"in={input_tokens} out={output_tokens}",
        )

    # ── Inspection ─────────────────────────────────────────────────────

    @property
    def total(self) -> float:
        return round(self._total, 6)

    @property
    def cap(self) -> float:
        return self._cap

    def snapshot(self) -> CostBreakdown:
        with self._lock:
            return CostBreakdown(
                total_usd=round(self._total, 6),
                entries=list(self._entries),
                cap_hit=self._total > self._cap,
                cap_usd=self._cap,
            )


@contextmanager
def tracker(cap_usd: float = 0.05, force: bool = False) -> Iterator[CostTracker]:
    """Context manager yielding a fresh :class:`CostTracker`."""
    tr = CostTracker(cap_usd=cap_usd, force=force)
    try:
        yield tr
    finally:
        logger.info(
            "cost.summary total=%.6f cap=%.4f entries=%d force=%s",
            tr.total,
            tr.cap,
            len(tr.snapshot().entries),
            force,
        )
