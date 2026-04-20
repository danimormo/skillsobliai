"""Demo: text keyword → full TrendReport + Markdown.

Usage:
    python -m SKILLS.24_trend_analyzer.examples.demo_text "mini waffle maker"
    python -m SKILLS.24_trend_analyzer.examples.demo_text "collagen supplement" --json
"""

from __future__ import annotations

import sys

from ._common import TrendAnalyzerInput, main

DEFAULT_KEYWORD = "collagen supplement"


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    keyword = " ".join(argv) if argv else DEFAULT_KEYWORD
    main(TrendAnalyzerInput(text=keyword))
