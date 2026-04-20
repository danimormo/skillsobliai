"""Demo: product URL → full TrendReport + Markdown.

Usage:
    python -m SKILLS.24_trend_analyzer.examples.demo_url https://shop.com/products/xyz
"""

from __future__ import annotations

import sys

from ._common import TrendAnalyzerInput, main

DEFAULT_URL = "https://dashstore.com/products/mini-maker"


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    url = argv[0] if argv else DEFAULT_URL
    main(TrendAnalyzerInput(url=url))  # type: ignore[arg-type]
