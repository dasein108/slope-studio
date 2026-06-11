"""DEPRECATED shim — the brand pipeline now lives in the studio package.

Use the CLI instead (logic: studio/marketing/brand.py):

    studio brand <spec.json>                 # real (~$0.12, fal Nano Banana)
    studio brand <spec.json> --provider stub # free offline wiring test

Kept only so old muscle memory / scripts still resolve. See SKILL.md.
"""
from __future__ import annotations

import sys

if __name__ == "__main__":
    spec = sys.argv[1] if len(sys.argv) > 1 else "<spec.json>"
    sys.exit(
        "make_brand.py is deprecated — run:\n"
        f"    studio brand {spec}\n"
        "(add --provider stub for a free wiring test)"
    )
