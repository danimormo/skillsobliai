"""Human-readable Markdown renderer for ``TrendReport``."""

from __future__ import annotations

from ..schemas import TrendReport


def to_markdown(report: TrendReport) -> str:
    fp = report.fingerprint
    lines: list[str] = []

    lines.append(f"# Trend Report — {fp.primary_keyword}")
    lines.append("")
    lines.append(f"**Verdict:** {_badge(report.verdict)}  ")
    lines.append(f"**Score:** {report.score:.1f} / 100  ")
    lines.append(f"**Rationale:** {report.rationale}")
    lines.append("")

    lines.append("## Sub-scores")
    lines.append("")
    lines.append("| Sub-score | Score | Weight | Notes |")
    lines.append("|-----------|------:|-------:|-------|")
    for s in report.sub_scores:
        lines.append(
            f"| {s.name:<12} | {s.value:>5.1f} | {s.weight * 100:>4.0f}% | {s.explanation} |"
        )
    lines.append("")

    lines.append("## Fingerprint")
    lines.append("")
    lines.append(f"- Category: `{fp.category}`")
    lines.append(f"- Secondary keywords: {', '.join(fp.secondary_keywords) or '—'}")
    lines.append(f"- Attributes: {', '.join(fp.product_attributes) or '—'}")
    if fp.estimated_retail_price_usd is not None:
        lines.append(f"- Estimated retail: ${fp.estimated_retail_price_usd:.2f}")
    lines.append("")

    if report.seasonality.summary:
        lines.append("## Seasonality")
        lines.append("")
        lines.append(report.seasonality.summary)
        lines.append("")

    if report.geography:
        lines.append("## Geography (top growing markets)")
        lines.append("")
        lines.append("| Country | Current | Δ vs prior 90d |")
        lines.append("|---------|--------:|---------------:|")
        for g in report.geography:
            sign = "+" if g.delta_pct >= 0 else ""
            lines.append(f"| {g.country} | {g.current_value} | {sign}{g.delta_pct:.0f}% |")
        lines.append("")

    if report.saturation.top_competitors:
        lines.append("## Competition")
        lines.append("")
        lines.append(f"**Stores selling this product:** {report.saturation.stores_found}")
        lines.append("")
        for c in report.saturation.top_competitors:
            price = f" — ${c.price_usd:.2f}" if c.price_usd is not None else ""
            url = f" ({c.product_url})" if c.product_url else ""
            lines.append(f"- `{c.domain}`{price}{url}")
        lines.append("")

    if report.meta_ads.active_ads_30d or report.meta_ads.top_advertisers:
        lines.append("## Meta Ads Library")
        lines.append("")
        lines.append(f"- Active ads (last 30d): **{report.meta_ads.active_ads_30d}**")
        lines.append(f"- Active ads (last 7d):  **{report.meta_ads.active_ads_7d}**")
        if report.meta_ads.earliest_ad_date:
            lines.append(f"- Earliest ad tracked: {report.meta_ads.earliest_ad_date}")
        if report.meta_ads.top_advertisers:
            lines.append(
                "- Top advertisers: " + ", ".join(report.meta_ads.top_advertisers[:5])
            )
        lines.append("")

    if report.price.retail_price_median_usd or report.price.supplier_price_median_usd:
        lines.append("## Price & Margin")
        lines.append("")
        p = report.price
        if p.retail_price_median_usd:
            rng = ""
            if p.retail_price_range_usd:
                rng = f" (range ${p.retail_price_range_usd[0]:.2f} – ${p.retail_price_range_usd[1]:.2f})"
            lines.append(f"- Retail median: **${p.retail_price_median_usd:.2f}**{rng}")
        if p.supplier_price_median_usd:
            lines.append(f"- Supplier median: ${p.supplier_price_median_usd:.2f}")
        if p.gross_margin_pct is not None:
            lines.append(f"- Estimated gross margin: **{p.gross_margin_pct:.0f}%**")
        lines.append("")

    if report.creatives.angles:
        lines.append("## Creative Angles")
        lines.append("")
        for i, a in enumerate(report.creatives.angles, 1):
            lines.append(f"{i}. **{a.name}** _(format: {a.format_hint}, emotion: {a.target_emotion})_")
            lines.append(f"   {a.description}")
        lines.append("")

    if report.creatives.hooks:
        lines.append("## Hook Copy")
        lines.append("")
        for i, h in enumerate(report.creatives.hooks, 1):
            lines.append(f"{i}. _{h.style}_ — {h.text}")
        lines.append("")

    lines.append("## Cost")
    lines.append("")
    lines.append(f"- Total: **${report.cost.total_usd:.4f}** (cap ${report.cost.cap_usd:.2f})")
    if report.cost.entries:
        lines.append("")
        lines.append("| Provider | Operation | USD | Units |")
        lines.append("|----------|-----------|----:|------:|")
        for e in report.cost.entries:
            lines.append(
                f"| {e.provider} | {e.operation} | {e.usd:.4f} | {e.units} |"
            )
    lines.append("")

    if report.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in report.warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _badge(v: str) -> str:
    return {"GO": "**GO**", "WAIT": "**WAIT**", "AVOID": "**AVOID**"}.get(v, v)
