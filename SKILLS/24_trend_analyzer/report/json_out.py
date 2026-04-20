"""JSON serializer for ``TrendReport``."""

from __future__ import annotations

import json

from ..schemas import TrendReport


def to_json(report: TrendReport, *, indent: int | None = 2) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=indent, default=str)
