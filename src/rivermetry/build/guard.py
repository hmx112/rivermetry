from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN = ("safe to", "dangerous to", "good for fishing", "custom flood risk")


def guard_output(root: str | Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    sitemap = (root / "sitemap.xml").read_text() if (root / "sitemap.xml").exists() else ""
    for html in root.rglob("*.html"):
        text = html.read_text(errors="ignore")
        lower = text.lower()
        for phrase in FORBIDDEN:
            if phrase in lower:
                errors.append(f"forbidden phrase {phrase!r} in {html}")
        if "<link rel=\"canonical\"" not in text:
            errors.append(f"missing canonical in {html}")
        if 'name="robots" content="noindex"' in text and str(html).replace(str(root), "") in sitemap:
            errors.append(f"noindex page appears in sitemap: {html}")
    if re.search(r"/(candidate|preview)/", sitemap):
        errors.append("candidate/preview path found in sitemap")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    root = args[0] if args else "dist"
    errors = guard_output(root)
    for error in errors:
        print(error)
    return 4 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
