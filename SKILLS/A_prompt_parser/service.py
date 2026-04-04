import json
import logging
import time
from pathlib import Path

from core.errors import InvalidParamsError
from core.skill_interface import BaseSkill, SkillContext, SkillResult
from core.supabase_client import get_supabase

from . import api_client, cache
from .schemas import (
    ParsedParams,
    PromptParserInput,
    PromptParserOutput,
)

logger = logging.getLogger(__name__)

SKILL_NAME = "prompt-parser"

# ── Load keyword pools once at import time ───────────────────────────
_KEYWORD_POOLS: dict[str, list[str]] = {}
_pool_path = Path(__file__).resolve().parent.parent.parent / "data" / "tiktok_keyword_pools.json"
try:
    with open(_pool_path) as f:
        _KEYWORD_POOLS = json.load(f)
except Exception:
    logger.warning("Could not load keyword pools from %s", _pool_path)


class PromptParserSkill(BaseSkill[PromptParserInput, PromptParserOutput]):
    name = SKILL_NAME
    version = "1.0.0"
    description = "Interprets free-text prompts into structured search params using Claude Haiku"
    consumes_credits = False
    credit_cost = 0

    def validate(self, input: PromptParserInput) -> bool:
        if not input.prompt or not input.prompt.strip():
            raise InvalidParamsError(
                message="prompt must not be empty",
                skill=SKILL_NAME,
                code="INVALID_PARAMS",
            )
        return True

    async def run(
        self, input: PromptParserInput, ctx: SkillContext
    ) -> SkillResult[PromptParserOutput]:
        start = time.perf_counter()
        self.validate(input)

        # ── Check cache ──────────────────────────────────────────────
        cached_data = await cache.get_cached(input.prompt)
        if cached_data is not None:
            output = PromptParserOutput(**cached_data)
            # Apply country override even on cache hit
            if input.override_countries:
                output.parsed.countries = input.override_countries
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return SkillResult(
                success=True,
                data=output,
                cached=True,
                execution_ms=elapsed_ms,
            )

        # ── Call Claude to parse the prompt ──────────────────────────
        system_prompt = api_client.build_system_prompt(_KEYWORD_POOLS)
        used_defaults = False
        raw_response = ""

        try:
            parsed_dict, raw_response = await api_client.parse_prompt(
                input.prompt, system_prompt
            )
        except Exception:
            logger.exception("Claude parsing failed, using defaults")
            parsed_dict = dict(api_client.DEFAULT_PARAMS)
            used_defaults = True
            raw_response = ""

        # ── Apply defaults for any missing keys ──────────────────────
        for key, default_val in api_client.DEFAULT_PARAMS.items():
            if key not in parsed_dict or parsed_dict[key] is None:
                parsed_dict[key] = default_val
                used_defaults = True

        # ── Override countries if requested ───────────────────────────
        if input.override_countries:
            parsed_dict["countries"] = input.override_countries

        parsed = ParsedParams(**parsed_dict)
        output = PromptParserOutput(
            parsed=parsed,
            raw_response=raw_response,
            used_defaults=used_defaults,
        )

        # ── Persist to Supabase ──────────────────────────────────────
        try:
            supabase = get_supabase()
            supabase.table("research_results").insert(
                {
                    "user_id": ctx.user_id,
                    "skill": SKILL_NAME,
                    "query_params": input.model_dump(),
                    "result": output.model_dump(),
                    "items_count": len(parsed.countries),
                }
            ).execute()
        except Exception:
            logger.exception("Failed to persist parser results to Supabase")

        # ── Cache result ─────────────────────────────────────────────
        await cache.set_cached(input.prompt, output.model_dump())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return SkillResult(
            success=True,
            data=output,
            cached=False,
            execution_ms=elapsed_ms,
        )
