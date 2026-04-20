"""Demo: local image path → full TrendReport + Markdown.

Usage:
    python -m SKILLS.24_trend_analyzer.examples.demo_image ./product.jpg
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

from ._common import TrendAnalyzerInput, main


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not argv:
        sys.stderr.write("usage: demo_image.py <path-to-image>\n")
        sys.exit(2)

    path = Path(argv[0])
    if not path.exists():
        sys.stderr.write(f"file not found: {path}\n")
        sys.exit(2)

    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    main(TrendAnalyzerInput(image_b64=b64))
