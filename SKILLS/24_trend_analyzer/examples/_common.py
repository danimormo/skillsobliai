"""Shared runner for the three demo scripts.

Each demo calls ``TrendAnalyzerSkill.run()`` directly (bypassing the HTTP
layer) and prints the Markdown rendering. Requires ``ANTHROPIC_API_KEY`` and
a reachable Redis (``REDIS_URL``) in the environment.

Run::

    python -m SKILLS.24_trend_analyzer.examples.demo_text
    python -m SKILLS.24_trend_analyzer.examples.demo_url
    python -m SKILLS.24_trend_analyzer.examples.demo_image  PATH_TO_IMAGE
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys

# Because the package dir is digit-prefixed, we load it via importlib.
_svc_mod = importlib.import_module("SKILLS.24_trend_analyzer.service")
_schema_mod = importlib.import_module("SKILLS.24_trend_analyzer.schemas")

TrendAnalyzerSkill = _svc_mod.TrendAnalyzerSkill
TrendAnalyzerInput = _schema_mod.TrendAnalyzerInput

# core.skill_interface is a plain import path
from core.skill_interface import SkillContext


async def run(input_obj: TrendAnalyzerInput, *, as_json: bool = False) -> int:
    skill = TrendAnalyzerSkill()
    result = await skill.run(input_obj, SkillContext(user_id="demo"))

    if not result.success or result.data is None:
        sys.stderr.write(f"skill failed: {result.error}\n")
        return 1

    if as_json:
        print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))
    else:
        print(result.data.markdown)

    return 0


def main(input_obj: TrendAnalyzerInput) -> None:
    as_json = "--json" in sys.argv
    sys.exit(asyncio.run(run(input_obj, as_json=as_json)))
